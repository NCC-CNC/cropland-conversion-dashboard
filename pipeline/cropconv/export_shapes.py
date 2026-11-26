"""Raw per-year shapefiles of ACI class patches for a test area, zipped.

    python -m cropconv.export_shapes --years 2024            # one sample year
    python -m cropconv.export_shapes                         # every service year

One polygon per connected patch of one original ACI class code (4-connected),
so the files are the unmodified ACI classes, not the dashboard's groups.
Output is EPSG:3978, the CRS the data was fetched in. Zips go to
pipeline/exports/ (gitignored), for upload to a GitHub Release.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import shapefile  # pyshp
from pyproj import CRS, Transformer
from rasterio.features import shapes

from . import classes as cl
from . import fetch as fx

EXPORTS = Path(__file__).resolve().parent.parent / "exports"

# Corners from the brief: Estevan SK, Melita MB, Russell MB, Melville SK.
CORNERS = {
    "Estevan": (-102.99, 49.14),
    "Melita": (-100.99, 49.27),
    "Russell": (-101.28, 50.78),
    "Melville": (-102.81, 50.93),
}
AREA_ID = "sk-mb-estevan-melville"


def test_area_bbox(px: int = fx.PIXEL_M) -> tuple[int, int, int, int]:
    """EPSG:3978 bbox around the four corners, snapped outward to the pixel size."""
    t = Transformer.from_crs(4326, 3978, always_xy=True)
    pts = [t.transform(*c) for c in CORNERS.values()]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0 = int(min(xs) // px) * px
    y0 = int(min(ys) // px) * px
    x1 = -int(-max(xs) // px) * px
    y1 = -int(-max(ys) // px) * px
    return x0, y0, x1, y1


def _signed_area(ring) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1])) / 2


def _shp_rings(geom: dict) -> list[list[tuple[float, float]]]:
    """Shapefile rule: outer rings clockwise, holes counter-clockwise."""
    rings = []
    for i, ring in enumerate(geom["coordinates"]):
        pts = [tuple(p) for p in ring[:-1]]
        clockwise = _signed_area(pts) < 0
        if (i == 0) != clockwise:
            pts.reverse()
        rings.append(pts + [pts[0]])
    return rings


def write_year(year: int, out_dir: Path, px: int = fx.PIXEL_M) -> Path:
    bbox = test_area_bbox(px)
    arr, transform = fx.read_year(fx.fetch_year(year, bbox, px))
    labels = {r["code"]: (r["label"], r["group"]) for r in cl.load_classes()}
    stem = f"aci_{year}_{AREA_ID}"
    base = out_dir / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    w = shapefile.Writer(str(base), shapeType=shapefile.POLYGON)
    w.field("YEAR", "N", 4)
    w.field("CODE", "N", 3)
    w.field("LABEL", "C", 40)
    w.field("GRP", "C", 10)
    n = 0
    for geom, val in shapes(arr, mask=arr != 0, transform=transform, connectivity=4):
        code = int(val)
        label, grp = labels.get(code, ("unknown", "other"))
        w.poly(_shp_rings(geom))
        w.record(year, code, label, grp)
        n += 1
    w.close()
    Path(f"{base}.prj").write_text(CRS.from_epsg(3978).to_wkt(), encoding="utf-8")
    zpath = out_dir / f"{stem}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ext in ("shp", "shx", "dbf", "prj"):
            f = Path(f"{base}.{ext}")
            z.write(f, f.name)
            f.unlink()
    print(f"{year}: {n} polygons, {zpath.stat().st_size / 1e6:.1f} MB zip", file=sys.stderr, flush=True)
    return zpath


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, help="default: every service year")
    ap.add_argument("--out", type=Path, default=EXPORTS)
    a = ap.parse_args(argv)
    years = a.years or fx.service_years()
    print(f"bbox {test_area_bbox()} years {years}", file=sys.stderr)
    for y in years:
        write_year(y, a.out)


if __name__ == "__main__":
    main()
