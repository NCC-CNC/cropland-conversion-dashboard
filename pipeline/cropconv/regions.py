"""Regions for choosing an area: farming-zone ecoregions clipped to MB and SK.

    python -m cropconv.regions            # download (cached), clip, write regions.json
    python -m cropconv.regions --check    # print id, name and area only, write nothing

A region is a National Ecological Framework ecoregion of ecozone 9 (Boreal
Plains) or 10 (Prairies), clipped to Manitoba and Saskatchewan, with pieces of
one ecoregion in one province merged. See docs/design/05_regional_partitioning.md.

Downloaded files are untrusted data: each archive is extracted into its own new
directory (flat, only the shapefile parts) and read only with pyshp, shapely and
pyproj. Nothing from them is ever executed.

Limits: the ecoregion layer is the 2003 1:1 000 000 product, and the province
boundary is Natural Earth 10m. Both are coarse, so assigning a cell near a
region edge is approximate.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import requests
import shapefile  # pyshp
import shapely
from pyproj import Transformer
from shapely.geometry import mapping, shape

REPO = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent.parent / "cache" / "regions_src"
DEFAULT_OUT = REPO / "web" / "public" / "data" / "regions.json"

ECOREGION_URL = "https://sis.agr.gc.ca/cansis/nsdb/ecostrat/region/ecoregion_shp.zip"
PROVINCE_URL = "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"
ECOREGION_LICENCE = "Open Government Licence - Canada, AAFC National Ecological Framework for Canada (2003, 1:1M)"
PROVINCE_LICENCE = "Natural Earth 10m admin-1 states and provinces, public domain"

ECOZONES = (9, 10)  # Boreal Plains, Prairies: the farming zone
PROVINCES = ("MB", "SK")
SOURCE_CRS = "EPSG:4617"  # NAD83(CSRS), what the .prj of the ecoregion layer says
WORK_CRS = "EPSG:3978"
AREA_CRS = "ESRI:102001"  # Canada Albers equal area conic, for km2
MIN_PIECE_KM2 = 10.0  # drop clip slivers (boundary mismatch) smaller than this
SIMPLIFY_M = 1000.0  # in EPSG:3978; the source is 1:1M so finer detail is not real
COORD_DECIMALS = 4

# The source spells one name wrongly. Keys are the source REGION_NAM exactly
# (after stripping padding); values are the display names we publish.
NAME_OVERRIDES = {
    "Southwest Manotoba Uplands": "Southwest Manitoba Uplands",
}


def slugify(text: str) -> str:
    """Lowercase ASCII slug: letters and digits separated by single hyphens."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def display_name(source_name: str) -> str:
    n = source_name.strip()
    return NAME_OVERRIDES.get(n, n)


def region_id(source_name: str, province: str) -> str:
    return f"{slugify(display_name(source_name))}-{province.lower()}"


# ---------------------------------------------------------------- download


def download(url: str, dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=300, headers={"User-Agent": "cropland-conversion-pipeline"})
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def extract_shapefile(zip_path: Path, out_dir: Path) -> Path:
    """Extract only shapefile parts, flat, into a new or reused empty-or-extracted dir.

    Member paths are reduced to their base names, so a hostile archive cannot
    write outside out_dir. Returns the .shp path.
    """
    keep = {".shp", ".shx", ".dbf", ".prj", ".cpg"}
    if not out_dir.exists() or not any(out_dir.iterdir()):
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                p = Path(info.filename)
                if info.is_dir() or p.suffix.lower() not in keep:
                    continue
                (out_dir / p.name).write_bytes(z.read(info))
    shps = sorted(out_dir.glob("*.shp"))
    if len(shps) != 1:
        raise RuntimeError(f"expected one .shp in {out_dir}, found {len(shps)}")
    return shps[0]


# ---------------------------------------------------------------- reading


def _reproject(geom, src_crs: str, dst_crs: str):
    t = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return shapely.transform(geom, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))


def _to_work(geom, src_crs: str):
    # densify first so long straight edges (such as the 49th parallel) curve correctly
    return _reproject(shapely.segmentize(geom, 0.02), src_crs, WORK_CRS)


def read_ecoregions(shp: Path):
    """Ecoregion records of ecozones 9 and 10 as dicts with a shapely geometry in EPSG:3978."""
    out = []
    r = shapefile.Reader(str(shp), encoding="latin-1")  # source has accented French names
    for sr in r.shapeRecords():
        d = sr.record.as_dict()
        if int(d["ECOZONE"]) not in ECOZONES:
            continue
        g = shapely.make_valid(shape(sr.shape.__geo_interface__))
        out.append(
            {
                "ecoregion": int(d["ECOREGION"]),
                "ecozone": int(d["ECOZONE"]),
                "source_name": str(d["REGION_NAM"]).strip(),
                "geom": _to_work(g, SOURCE_CRS),
            }
        )
    return out


def read_provinces(shp: Path, codes=PROVINCES):
    """Province geometry in EPSG:3978 keyed by two letter code (Natural Earth 'postal')."""
    out = {}
    r = shapefile.Reader(str(shp), encoding="utf-8")
    for sr in r.shapeRecords():
        d = sr.record.as_dict()
        if d.get("adm0_a3") == "CAN" and d.get("postal") in codes:
            g = shapely.make_valid(shape(sr.shape.__geo_interface__))
            out[d["postal"]] = _to_work(g, "EPSG:4326")
    missing = set(codes) - set(out)
    if missing:
        raise RuntimeError(f"provinces not found in boundary file: {sorted(missing)}")
    return out


# ---------------------------------------------------------------- clipping


def clip_regions(ecoregions, provinces, min_km2: float = MIN_PIECE_KM2):
    """Clip ecoregions to provinces and merge pieces sharing ecoregion and province.

    Inputs and outputs are in a metric CRS (EPSG:3978). Returns a list of dicts
    sorted by id, each with id, name, ecoregion, ecozone, province and geom.
    """
    merged: dict[tuple[int, str], dict] = {}
    for e in ecoregions:
        for code, pgeom in provinces.items():
            piece = e["geom"].intersection(pgeom)
            if piece.is_empty:
                continue
            # keep only polygonal parts (intersections can leave stray lines)
            polys = [g for g in getattr(piece, "geoms", [piece]) if g.geom_type in ("Polygon", "MultiPolygon")]
            if not polys:
                continue
            piece = shapely.union_all(polys)
            key = (e["ecoregion"], code)
            if key in merged:
                merged[key]["geom"] = merged[key]["geom"].union(piece)
            else:
                merged[key] = {
                    "id": region_id(e["source_name"], code),
                    "name": display_name(e["source_name"]),
                    "ecoregion": e["ecoregion"],
                    "ecozone": e["ecozone"],
                    "province": code,
                    "geom": piece,
                }
    out = [m for m in merged.values() if m["geom"].area / 1e6 >= min_km2]
    ids = [m["id"] for m in out]
    if len(ids) != len(set(ids)):
        raise RuntimeError("region ids are not unique")
    return sorted(out, key=lambda m: m["id"])


def area_km2(geom_3978) -> float:
    return _reproject(geom_3978, WORK_CRS, AREA_CRS).area / 1e6


# ---------------------------------------------------------------- output


def to_feature_collection(regions, simplify_m: float = SIMPLIFY_M, decimals: int = COORD_DECIMALS) -> dict:
    feats = []
    for r in regions:
        simple = r["geom"].simplify(simplify_m, preserve_topology=True)
        wgs = _reproject(simple, WORK_CRS, "EPSG:4326")
        wgs = shapely.set_precision(wgs, 10.0**-decimals)
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "id": r["id"],
                    "name": r["name"],
                    "province": r["province"],
                    "ecoregion": r["ecoregion"],
                    "ecozone": r["ecozone"],
                    "area_km2": round(area_km2(r["geom"]), 1),
                },
                "geometry": mapping(wgs),
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "description": "Farming-zone ecoregions (ecozones 9 and 10) clipped to Manitoba and Saskatchewan",
            "ecoregion_source": ECOREGION_LICENCE,
            "province_source": PROVINCE_LICENCE,
            "caveat": "Source ecoregions are 1:1M (2003) and the province boundary is coarse; "
            "cell assignment near region edges is approximate. Geometry is simplified.",
        },
        "features": feats,
    }


def build(cache: Path = CACHE, force: bool = False) -> dict:
    eco_zip = download(ECOREGION_URL, cache / "ecoregion_shp.zip", force)
    prov_zip = download(PROVINCE_URL, cache / "ne_admin1.zip", force)
    eco_shp = extract_shapefile(eco_zip, cache / "ecoregion")
    prov_shp = extract_shapefile(prov_zip, cache / "ne")
    clipped = clip_regions(read_ecoregions(eco_shp), read_provinces(prov_shp))
    return to_feature_collection(clipped)


# ---------------------------------------------------------------- use


def load_regions(path: Path = DEFAULT_OUT) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assign_regions(lon, lat, regions: dict | None = None) -> np.ndarray:
    """Region id for each point (WGS84 degrees); None where no region contains it.

    Vectorised with shapely.contains_xy per region after a bounding box test.
    Regions are disjoint by construction; if simplification makes two overlap
    at an edge, the first in id order wins.
    """
    regions = regions if regions is not None else load_regions()
    lon = np.asarray(lon, dtype="float64")
    shp = lon.shape
    lon = lon.ravel()
    lat = np.asarray(lat, dtype="float64").ravel()
    out = np.full(lon.shape, None, dtype=object)
    todo = np.ones(lon.shape, dtype=bool)
    for f in sorted(regions["features"], key=lambda f: f["properties"]["id"]):
        g = shape(f["geometry"])
        x0, y0, x1, y1 = g.bounds
        idx = np.flatnonzero(todo & (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1))
        if idx.size == 0:
            continue
        hit = idx[shapely.contains_xy(g, lon[idx], lat[idx])]
        out[hit] = f["properties"]["id"]
        todo[hit] = False
    return out.reshape(shp)


def region_areas_km2(regions: dict | None = None) -> dict[str, float]:
    """Clipped area in km2 (equal-area CRS, before simplification) keyed by region id."""
    regions = regions if regions is not None else load_regions()
    return {f["properties"]["id"]: float(f["properties"]["area_km2"]) for f in regions["features"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true", help="re-download the sources")
    ap.add_argument("--check", action="store_true", help="print the table and write nothing")
    a = ap.parse_args(argv)
    fc = build(force=a.force)
    for f in fc["features"]:
        p = f["properties"]
        print(f"{p['id']:40s} {p['name']:30s} {p['area_km2']:10.1f} km2")
    if not a.check:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(fc, separators=(",", ":"), ensure_ascii=False)
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out} ({len(text) / 1024:.0f} KB, {len(fc['features'])} regions)")


if __name__ == "__main__":
    main()
