"""Clipped downloads from the AAFC ACI ImageServer (never national rasters)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import rasterio
import requests

BASE = "https://agriculture.canada.ca/imagery-images/rest/services/annual_crop_inventory"
CACHE = Path(__file__).resolve().parent.parent / "cache"
PIXEL_M = 30
CRS = "EPSG:3978"  # NRCan Lambert Conformal Conic; the service reprojects on request


def _get(url, **kw):
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=300, headers={"User-Agent": "cropland-conversion-pipeline"}, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # retry with backoff
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"request failed: {url}: {last}")


def service_years() -> list[int]:
    j = _get(BASE, params={"f": "json"}).json()
    return sorted(int(s["name"].rsplit("/", 1)[1]) for s in j["services"])


def service_info(year: int) -> dict:
    return _get(f"{BASE}/{year}/ImageServer", params={"f": "json"}).json()


def service_legend_labels(year: int) -> list[str]:
    j = _get(f"{BASE}/{year}/ImageServer/legend", params={"f": "json"}).json()
    return [e["label"] for e in j["layers"][0]["legend"]]


def tile_path(year: int, bbox, px: int = PIXEL_M) -> Path:
    x0, y0, x1, y1 = (int(v) for v in bbox)
    return CACHE / f"aci_{year}_3978_{x0}_{y0}_{x1}_{y1}_{px}m.tif"


def fetch_year(year: int, bbox, px: int = PIXEL_M, force: bool = False) -> Path:
    """Download the clipped class raster for one year; cached on disk.

    bbox is (xmin, ymin, xmax, ymax) in EPSG:3978 metres, a multiple of px wide.
    The request asks for nearest neighbour resampling, single band U8, so the
    returned values are the unmodified ACI class codes (no colour mapping).
    """
    out = tile_path(year, bbox, px)
    if out.exists() and not force:
        return out
    x0, y0, x1, y1 = bbox
    w, h = (x1 - x0) // px, (y1 - y0) // px
    params = {
        "bbox": f"{x0},{y0},{x1},{y1}", "bboxSR": 3978, "imageSR": 3978,
        "size": f"{w},{h}", "format": "tiff", "pixelType": "U8",
        "interpolation": "RSP_NearestNeighbor", "f": "json",
    }
    j = _get(f"{BASE}/{year}/ImageServer/exportImage", params=params).json()
    if "href" not in j:
        raise RuntimeError(f"exportImage error for {year}: {json.dumps(j)[:300]}")
    data = _get(j["href"]).content
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.rename(out)
    return out


def read_year(path: Path):
    """Read a cached tile; returns (array, transform). Validates shape and type."""
    with rasterio.open(path) as ds:
        if ds.count != 1 or ds.dtypes[0] != "uint8":
            raise ValueError(f"{path.name}: expected 1 band uint8, got {ds.count} {ds.dtypes}")
        if ds.crs is None or ds.crs.to_epsg() != 3978:
            raise ValueError(f"{path.name}: unexpected CRS {ds.crs}")
        arr = ds.read(1)
        return arr, ds.transform


def assert_codes_unmodified(arr: np.ndarray, known_codes: set[int]) -> None:
    """Colour mapped or interpolated output would carry codes outside the legend."""
    vals = {int(v) for v in np.unique(arr)}
    bad = sorted(v for v in vals - known_codes if v != 0)
    if bad:
        raise ValueError(f"values not in the ACI legend (colour mapped or interpolated?): {bad}")
