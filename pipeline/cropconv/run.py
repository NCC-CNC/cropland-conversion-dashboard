"""Command line entry point.

    python -m cropconv.run                # fetch (cached), compute, write JSON
    python -m cropconv.run --sensitivity  # also print the filter sensitivity table
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from pyproj import Proj, Transformer

from . import aggregate as agg
from . import classes as cl
from . import convert as cv
from . import fetch as fx

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "web" / "public" / "data"
SOURCE = (
    "AAFC Annual Crop Inventory, OGL-Canada-2.0, https://agriculture.canada.ca/atlas/annual-crop-inventory "
    "(ImageServer: https://agriculture.canada.ca/imagery-images/rest/services/annual_crop_inventory)"
)

BASELINES = [2011, 2016, 2021]
GRID_KM = 40
PX = fx.PIXEL_M
N_PX = (GRID_KM * 1000) // PX  # 1333 pixels, 39 990 m, inside a 40 km grid

AREAS = {
    "ab-parkland-stettler": {
        "name": "Alberta Parkland test window (Stettler area)",
        "center": (-112.7, 52.3),  # lon, lat
    },
    "sk-mb-estevan-melville": {
        "name": "SK/MB test area (Estevan, Melita, Russell, Melville)",
        "bbox_corners": True,  # rectangle around the four towns, see export_shapes
    },
}


def window_bbox(bbox):
    """Grid and raster for a rectangle (EPSG:3978, a multiple of the pixel size wide).

    The grid starts at the raster's top left corner and is rounded up to whole
    1 km cells, so edge cells can be partial; their area comes from pixel counts.
    """
    x0, y0, x1, y1 = bbox
    n_cols = -(-(x1 - x0) // agg.CELL_M)
    n_rows = -(-(y1 - y0) // agg.CELL_M)
    grid = (x0, y1 - n_rows * agg.CELL_M, x0 + n_cols * agg.CELL_M, y1)
    return grid, tuple(bbox)


def window(center):
    """40 km grid aligned to 1 km in EPSG:3978, and the pixel raster bbox inside it."""
    x, y = Transformer.from_crs(4326, 3978, always_xy=True).transform(*center)
    x0 = int(np.floor(x / 1000) * 1000) - GRID_KM * 500
    y0 = int(np.floor(y / 1000) * 1000) - GRID_KM * 500
    grid = (x0, y0, x0 + GRID_KM * 1000, y0 + GRID_KM * 1000)
    raster = (x0, y0 + GRID_KM * 1000 - N_PX * PX, x0 + N_PX * PX, y0 + GRID_KM * 1000)
    return grid, raster


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_stack(raster_bbox, years, rows):
    """Fetch and read all years; returns {year: group array} and {year: natural idx array}."""
    group_lut, natural_lut = cl.build_luts(rows)
    known = {r["code"] for r in rows}
    groups, naturals, legend_log = {}, {}, {}
    shape = None
    for y in years:
        problems = cl.check_legend_labels(fx.service_legend_labels(y), rows)
        legend_log[y] = problems or "ok"
        if problems:
            log(f"WARNING legend check {y}: {problems}")
        path = fx.fetch_year(y, raster_bbox)
        arr, transform = fx.read_year(path)
        if shape is None:
            shape = arr.shape
        if arr.shape != shape:
            raise ValueError(f"{y}: shape {arr.shape} differs from {shape}")
        if abs(transform.a - PX) > 1e-6 or abs(transform.e + PX) > 1e-6:
            raise ValueError(f"{y}: pixel size is {transform.a}, expected {PX}")
        fx.assert_codes_unmodified(arr, known)
        valid = float((arr != 0).mean())
        cloud = float((arr == 10).mean())
        log(f"{y}: valid {valid:.3f} cloud {cloud:.4f} codes {len(np.unique(arr))}")
        if valid < 0.9:
            raise ValueError(f"{y}: only {valid:.0%} of the window has data")
        groups[y] = group_lut[arr]
        naturals[y] = natural_lut[arr]
    return groups, naturals, legend_log


def interval_masks(groups, naturals, latest, params, pixel_area_m2, available):
    """{baseline: (natural idx, converted mask)} for each baseline."""
    out = {}
    for b in BASELINES:
        if b >= latest:
            continue
        py = cv.persistence_year(b, latest, available)
        persist = groups[py] if py is not None else None
        nat = cv.clean_baseline(naturals[b], [groups[y] for y in available if y < b], params)
        conv = cv.conversion_mask(nat > 0, groups[latest], persist, params, pixel_area_m2)
        out[b] = (nat, conv, py)
    return out


def describe_method(latest, params, persist_years):
    persist = (
        "a cell must also be crop in the most recent earlier snapshot between the baseline and the latest year "
        f"({', '.join(str(p) for p in sorted(set(persist_years.values())))})"
        if params.persistence else "no persistence check was applied"
    )
    patch = (
        f"isolated patches smaller than {params.min_patch_ha:g} ha (connected pixels, 30 m) are removed"
        if params.min_patch_ha > 0 else "no minimum patch size was applied"
    )
    prior = (
        "natural cover in a baseline year excludes cells already mapped as crop in an earlier snapshot "
        "(likely fallow, forage rotation or mapping error; the 2011 baseline has no earlier snapshot)"
        if params.exclude_prior_crop else "cells that were crop in an earlier snapshot are not excluded from the baseline"
    )
    maj = "a 3x3 majority filter is applied first" if params.majority else "no majority filter is applied"
    pasture = (
        "Pasture and forage (ACI 122) counts as crop."
        if params.pasture_is_crop else
        "Pasture and forage (ACI 122) is not counted as crop, so conversion to tame pasture or hay is not detected."
    )
    return (
        "AAFC Annual Crop Inventory classes are grouped into natural (forest 200 to 230, grassland 110, wetland 80, "
        "shrubland 50), crop (agriculture and annual or specialty crops, codes 120 to 199 except 122) and other "
        "(water, urban, barren, cloud, burnt area, pasture and forage). "
        f"A pixel counts as converted when it is natural in the baseline year and crop in {latest}; "
        f"to reduce classification noise {persist}; {patch}; {maj}; and {prior}. {pasture} "
        "Converted pixels are summed by baseline natural class on a 1 km grid. "
        "Percent converted is converted divided by natural cover in the baseline year."
    )


CAVEATS = [
    "Crop is mapped with reported accuracy of 85 to 90 percent or more by AAFC, but natural classes such as grassland, wetland and shrubland are mapped less accurately. Small differences are within map error.",
    "The Annual Crop Inventory classification method and ground data changed over the series, so some change between years is a mapping artefact rather than a land change. Early years (2011) are the least reliable.",
    "Native grassland cannot be separated from tame grass and pasture. Conversion to pasture or hay is not counted as crop, and some grassland counted here may be tame.",
    "Conversion is detected from natural to crop only. Natural cover lost to urban, water or other uses is not shown, and cropland returning to grass is not subtracted.",
    "A noise filter (persistence and minimum patch size) removes isolated single year flips, but it also removes real small conversions, so hectares are conservative for small fields and linear clearings.",
    "Results are summed over 1 km grid cells whose centre lies inside the drawn area. The edge of a polygon is therefore approximate, and results for areas smaller than a few square kilometres are very uncertain.",
    "This is a screening aid for planning and grant context, not a parcel level or legal grade result, and it does not say why land was converted.",
]


def run(area_id, out_dir, params, latest=None, sensitivity=False):
    cfg = AREAS[area_id]
    rows = cl.load_classes()
    if cfg.get("bbox_corners"):
        from .export_shapes import test_area_bbox
        grid, raster = window_bbox(test_area_bbox())
    else:
        grid, raster = window(cfg["center"])
    log(f"window grid {grid} raster {raster}")

    avail = fx.service_years()
    latest = latest or max(avail)
    support = [latest - 1] if (latest - 1) in avail and (latest - 1) not in BASELINES else []
    years = sorted(set(BASELINES + [latest] + support))
    log(f"service years {avail[0]}..{avail[-1]}; using {years}, latest {latest}")
    groups, naturals, legend_log = load_stack(raster, years, rows)

    # areal scale of the projection varies slowly, take it per cell
    n_cols = (grid[2] - grid[0]) // agg.CELL_M
    n_rows = (grid[3] - grid[1]) // agg.CELL_M
    n_cells = n_cols * n_rows
    xs = grid[0] + (np.arange(n_cols) + 0.5) * agg.CELL_M
    ys = grid[3] - (np.arange(n_rows) + 0.5) * agg.CELL_M
    gx, gy = np.meshgrid(xs, ys)  # row-major: row = from top
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)
    lon, lat = to_ll.transform(gx.ravel(), gy.ravel())
    scale = np.asarray(Proj("EPSG:3978").get_factors(lon, lat).areal_scale)
    pixel_m2 = PX * PX / scale  # ground area per pixel for each cell
    pixel_ha = pixel_m2 / 1e4

    first = groups[years[0]]
    cells = agg.pixel_cells(first.shape, raster[0], raster[3], grid[3], PX, n_cols, n_rows)
    area_ha = np.bincount(cells[cells >= 0], minlength=n_cells) * pixel_ha
    pm2 = float(np.mean(pixel_m2))

    def compute(p):
        return interval_masks(groups, naturals, latest, p, pm2, years)

    res = compute(params)
    nat_counts = {b: agg.natural_counts(res[b][0], cells, n_cells) for b in res}
    conv_counts = {b: agg.converted_counts(res[b][0], res[b][1], cells, n_cells) for b in res}

    keep = np.zeros(n_cells, dtype=bool)
    for b in res:
        for c in cl.NATURAL_CLASSES:
            keep |= nat_counts[b][c] > 0
    log(f"cells kept {keep.sum()} of {n_cells}")

    out = {
        "lon": np.round(np.asarray(lon)[keep], 5).tolist(),
        "lat": np.round(np.asarray(lat)[keep], 5).tolist(),
        "area_ha": np.round(area_ha[keep], 2).tolist(),
        "intervals": {},
    }
    intervals_meta, persist_years = [], {}
    for b in sorted(res):
        key = f"{b}-{latest}"
        persist_years[b] = res[b][2]
        out["intervals"][key] = {
            "natural_ha": {c: agg.to_ha(nat_counts[b][c], pixel_ha, keep) for c in cl.NATURAL_CLASSES},
            "converted_ha": {c: agg.to_ha(conv_counts[b][c], pixel_ha, keep) for c in cl.NATURAL_CLASSES},
        }
        intervals_meta.append({"from": b, "to": latest, "years": latest - b})

    # bbox of the full grid in WGS84
    corners = [(grid[0], grid[1]), (grid[2], grid[1]), (grid[2], grid[3]), (grid[0], grid[3])]
    cl_lon, cl_lat = to_ll.transform([c[0] for c in corners], [c[1] for c in corners])
    bbox = [round(min(cl_lon), 4), round(min(cl_lat), 4), round(max(cl_lon), 4), round(max(cl_lat), 4)]

    meta = {
        "area_id": area_id,
        "name": cfg["name"],
        "bbox": bbox,
        "cell_size_m": agg.CELL_M,
        "snapshots": [*BASELINES, latest],
        "latest": latest,
        "natural_classes": cl.NATURAL_CLASSES,
        "intervals": intervals_meta,
        "method": describe_method(latest, params, {b: p for b, p in persist_years.items() if p}),
        "source": SOURCE,
        "generated": datetime.date.today().isoformat(),
        "caveats": CAVEATS,
    }

    d = out_dir / area_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (d / "cells.json").write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    areas_path = out_dir / "areas.json"
    areas = json.loads(areas_path.read_text()) if areas_path.exists() else []
    areas = [a for a in areas if a["id"] != area_id] + [{"id": area_id, "name": cfg["name"], "bbox": bbox}]
    areas_path.write_text(json.dumps(sorted(areas, key=lambda a: a["id"]), indent=2) + "\n", encoding="utf-8")
    log(f"wrote {d} (cells.json {(d / 'cells.json').stat().st_size / 1e6:.2f} MB)")

    summarise(out, intervals_meta, area_ha[keep].sum(), legend_log)
    if sensitivity:
        sensitivity_table(groups, naturals, latest, years, pm2, params, cells, pixel_ha, n_cells, keep)
    return meta, out


def summarise(out, intervals_meta, area_total, legend_log):
    print(f"\nLegend checks: {legend_log}")
    print(f"Kept cells: {len(out['lon'])}, kept area {area_total:,.0f} ha")
    for iv in intervals_meta:
        key = f"{iv['from']}-{iv['to']}"
        n, c = out["intervals"][key]["natural_ha"], out["intervals"][key]["converted_ha"]
        print(f"\nInterval {key} ({iv['years']} years)")
        tn = tc = 0.0
        for k in cl.NATURAL_CLASSES:
            sn, sc = sum(n[k]), sum(c[k])
            tn += sn
            tc += sc
            print(f"  {k:10s} natural {sn:9.1f} ha  converted {sc:8.1f} ha  {100 * sc / sn if sn else 0:5.2f}%")
        print(f"  {'TOTAL':10s} natural {tn:9.1f} ha  converted {tc:8.1f} ha  {100 * tc / tn:5.2f}%  "
              f"({tc / iv['years']:.1f} ha/yr)")


PRESETS = [
    ("1. No filter at all", dict(persistence=False, min_patch_ha=0.0, majority=False, exclude_prior_crop=False)),
    ("2. Persistence only", dict(persistence=True, min_patch_ha=0.0, majority=False, exclude_prior_crop=False)),
    ("3. Persistence + 0.5 ha patches", dict(persistence=True, min_patch_ha=0.5, majority=False, exclude_prior_crop=False)),
    ("4. Default: 3 + exclude prior crop", dict(persistence=True, min_patch_ha=0.5, majority=False, exclude_prior_crop=True)),
    ("5. As default, 2 ha patches", dict(min_patch_ha=2.0)),
    ("6. As default, plus 3x3 majority filter", dict(majority=True)),
    ("7. As default, pasture/forage counted as crop", dict(pasture_is_crop=True)),
]


def sensitivity_table(groups, naturals, latest, years, pm2, base_params, cells, pixel_ha, n_cells, keep):
    print("\nSensitivity: converted ha over the whole window (percent of that setting's baseline natural ha)")
    bases = [b for b in BASELINES if b < latest]
    head = " | ".join(f"{b} to {latest}" for b in bases)
    print(f"| Setting | {head} |")
    print("|---|" + "---|" * len(bases))
    nat_line = []
    for name, kw in PRESETS:
        p = replace(base_params, **kw)
        res = interval_masks(groups, naturals, latest, p, pm2, years)
        vals = []
        for b in bases:
            nat, conv, _ = res[b]
            ha = float(conv.sum() * pm2 / 1e4)
            nha = float((nat > 0).sum() * pm2 / 1e4)
            vals.append(f"{ha:,.0f} ({100 * ha / nha:.1f}%)")
            if name.startswith("4."):
                nat_line.append(f"{b}: {nha:,.0f}")
        print(f"| {name} | " + " | ".join(vals) + " |")
    print("Baseline natural ha under the default: " + ", ".join(nat_line))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", default="ab-parkland-stettler", choices=sorted(AREAS))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--latest", type=int, default=None, help="latest year (default: newest on the service)")
    ap.add_argument("--min-patch-ha", type=float, default=cv.FilterParams.min_patch_ha)
    ap.add_argument("--no-persistence", action="store_true")
    ap.add_argument("--majority", action="store_true")
    ap.add_argument("--keep-prior-crop", action="store_true",
                    help="do not drop baseline natural cells that were crop in an earlier snapshot")
    ap.add_argument("--pasture-is-crop", action="store_true")
    ap.add_argument("--sensitivity", action="store_true")
    a = ap.parse_args(argv)
    params = cv.FilterParams(
        persistence=not a.no_persistence, min_patch_ha=a.min_patch_ha,
        majority=a.majority, pasture_is_crop=a.pasture_is_crop,
        exclude_prior_crop=not a.keep_prior_crop,
    )
    run(a.area, a.out, params, a.latest, a.sensitivity)


if __name__ == "__main__":
    main()
