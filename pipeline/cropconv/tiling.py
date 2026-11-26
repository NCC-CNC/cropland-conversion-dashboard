"""Partition an area's 1 km cells into fixed tiles for loading (contract version 3).

A tile is a square block of the EPSG:3978 plane whose edges are multiples of the
tile size from the projection origin, so tiles line up across areas and runs. A
cell belongs to the tile that contains its centre, hence to exactly one tile.
Each tile file has the cells.json columnar shape plus a small `region` column
(an index into `regions` of index.json, -1 for none). See
docs/decisions/0004-tiled-cell-data.md and docs/design/05_regional_partitioning.md.
"""
from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

import numpy as np
from pyproj import Transformer

TILE_KM = 100
TILES_DIR = "tiles"
INDEX_NAME = "index.json"
NO_REGION = -1


def tile_coords(x, y, tile_m: int):
    """Integer (col, row) of the tile containing each point (EPSG:3978 metres).

    Row increases northward, like y. An edge belongs to the tile on its north east side.
    """
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    return np.floor(x / tile_m).astype(np.int64), np.floor(y / tile_m).astype(np.int64)


def tile_name(col: int, row: int) -> str:
    return f"{int(col)}_{int(row)}"


def take(node, idx: np.ndarray):
    """Select the entries idx from every array in a cells.json style nested structure."""
    if isinstance(node, dict):
        return {k: take(v, idx) for k, v in node.items()}
    return np.asarray(node)[idx].tolist()


def cells_bbox_wgs84(x, y, to_ll: Transformer, cell_m: int = 1000):
    """WGS84 [w, s, e, n] around cells with centres (x, y) in EPSG:3978 (cell edges, densified)."""
    h = cell_m / 2
    x0, x1 = float(np.min(x)) - h, float(np.max(x)) + h
    y0, y1 = float(np.min(y)) - h, float(np.max(y)) + h
    t = np.linspace(0.0, 1.0, 11)
    ex = np.concatenate([x0 + (x1 - x0) * t, np.full(11, x1), x0 + (x1 - x0) * t, np.full(11, x0)])
    ey = np.concatenate([np.full(11, y0), y0 + (y1 - y0) * t, np.full(11, y1), y0 + (y1 - y0) * t])
    lon, lat = to_ll.transform(ex, ey)
    pad = 5e-5  # rounding to 4 decimals must never shrink the box
    return [round(float(np.min(lon)) - pad, 4), round(float(np.min(lat)) - pad, 4),
            round(float(np.max(lon)) + pad, 4), round(float(np.max(lat)) + pad, 4)]


def region_table(region_ids, regions: dict | None):
    """(sorted region ids, int16 index per cell with -1 for none).

    With regions (the GeoJSON of regions.json) the table lists every region, so indices
    are stable between areas; without it, only the ids that occur.
    """
    ids = list(region_ids)
    if regions is not None:
        order = sorted(f["properties"]["id"] for f in regions["features"])
    else:
        order = sorted({r for r in ids if r is not None})
    lookup = {r: i for i, r in enumerate(order)}
    idx = np.array([lookup[r] if r is not None else NO_REGION for r in ids], dtype=np.int16)
    return order, idx


def totals(cells: dict, idx: np.ndarray) -> dict:
    """Per interval sums over the cells idx, in the shape of an interval with scalars for arrays."""
    out = {}
    for key, iv in cells["intervals"].items():
        out[key] = {
            "natural_ha": {c: round(float(np.sum(np.asarray(a)[idx])), 2) for c, a in iv["natural_ha"].items()},
            "converted_ha": {
                t: {c: round(float(np.sum(np.asarray(a)[idx])), 2) for c, a in by.items()}
                for t, by in iv["converted_ha"].items()
            },
        }
    return out


def write_tiles(area_dir: Path, cells: dict, x, y, region_ids, regions: dict | None, *,
                area_id: str, tile_km: int = TILE_KM, cell_m: int = 1000, names: dict | None = None):
    """Write tiles/<col>_<row>.json and index.json for one area; returns (index, per tile stats).

    cells is the single file cells.json dict; x, y are the cell centres in EPSG:3978 (same
    order) and region_ids the region id (or None) per cell. Old tiles are removed first.
    Stats are dicts with id, raw and gzipped byte sizes.
    """
    tile_m = tile_km * 1000
    n = len(cells["lon"])
    if not (len(x) == len(y) == len(region_ids) == n):
        raise ValueError("x, y, region_ids and cells must have equal length")
    area_dir = Path(area_dir)
    tdir = area_dir / TILES_DIR
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)

    x, y = np.asarray(x, dtype="float64"), np.asarray(y, dtype="float64")
    order, ridx = region_table(region_ids, regions)
    col, row = tile_coords(x, y, tile_m)
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)

    key = np.lexsort((row, col))
    breaks = np.flatnonzero((np.diff(col[key]) != 0) | (np.diff(row[key]) != 0)) + 1
    tiles, stats = [], []
    region_tiles = {r: [] for r in order}
    for grp in (np.split(key, breaks) if n else []):
        grp = np.sort(grp)  # keep the original cell order inside a tile
        c, r = int(col[grp[0]]), int(row[grp[0]])
        name = tile_name(c, r)
        part = take({k: cells[k] for k in ("lon", "lat", "area_ha")}, grp)
        part["region"] = ridx[grp].tolist()
        part["intervals"] = take(cells["intervals"], grp)
        data = (json.dumps(part, separators=(",", ":")) + "\n").encode("utf-8")
        (tdir / f"{name}.json").write_bytes(data)
        counts = np.bincount(ridx[grp][ridx[grp] >= 0], minlength=len(order))
        touched = {order[i]: int(k) for i, k in enumerate(counts) if k}
        for rid in touched:
            region_tiles[rid].append(name)
        tiles.append({
            "id": name, "col": c, "row": r,
            "file": f"{TILES_DIR}/{name}.json",
            "bbox": cells_bbox_wgs84(x[grp], y[grp], to_ll, cell_m),
            "cells": int(grp.size),
            "bytes": len(data),
            "regions": touched,
        })
        stats.append({"id": name, "raw": len(data), "gz": len(gzip.compress(data, 9, mtime=0))})

    area_ha = np.asarray(cells["area_ha"])
    summary = []
    for i, rid in enumerate(order):
        sel = np.flatnonzero(ridx == i)
        if sel.size:
            summary.append({
                "id": rid, "name": (names or {}).get(rid, rid), "cells": int(sel.size), "area_ha": round(float(area_ha[sel].sum()), 2),
                "tiles": region_tiles[rid], "totals": totals(cells, sel),
            })
    none = np.flatnonzero(ridx == NO_REGION)
    unassigned = {"cells": int(none.size)}
    if none.size:
        unassigned.update(area_ha=round(float(area_ha[none].sum()), 2), totals=totals(cells, none))
    index = {
        "area_id": area_id,
        "contract_version": 3,
        "crs": "EPSG:3978",
        "tile_m": tile_m,
        "cell_size_m": cell_m,
        "cells": n,
        "regions": order,
        "region_summary": summary,
        "unassigned": unassigned,
        "tiles": tiles,
    }
    (area_dir / INDEX_NAME).write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")
    return index, stats


def summarise_stats(stats: list[dict]) -> dict:
    """min, median, max and total of raw and gzipped tile sizes in bytes."""
    out = {"tiles": len(stats)}
    for k in ("raw", "gz"):
        v = np.array([s[k] for s in stats]) if stats else np.zeros(1)
        out[k] = {"min": int(v.min()), "median": int(np.median(v)), "max": int(v.max()), "total": int(v.sum())}
    return out


def write_area(area_dir: Path, cells: dict, x, y, area_id: str, tile_km: int = TILE_KM):
    """Tag each cell with its region and write the tiled form of an area; logs a size summary."""
    import sys

    from . import regions as rg

    reg = rg.load_regions()
    ids = rg.assign_regions(cells["lon"], cells["lat"], reg)
    names = {f["properties"]["id"]: f["properties"]["name"] for f in reg["features"]}
    index, stats = write_tiles(area_dir, cells, x, y, ids, reg, area_id=area_id, tile_km=tile_km, names=names)
    s = summarise_stats(stats)
    print(f"wrote {area_dir}: {s['tiles']} tiles, {index['unassigned']['cells']} cells without a region; "
          f"raw median {s['raw']['median'] / 1e3:.0f} KB max {s['raw']['max'] / 1e3:.0f} KB, "
          f"gzip median {s['gz']['median'] / 1e3:.0f} KB total {s['gz']['total'] / 1e6:.2f} MB", file=sys.stderr)
    return index, stats
