"""Run the farming-zone regions in tiled mode, one 100 km tile at a time.

    python -m cropconv.regional --list                    # tiles per region
    python -m cropconv.regional --regions southwest-manitoba-uplands-mb --out /tmp/data
    python -m cropconv.regional                           # all 14 regions (hours, see README)
    python -m cropconv.regional --dry-run                 # print the plan only

Why tiles: a province is far too big to hold as one raster per year (an earlier
whole-window check was killed for memory). Each tile of the fixed ADR 0004 grid
(100 km squares in EPSG:3978) is fetched, converted and aggregated on its own,
with at most five years of one tile (about 11 million pixels each) in memory
at a time. The result of a tile is cached on disk, so a run can be stopped and
resumed, and a later run for more regions only does the tiles it has not done.

Halo: each raster extends one cell (1 km) beyond the tile on every side, and only
the cells inside the tile are written. The halo makes the noise filters exact:
a patch that reaches the window edge has at least 34 pixels in view, so the 6 pixel
patch rule keeps it exactly as the whole-window run would, and the 3x3 majority
filter needs one pixel. Cell values therefore equal those of a single big run
(checked by test on synthetic rasters).

Cells outside the selected regions are dropped, so every region in the index is
complete (a tile on a region edge also holds cells of its neighbours, which are only
kept when that neighbour is selected). See docs/design/05_regional_partitioning.md.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime
import gc
import gzip
import hashlib
import json
import shutil
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import shapely
from pyproj import Proj, Transformer
from shapely import box
from shapely.geometry import shape

from . import aggregate as agg
from . import classes as cl
from . import convert as cv
from . import fetch as fx
from . import regions as rg
from . import run as rn
from . import summaries, tiling

AREA_ID = "mb-sk-farming-zone"
AREA_NAME = "Manitoba and Saskatchewan farming zone"
HALO_M = 1000  # one 1 km cell on every side of a tile
RESULTS_DIR = "regional"  # under the cache directory
PX = fx.PIXEL_M

CAVEAT_2011 = (
    "The 2011 to 2025 interval shows much more conversion than the later intervals (roughly 2.5 to 4.5 times the "
    "2016 to 2025 interval across the farming zone), and part of that may be a mapping difference between years "
    "rather than real change. The 2011 map also covers less of the far north than later years. Prefer the 2016 and "
    "2021 baselines."
)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- tile selection and geometry

def region_features(regions: dict, ids=None):
    feats = {f["properties"]["id"]: f for f in regions["features"]}
    if ids is None:
        return feats
    missing = [i for i in ids if i not in feats]
    if missing:
        raise ValueError(f"unknown region ids {missing}; choose from {sorted(feats)}")
    return {i: feats[i] for i in ids}


def tiles_for_regions(regions: dict, ids=None, tile_km: int = tiling.TILE_KM) -> dict[str, list[tuple[int, int]]]:
    """{region id: sorted [(col, row)]} for the tiles whose square meets the region (EPSG:3978)."""
    to_work = Transformer.from_crs(4326, 3978, always_xy=True)
    tile_m = tile_km * 1000
    out = {}
    for rid, f in region_features(regions, ids).items():
        g = shape(f["geometry"])
        gw = shapely.transform(g, lambda c: np.column_stack(to_work.transform(c[:, 0], c[:, 1])))
        x0, y0, x1, y1 = gw.bounds
        found = []
        for c in range(int(np.floor(x0 / tile_m)), int(np.floor(x1 / tile_m)) + 1):
            for r in range(int(np.floor(y0 / tile_m)), int(np.floor(y1 / tile_m)) + 1):
                if gw.intersects(box(c * tile_m, r * tile_m, (c + 1) * tile_m, (r + 1) * tile_m)):
                    found.append((c, r))
        out[rid] = sorted(found)
    return out


def all_tiles(per_region: dict) -> list[tuple[int, int]]:
    return sorted({t for v in per_region.values() for t in v})


def tile_window(col: int, row: int, tile_km: int = tiling.TILE_KM, halo_m: int = HALO_M):
    """Raster bbox, 1 km grid and core cell range of a tile (EPSG:3978 metres).

    The raster starts one halo before the tile corner, so its pixels never straddle a cell edge at
    the left or top. The grid is the raster rounded up to whole cells; core cells are those whose
    centre lies inside the tile.
    """
    tile_m = tile_km * 1000
    x0, y0 = col * tile_m - halo_m, row * tile_m - halo_m
    n_px = -(-(tile_m + 2 * halo_m) // PX)
    raster = (x0, y0, x0 + n_px * PX, y0 + n_px * PX)
    n_cells = -(-(n_px * PX) // agg.CELL_M)
    grid = (x0, y0 + n_px * PX - n_cells * agg.CELL_M, x0 + n_cells * agg.CELL_M, y0 + n_px * PX)
    h = halo_m // agg.CELL_M
    return raster, grid, (h, h + tile_km)  # core cell index range (columns, and rows from the top)


# ---------------------------------------------------------------- per tile computation

def cache_key(years, latest, params, targets, tile_km, sensitivity, rows) -> str:
    blob = json.dumps({
        "years": list(years), "latest": latest, "params": asdict(params), "targets": list(targets),
        "tile_km": tile_km, "halo": HALO_M, "sensitivity": bool(sensitivity), "baselines": rn.BASELINES,
        "classes": [list(map(str, r.values())) for r in rows], "presets": [p[0] for p in rn.PRESETS],
        "v": 2,  # 2: per-cell mapped area for the coverage measure
    }, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def read_stack_year(year, raster, known, group_lut, natural_lut, fetch_fn=None):
    """One year of one tile as (group array, natural index array, valid fraction, mapped mask), raster freed."""
    path = (fetch_fn or fx.fetch_year)(year, raster)
    arr, transform = fx.read_year(path)
    if abs(transform.a - PX) > 1e-6 or abs(transform.e + PX) > 1e-6:
        raise ValueError(f"{year}: pixel size is {transform.a}, expected {PX}")
    return arr_to_groups(arr, known, group_lut, natural_lut)


def arr_to_groups(arr, known, group_lut, natural_lut):
    """(group array, natural index array, valid fraction, mapped mask); code 0 is unmapped."""
    fx.assert_codes_unmodified(arr, known)
    mapped = arr != 0
    return group_lut[arr], natural_lut[arr], float(mapped.mean()), mapped


def compute_tile(col, row, readers, years, latest, params, targets, tile_km=tiling.TILE_KM, sensitivity=False):
    """Cells of one tile as a dict of numpy arrays (None for a tile with no data at all).

    readers(year, raster) -> (groups, naturals, valid fraction, mapped mask) reads one year, so only one raw
    raster exists at a time. Returned arrays cover the base cell set (cells with natural cover under
    the default settings, plus, with sensitivity, under any preset); `keep` marks the default ones.
    """
    raster, grid, (c0, c1) = tile_window(col, row, tile_km)
    n_cols = (grid[2] - grid[0]) // agg.CELL_M
    n_rows = (grid[3] - grid[1]) // agg.CELL_M
    n_cells = n_cols * n_rows
    groups, naturals, valid, mapped = {}, {}, {}, {}
    for y in years:  # one year at a time
        groups[y], naturals[y], valid[y], mapped[y] = readers(y, raster)
        if groups[y].shape != groups[years[0]].shape:
            raise ValueError(f"{y}: shape differs from {years[0]}")
    top = max(valid.values())
    if top == 0:
        return None  # outside the data (sea, other country)
    if valid[latest] == 0:
        # Far north: only an older year maps it, so there is nothing to compare against the latest.
        print(f"warning: tile {col}_{row}: no {latest} data, skipped", flush=True)
        return None
    for y, v in valid.items():
        if v < 0.5 * top:
            # The ACI mapped extent differs by year (the far north is mapped only in some years).
            # Unmapped pixels are not natural cover and not conversion, so the tile is kept.
            print(f"warning: tile {col}_{row} {y}: only {v:.0%} of the window is mapped against {top:.0%}", flush=True)

    xs = grid[0] + (np.arange(n_cols) + 0.5) * agg.CELL_M
    ys = grid[3] - (np.arange(n_rows) + 0.5) * agg.CELL_M
    gx, gy = np.meshgrid(xs, ys)
    gx, gy = gx.ravel(), gy.ravel()
    lon, lat = Transformer.from_crs(3978, 4326, always_xy=True).transform(gx, gy)
    scale = np.asarray(Proj("EPSG:3978").get_factors(lon, lat).areal_scale)
    pixel_m2 = PX * PX / scale
    pixel_ha = pixel_m2 / 1e4
    cells = agg.pixel_cells(groups[years[0]].shape, raster[0], raster[3], grid[3], PX, n_cols, n_rows)
    area_ha = np.bincount(cells[cells >= 0], minlength=n_cells) * pixel_ha
    pm2 = float(np.mean(pixel_m2))
    flat = np.arange(n_cells)
    core = ((flat % n_cols >= c0) & (flat % n_cols < c1) & (flat // n_cols >= c0) & (flat // n_cols < c1))

    # Mapped area (pixels with data, any class) per core cell and year: the coverage measure.
    mp_cells = np.flatnonzero(core)
    mp_ha = np.stack([np.bincount(cells[mapped[y] & (cells >= 0)], minlength=n_cells)[mp_cells] * pixel_ha[mp_cells]
                      for y in years])
    del mapped

    res = rn.interval_masks(groups, naturals, latest, params, pm2, years, targets)
    nat = {b: agg.natural_counts(res[b][0], cells, n_cells) for b in res}
    conv = {b: {t: agg.converted_counts(res[b][0], res[b][1][t], cells, n_cells) for t in targets} for b in res}
    keep = np.zeros(n_cells, dtype=bool)
    for b in res:
        for c in cl.NATURAL_CLASSES:
            keep |= nat[b][c] > 0
    base = keep.copy()

    sens = {}
    if sensitivity:
        for pid, _label, kw in rn.PRESETS:
            sres = rn.interval_masks(groups, naturals, latest, replace(params, **kw), pm2, years, ["crop"])
            for b, (snat, sconv, _) in sres.items():
                nc = agg.sum_by_cell(snat > 0, cells, n_cells)
                cc = agg.sum_by_cell(sconv["crop"], cells, n_cells)
                sens[(pid, b)] = (nc * pixel_ha, cc * pixel_ha)
                base |= nc > 0
    base &= core
    keep &= core

    sel = np.flatnonzero(base)
    out = {
        "x": gx[sel], "y": gy[sel], "lon": np.round(lon[sel], 5), "lat": np.round(lat[sel], 5),
        "area_ha": np.round(area_ha[sel], 2), "keep": keep[sel],
    }
    for b in res:
        for c in cl.NATURAL_CLASSES:
            out[f"nat__{b}__{c}"] = np.round(nat[b][c][sel] * pixel_ha[sel], 2)
            for t in targets:
                out[f"conv__{b}__{t}__{c}"] = np.round(conv[b][t][c][sel] * pixel_ha[sel], 2)
    for (pid, b), (nha, cha) in sens.items():
        out[f"sens__{pid}__{b}__nat"] = nha[sel]
        out[f"sens__{pid}__{b}__conv"] = cha[sel]
    anym = (mp_ha > 0).any(axis=0)
    out["mp_lon"] = np.round(lon[mp_cells][anym], 5)
    out["mp_lat"] = np.round(lat[mp_cells][anym], 5)
    out["mp_years"] = np.array(years, dtype=np.int32)
    out["mp_ha"] = np.round(mp_ha[:, anym], 2)
    out["persist"] = np.array([res[b][2] or 0 for b in sorted(res)], dtype=np.int32)
    out["baselines"] = np.array(sorted(res), dtype=np.int32)
    del groups, naturals
    gc.collect()
    return out


def save_tile(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **(data if data is not None else {"empty": np.array([1])}))
    tmp.rename(path)


def load_tile(path: Path):
    with np.load(path) as z:
        d = {k: z[k] for k in z.files}
    return None if "empty" in d else d


# ---------------------------------------------------------------- assembly

def build_intervals(d, targets, mask, latest):
    ivs = {}
    for b in d["baselines"].tolist():
        converted = {}
        for t in targets:
            by = {}
            for c in cl.NATURAL_CLASSES:
                arr = d[f"conv__{b}__{t}__{c}"][mask]
                if arr.any():
                    by[c] = arr.tolist()
            if by:
                converted[t] = by
        ivs[f"{b}-{latest}"] = {
            "natural_ha": {c: d[f"nat__{b}__{c}"][mask].tolist() for c in cl.NATURAL_CLASSES},
            "converted_ha": converted,
        }
    return ivs


def assemble(out_area: Path, area_id: str, tile_files: dict, regions: dict, selected: list[str], targets, latest,
             tile_km, sensitivity):
    """Write tiles, index.json and return (index, stats, sensitivity sums, persistence years, bbox).

    tile_files {(col,row): npz path}. Tiles are read one at a time.
    """
    tdir = out_area / tiling.TILES_DIR
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    order, _ = tiling.region_table([], regions)
    lookup = {r: i for i, r in enumerate(order)}
    names = {f["properties"]["id"]: f["properties"]["name"] for f in regions["features"]}
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)
    chosen = set(selected)
    tiles, stats = [], []
    region_tiles = {r: [] for r in order}
    region_cells = {r: 0 for r in order}
    region_area = {r: 0.0 for r in order}
    region_parts = {r: [] for r in order}
    region_mapped = {r: {} for r in order}
    sens_sum: dict = {}
    dropped = 0
    persist = {}
    bbox = [180.0, 90.0, -180.0, -90.0]
    for (col, row), path in sorted(tile_files.items()):
        d = load_tile(path)
        if d is None:
            continue
        for b, p in zip(d["baselines"].tolist(), d["persist"].tolist()):
            persist[b] = p or None
        ids = rg.assign_regions(d["lon"], d["lat"], regions)
        ok = np.array([i in chosen for i in ids], dtype=bool)
        if "mp_ha" in d and d["mp_lon"].size:
            mids = rg.assign_regions(d["mp_lon"], d["mp_lat"], regions)
            for rid in {i for i in mids if i in chosen}:
                sel = mids == rid
                for y, ha in zip(d["mp_years"].tolist(), d["mp_ha"][:, sel].sum(axis=1).tolist()):
                    region_mapped[rid][y] = region_mapped[rid].get(y, 0.0) + ha
        if sensitivity:
            for k in d:
                if k.startswith("sens__"):
                    sens_sum[k] = sens_sum.get(k, 0.0) + float(d[k][ok].sum())
        dropped += int(np.sum(d["keep"] & ~ok))
        m = d["keep"] & ok
        if not m.any():
            continue
        ridx = np.array([lookup[i] for i in ids[m]], dtype=np.int16)
        part = {"lon": d["lon"][m].tolist(), "lat": d["lat"][m].tolist(), "area_ha": d["area_ha"][m].tolist(),
                "region": ridx.tolist(), "intervals": build_intervals(d, targets, m, latest)}
        name = tiling.tile_name(col, row)
        data = (json.dumps(part, separators=(",", ":")) + "\n").encode("utf-8")
        (tdir / f"{name}.json").write_bytes(data)
        cnt = np.bincount(ridx, minlength=len(order))
        touched = {order[i]: int(k) for i, k in enumerate(cnt) if k}
        cells_for_totals = {"intervals": part["intervals"]}
        for rid in touched:
            region_tiles[rid].append(name)
            sel = np.flatnonzero(ridx == lookup[rid])
            region_cells[rid] += int(sel.size)
            region_area[rid] += float(np.asarray(part["area_ha"])[sel].sum())
            region_parts[rid].append(tiling.totals(cells_for_totals, sel))
        tbox = tiling.cells_bbox_wgs84(d["x"][m], d["y"][m], to_ll)
        bbox = [min(bbox[0], tbox[0]), min(bbox[1], tbox[1]), max(bbox[2], tbox[2]), max(bbox[3], tbox[3])]
        tiles.append({"id": name, "col": col, "row": row, "file": f"{tiling.TILES_DIR}/{name}.json",
                      "bbox": tbox, "cells": int(m.sum()), "bytes": len(data), "regions": touched})
        stats.append({"id": name, "raw": len(data), "gz": len(gzip.compress(data, 9, mtime=0))})
        del d, part, data
    summary = [{"id": rid, "name": names.get(rid, rid), "cells": region_cells[rid],
                "area_ha": round(region_area[rid], 2), "tiles": region_tiles[rid],
                "totals": summaries.add_totals(region_parts[rid]),
                "mapped_km2": {str(y): round(v / 100.0, 1) for y, v in sorted(region_mapped[rid].items())}}
               for rid in order if region_cells[rid] or region_mapped[rid]]
    index = {
        "area_id": area_id, "contract_version": 3, "crs": "EPSG:3978", "tile_m": tile_km * 1000,
        "cell_size_m": agg.CELL_M, "cells": sum(t["cells"] for t in tiles), "regions": order,
        "region_summary": summary,
        # cells outside the selected regions are not written, so none are left unassigned
        "unassigned": {"cells": 0, "dropped_outside_regions": dropped},
        "tiles": tiles,
    }
    (out_area / tiling.INDEX_NAME).write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")
    return index, stats, sens_sum, persist, bbox


def sensitivity_from_sums(sums: dict, latest: int, baselines: list[int]):
    rows = []
    for pid, label, _ in rn.PRESETS:
        ivs = {}
        for b in baselines:
            ha = round(sums.get(f"sens__{pid}__{b}__conv", 0.0), 1)
            nha = round(sums.get(f"sens__{pid}__{b}__nat", 0.0), 1)
            ivs[f"{b}-{latest}"] = {"converted_ha": ha, "natural_ha": nha,
                                    "percent": round(100 * ha / nha, 2) if nha else 0.0}
        rows.append({"id": pid, "label": label, "is_default": pid == rn.DEFAULT_PRESET, "intervals": ivs})
    return rows


def write_outputs(out_dir: Path, area_id, name, tile_files, regions, selected, targets, latest, years, params,
                  tile_km, sensitivity):
    """Assemble tiles, meta.json, province summary and areas.json from cached tile results."""
    d = out_dir / area_id
    d.mkdir(parents=True, exist_ok=True)
    index, stats, sums, persist, bbox = assemble(d, area_id, tile_files, regions, selected, targets, latest, tile_km,
                                                 sensitivity)
    baselines = sorted(b for b in rn.BASELINES if b < latest)
    intervals = [{"from": b, "to": latest, "years": latest - b, **({"note": CAVEAT_2011} if b == 2011 else {})}
                 for b in baselines]
    meta = {
        "area_id": area_id, "name": name, "bbox": bbox, "cell_size_m": agg.CELL_M,
        "snapshots": [*rn.BASELINES, latest], "latest": latest, "natural_classes": cl.NATURAL_CLASSES,
        "intervals": intervals, "targets": targets, "contract_version": 3, "tiled": True, "tile_km": tile_km,
        "regions": sorted(selected),
        "method": rn.describe_method(latest, params, {b: p for b, p in persist.items() if p}, targets),
        "source": rn.SOURCE, "generated": datetime.date.today().isoformat(),
        "caveats": rn.build_caveats(targets) + [CAVEAT_2011],
        "target_caveats": rn.build_target_caveats(targets),
    }
    if sensitivity:
        meta["sensitivity"] = rn.sensitivity_meta(sensitivity_from_sums(sums, latest, baselines))
    (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    summaries.write_province_summary(d, regions)
    areas_path = out_dir / "areas.json"
    areas = json.loads(areas_path.read_text()) if areas_path.exists() else []
    areas = [a for a in areas if a["id"] != area_id] + [{"id": area_id, "name": name, "bbox": bbox}]
    areas_path.write_text(json.dumps(sorted(areas, key=lambda a: a["id"]), indent=2) + "\n", encoding="utf-8")
    s = tiling.summarise_stats(stats)
    log(f"wrote {d}: {s['tiles']} tiles, {index['cells']} cells, raw median {s['raw']['median'] / 1e3:.0f} KB "
        f"max {s['raw']['max'] / 1e3:.0f} KB, gzip total {s['gz']['total'] / 1e6:.2f} MB")
    return meta, index


# ---------------------------------------------------------------- the run

def run_regions(out_dir: Path, selected: list[str] | None, params, latest=None, targets=None, tile_km=tiling.TILE_KM,
                sensitivity=False, workers=2, drop_rasters=False, check_legend=True, cache_dir: Path | None = None,
                area_id=AREA_ID, name=AREA_NAME, dry_run=False, limit=None):
    regions = rg.load_regions()
    ids = selected or sorted(region_features(regions))
    per_region = tiles_for_regions(regions, ids, tile_km)
    tiles = all_tiles(per_region)
    if limit:
        tiles = tiles[:limit]
    targets = [t for t in cl.TARGETS if t in (targets or cl.TARGETS)]
    if params.pasture_is_crop:
        targets = [t for t in targets if t != "pasture"]
    avail = fx.service_years()
    latest = latest or max(avail)
    support = [latest - 1] if (latest - 1) in avail and (latest - 1) not in rn.BASELINES else []
    years = sorted(set(rn.BASELINES + [latest] + support))
    rows = cl.load_classes()
    key = cache_key(years, latest, params, targets, tile_km, sensitivity, rows)
    if cache_dir:
        fx.CACHE = Path(cache_dir)
    results = fx.CACHE / RESULTS_DIR / key
    files = {t: results / f"{t[0]}_{t[1]}.npz" for t in tiles}
    todo = [t for t in tiles if not files[t].exists()]
    log(f"{len(ids)} regions, {len(tiles)} tiles of {tile_km} km, {len(tiles) - len(todo)} cached, {len(todo)} to run; "
        f"years {years}, latest {latest}, results in {results}")
    if dry_run:
        return None

    group_lut, natural_lut = cl.build_luts(rows)
    known = {r["code"] for r in rows}
    if check_legend:
        for y in years:
            problems = cl.check_legend_labels(fx.service_legend_labels(y), rows)
            if problems:
                log(f"WARNING legend check {y}: {problems}")

    def readers(year, raster):
        return read_stack_year(year, raster, known, group_lut, natural_lut)

    def prefetch(t):
        raster = tile_window(*t, tile_km)[0]
        return [fx.fetch_year(y, raster) for y in years]

    t_start = time.time()
    done = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        pending = {}
        it = iter(todo)

        def submit_next():
            t = next(it, None)
            if t is not None:
                pending[t] = pool.submit(prefetch, t)

        for _ in range(max(1, workers) + 1):
            submit_next()
        for t in todo:
            pending.pop(t).result()  # raises on a failed download; completed downloads stay cached
            submit_next()
            t0 = time.time()
            data = compute_tile(*t, readers, years, latest, params, targets, tile_km, sensitivity)
            save_tile(files[t], data)
            done += 1
            if drop_rasters:
                raster = tile_window(*t, tile_km)[0]
                for y in years:
                    fx.tile_path(y, raster).unlink(missing_ok=True)
            n = 0 if data is None else len(data["lon"])
            elapsed = time.time() - t_start
            log(f"tile {t[0]}_{t[1]}: {n} cells, {time.time() - t0:.0f} s compute; {done}/{len(todo)} done, "
                f"{elapsed / 60:.1f} min elapsed, about {elapsed / done * (len(todo) - done) / 60:.0f} min left")
    return write_outputs(out_dir, area_id, name, files, regions, ids, targets, latest, years, params, tile_km,
                         sensitivity)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--regions", default=None, help="comma separated region ids (default: all 14)")
    ap.add_argument("--list", action="store_true", help="list regions with their tile counts and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the plan (tiles, cached or not) and exit")
    ap.add_argument("--out", type=Path, default=rn.DEFAULT_OUT)
    ap.add_argument("--area-id", default=AREA_ID)
    ap.add_argument("--cache-dir", type=Path, default=None, help="rasters and tile results (default pipeline/cache)")
    ap.add_argument("--tiled", type=int, default=tiling.TILE_KM, metavar="KM", help="tile size in km (default %(default)s)")
    ap.add_argument("--workers", type=int, default=2, help="parallel tile downloads (default %(default)s)")
    ap.add_argument("--drop-rasters", action="store_true",
                    help="delete a tile's downloaded rasters once its result is cached (saves about 58 MB per tile)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N tiles (testing)")
    ap.add_argument("--latest", type=int, default=None)
    ap.add_argument("--sensitivity", action="store_true",
                    help="also write the filter sensitivity block (about 8 extra crop passes per tile)")
    ap.add_argument("--no-legend-check", action="store_true")
    ap.add_argument("--targets", default=",".join(cl.TARGETS))
    ap.add_argument("--min-patch-ha", type=float, default=cv.FilterParams.min_patch_ha)
    ap.add_argument("--no-persistence", action="store_true")
    ap.add_argument("--majority", action="store_true")
    ap.add_argument("--keep-prior-crop", action="store_true")
    ap.add_argument("--keep-prior-pasture-urban", action="store_true")
    ap.add_argument("--pasture-is-crop", action="store_true")
    a = ap.parse_args(argv)
    regions = rg.load_regions()
    selected = [s.strip() for s in a.regions.split(",") if s.strip()] if a.regions else None
    try:
        per_region = tiles_for_regions(regions, selected, a.tiled)
    except ValueError as e:
        ap.error(str(e))
    if a.list:
        for rid, ts in per_region.items():
            print(f"{rid}: {len(ts)} tiles")
        print(f"total: {len(all_tiles(per_region))} distinct tiles")
        return
    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in cl.TARGETS]
    if bad:
        ap.error(f"unknown targets {bad}; choose from {cl.TARGETS}")
    params = cv.FilterParams(
        persistence=not a.no_persistence, min_patch_ha=a.min_patch_ha, majority=a.majority,
        pasture_is_crop=a.pasture_is_crop, exclude_prior_crop=not a.keep_prior_crop,
        exclude_prior_pasture_urban=not a.keep_prior_pasture_urban,
    )
    run_regions(a.out, selected, params, a.latest, targets, a.tiled, a.sensitivity, a.workers, a.drop_rasters,
                not a.no_legend_check, a.cache_dir, a.area_id, AREA_NAME, a.dry_run, a.limit)


if __name__ == "__main__":
    main()
