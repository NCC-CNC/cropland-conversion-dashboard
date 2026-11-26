"""Write the 30 m converted-pixel layer as a PMTiles archive (ADR 0003).

    python -m cropconv.export_tiles --area sk-mb-estevan-melville

Uses the same fetch cache, class groups, conversion masks and default filters
as `cropconv.run`, so the pixels match the definition behind the 1 km totals.
Output is pipeline/exports/<area_id>.pmtiles (gitignored): vector tiles in
EPSG:3857, PMTiles v3, gzip compressed MVT, one layer called "converted".

Each feature is one 4-connected patch of converted pixels for one
(interval, target, natural class), with properties:

    interval  baseline year (number); the interval runs from it to the latest year
    target    crop, pasture, urban or barren
    class     baseline natural class: forest, grassland, wetland, shrubland

Geometry is simplified per zoom, and patches smaller than about half a screen
pixel are dropped below the maximum zoom. The maximum zoom keeps the exact
30 m pixel outlines. Pure Python (shapely, mapbox-vector-tile, pmtiles).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from affine import Affine
from mapbox_vector_tile import encode as mvt_encode
from mapbox_vector_tile.encoder import on_invalid_geometry_make_valid
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from pyproj import Proj, Transformer
from rasterio.features import shapes

from . import aggregate as agg
from . import classes as cl
from . import convert as cv
from . import fetch as fx
from . import run as rn

EXPORTS = Path(__file__).resolve().parent.parent / "exports"
LAYER = "converted"
EXTENT = 4096
BUFFER = 64  # tile buffer in extent units
WORLD = 2 * math.pi * 6378137.0  # Web Mercator width in metres
MIN_ZOOM, MAX_ZOOM = 11, 14


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def tile_size_m(z: int) -> float:
    return WORLD / (1 << z)


def mean_pixel_m2(grid) -> float:
    """Mean ground area of a 30 m pixel over the grid, computed as run.run does."""
    n_cols = (grid[2] - grid[0]) // agg.CELL_M
    n_rows = (grid[3] - grid[1]) // agg.CELL_M
    xs = grid[0] + (np.arange(n_cols) + 0.5) * agg.CELL_M
    ys = grid[3] - (np.arange(n_rows) + 0.5) * agg.CELL_M
    gx, gy = np.meshgrid(xs, ys)
    lon, lat = Transformer.from_crs(3978, 4326, always_xy=True).transform(gx.ravel(), gy.ravel())
    scale = np.asarray(Proj("EPSG:3978").get_factors(lon, lat).areal_scale)
    return float(np.mean(fx.PIXEL_M * fx.PIXEL_M / scale))


def vectorize(label: np.ndarray, transform: Affine, classes: list[str]):
    """4-connected patches of a label raster (0 = none, k = classes[k-1]).

    Returns (geometries in the raster CRS, class name per geometry).
    """
    geoms, names = [], []
    for geo, val in shapes(label, mask=label > 0, transform=transform, connectivity=4):
        geoms.append(shapely.from_geojson(json.dumps(geo)))
        names.append(classes[int(val) - 1])
    return geoms, names


def to_mercator(geoms, src_crs: int = 3978) -> np.ndarray:
    tr = Transformer.from_crs(src_crs, 3857, always_xy=True)
    arr = np.empty(len(geoms), dtype=object)
    arr[:] = geoms
    return shapely.transform(arr, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))


class FeatureSet:
    """All patches in EPSG:3857 with their properties."""

    def __init__(self):
        self.geoms: list = []
        self.props: list[dict] = []

    def add(self, geoms, names, interval: int, target: str):
        self.geoms.extend(geoms)
        self.props.extend({"interval": interval, "target": target, "class": n} for n in names)

    def __len__(self):
        return len(self.geoms)


def zoom_geoms(geoms: np.ndarray, z: int, max_zoom: int):
    """Simplify and filter for one zoom; returns (geoms, kept indices)."""
    if z >= max_zoom:
        return geoms, np.arange(len(geoms))
    res = tile_size_m(z) / 256.0  # metres per 256 px screen pixel
    simple = shapely.simplify(geoms, res * 0.5)  # topology preserving
    keep = np.flatnonzero(shapely.area(simple) >= 0.5 * res * res)
    return simple[keep], keep


def encode_tile(z: int, x: int, y: int, geoms, props) -> bytes:
    """Clip (with buffer) and encode one tile; b'' when nothing remains."""
    ts = tile_size_m(z)
    minx, maxx = -WORLD / 2 + x * ts, -WORLD / 2 + (x + 1) * ts
    maxy, miny = WORLD / 2 - y * ts, WORLD / 2 - (y + 1) * ts
    b = ts / EXTENT * BUFFER
    arr = np.empty(len(geoms), dtype=object)
    arr[:] = list(geoms)
    clipped = shapely.clip_by_rect(arr, minx - b, miny - b, maxx + b, maxy + b)
    feats = []
    for g, p in zip(clipped, props):
        if g is None or g.is_empty:
            continue
        parts = [q for q in shapely.get_parts(g) if q.geom_type == "Polygon" and not q.is_empty]
        if not parts:
            continue
        geom = parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)
        feats.append({"geometry": geom, "properties": p})
    if not feats:
        return b""
    data = mvt_encode(
        [{"name": LAYER, "features": feats}],
        default_options={
            "quantize_bounds": (minx, miny, maxx, maxy), "extents": EXTENT,
            "on_invalid_geometry": on_invalid_geometry_make_valid,
        },
    )
    return gzip.compress(data, compresslevel=9, mtime=0)


def build_tiles(fs: FeatureSet, min_zoom: int, max_zoom: int):
    """Yield (z, x, y, bytes) in tile id order."""
    base = np.empty(len(fs), dtype=object)
    base[:] = fs.geoms
    for z in range(min_zoom, max_zoom + 1):
        t0 = time.time()
        geoms, keep = zoom_geoms(base, z, max_zoom)
        ts = tile_size_m(z)
        n = 1 << z
        b = shapely.bounds(geoms)
        buckets = defaultdict(list)
        x0 = np.clip(np.floor((b[:, 0] + WORLD / 2) / ts).astype(int), 0, n - 1)
        x1 = np.clip(np.floor((b[:, 2] + WORLD / 2) / ts).astype(int), 0, n - 1)
        y0 = np.clip(np.floor((WORLD / 2 - b[:, 3]) / ts).astype(int), 0, n - 1)
        y1 = np.clip(np.floor((WORLD / 2 - b[:, 1]) / ts).astype(int), 0, n - 1)
        for i in range(len(geoms)):
            for tx in range(x0[i], x1[i] + 1):
                for ty in range(y0[i], y1[i] + 1):
                    buckets[(tx, ty)].append(i)
        out = []
        for (tx, ty), idx in buckets.items():
            data = encode_tile(z, tx, ty, geoms[idx], [fs.props[keep[i]] for i in idx])
            if data:
                out.append((zxy_to_tileid(z, tx, ty), z, tx, ty, data))
        out.sort()
        log(f"z{z}: {len(geoms)} features, {len(out)} tiles, {time.time() - t0:.1f}s")
        for _, zz, tx, ty, data in out:
            yield zz, tx, ty, data


def write_pmtiles(fs: FeatureSet, path: Path, min_zoom: int, max_zoom: int, bounds, metadata: dict):
    """Write the archive; bounds is (west, south, east, north) in degrees. Returns tile counts per zoom."""
    counts: dict[int, int] = defaultdict(int)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with open(tmp, "wb") as f:
        w = Writer(f)
        for z, x, y, data in build_tiles(fs, min_zoom, max_zoom):
            w.write_tile(zxy_to_tileid(z, x, y), data)
            counts[z] += 1
        west, south, east, north = bounds
        header = {
            "tile_type": TileType.MVT,
            "tile_compression": Compression.GZIP,
            "min_zoom": min_zoom, "max_zoom": max_zoom,
            "min_lon_e7": int(west * 1e7), "min_lat_e7": int(south * 1e7),
            "max_lon_e7": int(east * 1e7), "max_lat_e7": int(north * 1e7),
            "center_zoom": min_zoom,
            "center_lon_e7": int((west + east) / 2 * 1e7), "center_lat_e7": int((south + north) / 2 * 1e7),
        }
        md = dict(metadata)
        md["vector_layers"] = [{
            "id": LAYER, "minzoom": min_zoom, "maxzoom": max_zoom,
            "fields": {"interval": "Number", "target": "String", "class": "String"},
        }]
        w.finalize(header, md)
    tmp.replace(path)
    return dict(counts)


def interval_features(natural, masks: dict[str, np.ndarray], transform: Affine, interval: int, fs: FeatureSet):
    """Add the patches of each target mask, labelled by baseline natural class."""
    for t, m in masks.items():
        label = np.where(m, natural, 0).astype(np.uint8)  # natural idx is 1 + index in NATURAL_CLASSES
        if not label.any():
            continue
        geoms, names = vectorize(label, transform, cl.NATURAL_CLASSES)
        fs.add(to_mercator(geoms), names, interval, t)
        log(f"  {interval} {t}: {len(geoms)} patches")


def cached_latest(raster) -> int | None:
    found = [y for y in range(2009, 2060) if fx.tile_path(y, raster).exists()]
    return max(found) if found else None


def export_area(area_id, out_dir: Path, params, latest=None, targets=None, min_zoom=MIN_ZOOM,
                max_zoom=MAX_ZOOM, check_legend=False):
    cfg = rn.AREAS[area_id]
    targets = [t for t in cl.TARGETS if t in (targets or cl.TARGETS)]
    if params.pasture_is_crop:
        targets = [t for t in targets if t != "pasture"]
    if not cfg.get("bbox_corners"):
        raise SystemExit("only bbox_corners areas are supported so far (use sk-mb-estevan-melville)")
    from .export_shapes import test_area_bbox
    grid, raster = rn.window_bbox(test_area_bbox())
    if latest is None:
        try:
            latest = max(fx.service_years())
        except RuntimeError:
            latest = cached_latest(raster)
            log(f"service unreachable, using newest cached year {latest}")
    support = [latest - 1] if (latest - 1) not in rn.BASELINES else []
    years = sorted(set(rn.BASELINES + [latest] + support))
    log(f"years {years}, latest {latest}")
    rows = cl.load_classes()
    groups, naturals, _ = rn.load_stack(raster, years, rows, check_legend=check_legend)
    pm2 = mean_pixel_m2(grid)
    transform = Affine(fx.PIXEL_M, 0, raster[0], 0, -fx.PIXEL_M, raster[3])

    fs = FeatureSet()
    t0 = time.time()
    for b in rn.BASELINES:  # one interval at a time keeps masks small
        if b >= latest:
            continue
        py = cv.persistence_year(b, latest, years)
        nat = cv.clean_baseline(naturals[b], [groups[y] for y in years if y < b], params)
        masks = cv.conversion_masks(nat > 0, groups[latest], groups[py] if py is not None else None,
                                    params, pm2, targets)
        for t, m in masks.items():
            log(f"  {b} {t}: {m.sum() * pm2 / 1e4:,.0f} ha converted")
        interval_features(nat, masks, transform, b, fs)
        del masks, nat
    log(f"vectorised {len(fs)} patches in {time.time() - t0:.1f}s")

    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)
    cs = [(grid[0], grid[1]), (grid[2], grid[1]), (grid[2], grid[3]), (grid[0], grid[3])]
    lon, lat = to_ll.transform([c[0] for c in cs], [c[1] for c in cs])
    bounds = (min(lon), min(lat), max(lon), max(lat))
    metadata = {
        "name": cfg["name"], "area_id": area_id, "format": "pbf", "type": "overlay", "version": "1",
        "description": "Converted 30 m pixels (natural in the baseline year, target class in the latest year), "
                       "4-connected patches per interval, target and natural class.",
        "attribution": "AAFC Annual Crop Inventory, OGL-Canada-2.0",
        "latest": latest, "intervals": [b for b in rn.BASELINES if b < latest], "targets": targets,
        "method": rn.describe_method(latest, params, {}, targets),
    }
    path = out_dir / f"{area_id}.pmtiles"
    counts = write_pmtiles(fs, path, min_zoom, max_zoom, bounds, metadata)
    log(f"wrote {path} ({path.stat().st_size / 1e6:.2f} MB), tiles per zoom {counts}")
    return path, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", default="sk-mb-estevan-melville", choices=sorted(rn.AREAS))
    ap.add_argument("--out", type=Path, default=EXPORTS)
    ap.add_argument("--latest", type=int, default=None)
    ap.add_argument("--targets", default=",".join(cl.TARGETS))
    ap.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    ap.add_argument("--max-zoom", type=int, default=MAX_ZOOM)
    ap.add_argument("--min-patch-ha", type=float, default=cv.FilterParams.min_patch_ha)
    ap.add_argument("--no-persistence", action="store_true")
    ap.add_argument("--majority", action="store_true")
    ap.add_argument("--keep-prior-crop", action="store_true")
    ap.add_argument("--keep-prior-pasture-urban", action="store_true")
    ap.add_argument("--pasture-is-crop", action="store_true")
    ap.add_argument("--check-legend", action="store_true", help="check the service legend (needs network)")
    a = ap.parse_args(argv)
    params = cv.FilterParams(
        persistence=not a.no_persistence, min_patch_ha=a.min_patch_ha, majority=a.majority,
        pasture_is_crop=a.pasture_is_crop, exclude_prior_crop=not a.keep_prior_crop,
        exclude_prior_pasture_urban=not a.keep_prior_pasture_urban,
    )
    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in cl.TARGETS]
    if bad:
        ap.error(f"unknown targets {bad}; choose from {cl.TARGETS}")
    export_area(a.area, a.out, params, a.latest, targets, a.min_zoom, a.max_zoom, a.check_legend)


if __name__ == "__main__":
    main()
