import gzip
import sys
from pathlib import Path

import mapbox_vector_tile
import numpy as np
import shapely
from affine import Affine
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import Compression, TileType, deserialize_header

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cropconv import classes as cl
from cropconv import export_tiles as et

# A 50 m grid in EPSG:3978 near the SK/MB test area, 30 m pixels.
X0, Y1 = -520000.0, 150000.0
TRANSFORM = Affine(30, 0, X0, 0, -30, Y1)


def synthetic():
    """Natural idx raster and masks: a forest block, a grassland block touching it only
    diagonally, and one crop-only block."""
    nat = np.zeros((20, 20), dtype=np.uint8)
    nat[2:6, 2:6] = 1 + cl.NATURAL_CLASSES.index("forest")
    nat[6:9, 6:9] = 1 + cl.NATURAL_CLASSES.index("grassland")  # touches the forest block at a corner
    crop = nat > 0
    urban = np.zeros_like(crop)
    urban[12:14, 12:14] = True
    nat[12:14, 12:14] = 1 + cl.NATURAL_CLASSES.index("wetland")
    return nat, {"crop": crop & (nat > 0), "urban": urban}


def test_vectorize_gives_one_patch_per_class_and_4_connectivity():
    nat, masks = synthetic()
    label = np.where(masks["crop"], nat, 0).astype(np.uint8)
    geoms, names = et.vectorize(label, TRANSFORM, cl.NATURAL_CLASSES)
    assert sorted(names) == ["forest", "grassland"]
    areas = {n: g.area for g, n in zip(geoms, names)}
    assert areas["forest"] == 16 * 900
    assert areas["grassland"] == 9 * 900
    # same class, diagonal contact only: 4-connectivity must keep two patches
    diag = np.zeros((6, 6), dtype=np.uint8)
    diag[0:2, 0:2] = 1
    diag[2:4, 2:4] = 1
    g2, n2 = et.vectorize(diag, TRANSFORM, cl.NATURAL_CLASSES)
    assert len(g2) == 2 and n2 == ["forest", "forest"]


def test_interval_features_properties():
    nat, masks = synthetic()
    fs = et.FeatureSet()
    et.interval_features(nat, masks, TRANSFORM, 2016, fs)
    assert len(fs) == 3
    props = sorted((p["target"], p["class"]) for p in fs.props)
    assert props == [("crop", "forest"), ("crop", "grassland"), ("urban", "wetland")]
    assert all(p["interval"] == 2016 for p in fs.props)
    # reprojected to Web Mercator, so coordinates are metres on the 3857 plane
    minx, miny, maxx, maxy = shapely.total_bounds(np.array(fs.geoms, dtype=object))
    assert -1.3e7 < minx < maxx < -1.0e7 and 6e6 < miny < maxy < 1e7


def test_pmtiles_header_and_round_trip(tmp_path):
    nat, masks = synthetic()
    fs = et.FeatureSet()
    et.interval_features(nat, masks, TRANSFORM, 2016, fs)
    path = tmp_path / "t.pmtiles"
    bounds = (-103.0, 49.0, -101.0, 51.0)
    counts = et.write_pmtiles(fs, path, 11, 13, bounds, {"name": "test"})
    assert set(counts) == {11, 12, 13} and all(v >= 1 for v in counts.values())

    raw = path.read_bytes()
    assert raw[:7] == b"PMTiles" and raw[7] == 3
    h = deserialize_header(raw[:127])
    assert h["tile_type"] == TileType.MVT and h["tile_compression"] == Compression.GZIP
    assert (h["min_zoom"], h["max_zoom"]) == (11, 13)
    assert h["addressed_tiles_count"] == sum(counts.values())

    with open(path, "rb") as f:
        reader = Reader(MmapSource(f))
        meta = reader.metadata()
        assert meta["vector_layers"][0]["id"] == "converted"
        assert meta["name"] == "test"
        tiles = list(all_tiles(MmapSource(f)))
        assert len(tiles) == sum(counts.values())
        (z, x, y), data = next(t for t in tiles if t[0][0] == 13)
        layer = mapbox_vector_tile.decode(gzip.decompress(data))["converted"]
    feats = layer["features"]
    assert feats and all(set(ft["properties"]) == {"interval", "target", "class"} for ft in feats)
    assert {ft["properties"]["interval"] for ft in feats} == {2016}
    assert {ft["properties"]["target"] for ft in feats} <= {"crop", "urban"}
    assert all(ft["geometry"]["type"] in ("Polygon", "MultiPolygon") for ft in feats)


def test_low_zoom_drops_tiny_patches_but_max_zoom_keeps_them():
    nat = np.zeros((6, 6), dtype=np.uint8)
    nat[1:2, 1:2] = 1  # one 30 m pixel, below half a screen pixel at z11
    fs = et.FeatureSet()
    et.interval_features(nat, {"crop": nat > 0}, TRANSFORM, 2021, fs)
    base = np.empty(1, dtype=object)
    base[:] = fs.geoms
    assert len(et.zoom_geoms(base, 11, 14)[0]) == 0
    assert len(et.zoom_geoms(base, 14, 14)[0]) == 1
