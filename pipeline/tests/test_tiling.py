import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cropconv import regions as rg
from cropconv import tiling as tl

TILE_KM = 10  # small tiles keep the synthetic grid cheap
CLASSES = ["forest", "grassland", "wetland", "shrubland"]


def region_collection():
    """Two rectangles in EPSG:3978 metres turned into a regions.json style collection (WGS84)."""
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)

    def box(x0, y0, x1, y1):
        ring = [to_ll.transform(x, y) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]
        return {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}

    feats = [
        {"type": "Feature", "properties": {"id": "west-sk", "name": "West"}, "geometry": box(-520000, 150000, -509000, 175000)},
        {"type": "Feature", "properties": {"id": "east-mb", "name": "East"}, "geometry": box(-509000, 150000, -498000, 175000)},
    ]
    return {"type": "FeatureCollection", "features": feats}


def synthetic(seed=1):
    """A 20 x 15 km grid of 1 km cells (centres on .5 km) with a hole, in EPSG:3978."""
    rng = np.random.default_rng(seed)
    xs = -520000 + 500 + 1000 * np.arange(20)
    ys = 150000 + 500 + 1000 * np.arange(15)
    gx, gy = np.meshgrid(xs, ys)
    x, y = gx.ravel(), gy.ravel()
    keep = rng.random(x.size) > 0.2
    x, y = x[keep], y[keep]
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)
    lon, lat = to_ll.transform(x, y)
    n = x.size

    def arr(scale):
        return np.round(rng.random(n) * scale, 2)

    intervals = {}
    for key in ("2016-2024", "2021-2024"):
        intervals[key] = {
            "natural_ha": {c: arr(100).tolist() for c in CLASSES},
            "converted_ha": {
                "crop": {"forest": arr(5).tolist(), "grassland": arr(20).tolist()},
                "urban": {"grassland": arr(1).tolist()},
            },
        }
    cells = {"lon": np.round(lon, 5).tolist(), "lat": np.round(lat, 5).tolist(),
             "area_ha": [100.0] * n, "intervals": intervals}
    return cells, x, y


def leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from leaves(v, path + (k,))
    else:
        yield path, node


@pytest.fixture()
def written(tmp_path):
    cells, x, y = synthetic()
    regs = region_collection()
    ids = rg.assign_regions(cells["lon"], cells["lat"], regs)
    index, stats = tl.write_tiles(tmp_path, cells, x, y, ids, regs, area_id="syn", tile_km=TILE_KM,
                                  names={"west-sk": "West", "east-mb": "East"})
    return tmp_path, cells, x, y, ids, index, stats


def test_tile_coords_and_edges():
    c, r = tl.tile_coords([-520000.0, -510000.0, -509999.5], [0.0, 9999.0, 10000.0], 10000)
    assert c.tolist() == [-52, -51, -51]  # an edge belongs to the tile on its north east side
    assert r.tolist() == [0, 0, 1]
    assert tl.tile_name(-52, 3) == "-52_3"


def test_every_cell_in_exactly_one_tile(written):
    d, cells, x, y, ids, index, stats = written
    assert index["cells"] == len(cells["lon"]) == sum(t["cells"] for t in index["tiles"])
    seen = set()
    for t in index["tiles"]:
        part = json.loads((d / t["file"]).read_text())
        assert len(part["lon"]) == t["cells"] == len(part["region"])
        for lon, lat in zip(part["lon"], part["lat"]):
            assert (lon, lat) not in seen
            seen.add((lon, lat))
        # every cell centre of the tile is in the tile's square and bbox
        w, s, e, n = t["bbox"]
        assert all(w <= v <= e for v in part["lon"]) and all(s <= v <= n for v in part["lat"])
    assert len(seen) == len(cells["lon"])
    col, row = tl.tile_coords(x, y, TILE_KM * 1000)
    assert {(int(a), int(b)) for a, b in zip(col, row)} == {(t["col"], t["row"]) for t in index["tiles"]}
    assert len(stats) == len(index["tiles"])


def test_region_ids_and_summary(written):
    d, cells, x, y, ids, index, stats = written
    assert index["regions"] == ["east-mb", "west-sk"]
    by_id = {r["id"]: r for r in index["region_summary"]}
    for rid in ("west-sk", "east-mb"):
        assert by_id[rid]["cells"] == int(np.sum(ids == rid))
    # the split between the regions is at x = -509000, inside the second 10 km tile column
    both = [t for t in index["tiles"] if len(t["regions"]) == 2]
    assert both and all(set(t["regions"]) == {"west-sk", "east-mb"} for t in both)
    assert sum(r["cells"] for r in index["region_summary"]) + index["unassigned"]["cells"] == index["cells"]
    for t in index["tiles"]:
        part = json.loads((d / t["file"]).read_text())
        for i, rid in enumerate(index["regions"]):
            assert part["region"].count(i) == t["regions"].get(rid, 0)
        assert sum(t["regions"].values()) + part["region"].count(-1) == t["cells"]
    for rid, r in by_id.items():
        assert r["name"] in ("West", "East")
        for name in r["tiles"]:
            assert rid in next(t for t in index["tiles"] if t["id"] == name)["regions"]
    # cells outside every region are counted and carry -1
    assert index["unassigned"]["cells"] == int(np.sum(np.array([i is None for i in ids])))


def test_index_schema(written):
    d, cells, x, y, ids, index, stats = written
    on_disk = json.loads((d / "index.json").read_text())
    assert on_disk == index
    assert set(index) == {"area_id", "contract_version", "crs", "tile_m", "cell_size_m", "cells",
                          "regions", "region_summary", "unassigned", "tiles"}
    assert index["contract_version"] == 3 and index["crs"] == "EPSG:3978" and index["tile_m"] == TILE_KM * 1000
    for t in index["tiles"]:
        assert set(t) == {"id", "col", "row", "file", "bbox", "cells", "bytes", "regions"}
        assert t["file"] == f"tiles/{t['id']}.json" and (d / t["file"]).stat().st_size == t["bytes"]
        w, s, e, n = t["bbox"]
        assert -180 <= w < e <= 180 and -90 <= s < n <= 90
    for r in index["region_summary"]:
        assert set(r) == {"id", "name", "cells", "area_ha", "tiles", "totals"}
        assert set(r["totals"]) == set(cells["intervals"])
    assert sorted(p.name for p in (d / "tiles").iterdir()) == sorted(f"{t['id']}.json" for t in index["tiles"])


def test_round_trip_sums_equal_per_target_class_and_interval(written):
    d, cells, x, y, ids, index, stats = written
    parts = [json.loads((d / t["file"]).read_text()) for t in index["tiles"]]
    ref = {p: math.fsum(v) for p, v in leaves(cells["intervals"])}
    acc = {}
    for part in parts:
        for p, v in leaves(part["intervals"]):
            acc.setdefault(p, []).append(v)
    assert set(acc) == set(ref)
    assert any(p[1:3] == ("converted_ha", "crop") for p in ref) and any("urban" in p for p in ref)
    for p, vs in acc.items():
        assert math.fsum(a for v in vs for a in v) == ref[p], p  # exact: same doubles, exact summation
    for col in ("lon", "lat", "area_ha"):
        assert math.fsum(a for part in parts for a in part[col]) == math.fsum(cells[col])
    # region totals in the index add up to the whole, per target, class and interval
    for key, iv in cells["intervals"].items():
        for cls, arr in iv["natural_ha"].items():
            tot = [r["totals"][key]["natural_ha"][cls] for r in index["region_summary"]]
            tot.append(index["unassigned"].get("totals", {}).get(key, {}).get("natural_ha", {}).get(cls, 0))
            assert sum(tot) == pytest.approx(sum(arr), abs=0.05)


def test_rewrite_removes_stale_tiles_and_empty_input(tmp_path):
    (tmp_path / "tiles").mkdir()
    (tmp_path / "tiles" / "stale.json").write_text("{}")
    cells, x, y = synthetic()
    keep = np.zeros(len(x), dtype=bool)
    keep[:3] = True
    small = {"lon": cells["lon"][:3], "lat": cells["lat"][:3], "area_ha": cells["area_ha"][:3],
             "intervals": tl.take(cells["intervals"], np.flatnonzero(keep))}
    index, _ = tl.write_tiles(tmp_path, small, x[:3], y[:3], [None] * 3, None, area_id="s", tile_km=TILE_KM)
    assert not (tmp_path / "tiles" / "stale.json").exists()
    assert index["regions"] == [] and index["unassigned"]["cells"] == 3
    with pytest.raises(ValueError):
        tl.write_tiles(tmp_path, small, x[:2], y[:3], [None] * 3, None, area_id="s")


def test_summarise_stats():
    s = tl.summarise_stats([{"id": "a", "raw": 10, "gz": 1}, {"id": "b", "raw": 30, "gz": 3}, {"id": "c", "raw": 20, "gz": 2}])
    assert s["tiles"] == 3 and s["raw"] == {"min": 10, "median": 20, "max": 30, "total": 60}
