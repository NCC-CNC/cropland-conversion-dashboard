"""Regional tiled runner on a synthetic world: tile geometry, exactness against one big window, resume, assembly."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cropconv import classes as cl
from cropconv import convert as cv
from cropconv import fetch as fx
from cropconv import regional as rgl
from cropconv import regions as rg
from cropconv import tiling as tl

YEARS = [2011, 2016, 2021, 2024, 2025]
ROWS = cl.load_classes()
GROUP_LUT, NATURAL_LUT = cl.build_luts(ROWS)
KNOWN = {r["code"] for r in ROWS}
TILE_KM = 30  # a multiple of 30 m, so every tile raster lies on the same pixel lattice
ORIGIN_MOD = 5.0  # pixel centres are 5 m past a multiple of 30 m in this setup


def _h(a, b, salt):
    return ((a * 73856093) ^ (b * 19349663) ^ (salt * 83492791)) % 1000


def world(year, raster):
    """Deterministic classes by pixel centre: 240 m blocks, natural fading to crop in later years, plus pixel noise."""
    x0, y0, x1, y1 = raster
    w, h = int((x1 - x0) // 30), int((y1 - y0) // 30)
    ix = np.round((x0 + (np.arange(w) + 0.5) * 30 - ORIGIN_MOD) / 30).astype(np.int64)
    iy = np.round((y1 - (np.arange(h) + 0.5) * 30 - ORIGIN_MOD) / 30).astype(np.int64)
    bx, by = ix[None, :] // 8, iy[:, None] // 8
    hb = _h(bx, by, 1)
    base = np.select([hb < 150, hb < 300, hb < 400, hb < 700, hb < 800, hb < 850],
                     [110, 200, 80, 131, 122, 34], default=20).astype(np.uint8)
    later = year >= 2021
    flip = (_h(bx, by, 7) < 350) & (hb < 400) & later  # natural blocks that are crop from 2021 on
    arr = np.where(flip, 131, base).astype(np.uint8)
    noise = _h(ix[None, :], iy[:, None], 11 + (year % 7)) < 15
    arr = np.where(noise & (year >= 2024), 131, arr).astype(np.uint8)
    return arr


def readers(year, raster):
    return rgl.arr_to_groups(world(year, raster), KNOWN, GROUP_LUT, NATURAL_LUT)


PARAMS = cv.FilterParams()
TARGETS = cl.TARGETS


def cells_by_xy(d):
    return {(float(x), float(y)): i for i, (x, y) in enumerate(zip(d["x"], d["y"]))}


def test_tile_window_geometry():
    raster, grid, (c0, c1) = rgl.tile_window(2, -1, 100)
    assert raster[0] == 2 * 100000 - 1000 and raster[1] == -100000 - 1000
    assert (raster[2] - raster[0]) == 102000 == (raster[3] - raster[1])
    assert grid == raster  # 102 whole cells
    assert (c0, c1) == (1, 101)
    # the tile corner is exactly c0 cells into the grid
    assert grid[0] + c0 * 1000 == 200000


def test_tiles_for_regions_matches_squares():
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)
    ring = [to_ll.transform(x, y) for x, y in [(10000, 10000), (130000, 10000), (130000, 40000), (10000, 40000), (10000, 10000)]]
    regs = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"id": "a-sk", "name": "A"}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]}
    t = rgl.tiles_for_regions(regs, None, 100)
    assert t == {"a-sk": [(0, 0), (1, 0)]}
    with pytest.raises(ValueError):
        rgl.tiles_for_regions(regs, ["nope"], 100)


def test_tile_cells_equal_a_single_big_window():
    """Four 30 km tiles reproduce one 60 km window cell for cell (the halo makes the filters exact)."""
    big = rgl.compute_tile(0, 0, readers, YEARS, 2025, PARAMS, TARGETS, tile_km=60)
    assert big is not None and len(big["x"]) > 2000
    where = cells_by_xy(big)
    seen = 0
    for col in (0, 1):
        for row in (0, 1):
            t = rgl.compute_tile(col, row, readers, YEARS, 2025, PARAMS, TARGETS, tile_km=TILE_KM)
            for i, key in enumerate(zip(t["x"].tolist(), t["y"].tolist())):
                j = where[key]
                seen += 1
                for k in t:
                    if k.startswith(("nat__", "conv__")) or k in ("area_ha", "lon", "lat"):
                        assert t[k][i] == pytest.approx(big[k][j], abs=1e-6), (k, key)
    assert seen == len(where)
    conv = sum(float(big[k].sum()) for k in big if k.startswith("conv__"))
    assert conv > 0  # the comparison is not vacuous


def test_halo_matters_for_patches_across_a_tile_edge():
    """Without a halo the patch filter would judge cut patches on their visible part and change counts."""
    big = rgl.compute_tile(0, 0, readers, YEARS, 2025, PARAMS, TARGETS, tile_km=60)
    key = "conv__2016__crop__grassland"
    assert big[key].sum() > 0


def test_no_data_tile_is_none():
    z = lambda year, raster: rgl.arr_to_groups(
        np.zeros((int((raster[3] - raster[1]) // 30),) * 2, dtype=np.uint8), KNOWN, GROUP_LUT, NATURAL_LUT)
    assert rgl.compute_tile(0, 0, z, YEARS, 2025, PARAMS, TARGETS, tile_km=TILE_KM) is None


def sparse_year(bad):
    def r(year, raster):
        a = world(year, raster)
        if year == bad:
            a[:] = 0
            a[:5, :5] = 131
        return rgl.arr_to_groups(a, KNOWN, GROUP_LUT, NATURAL_LUT)
    return r


def test_latest_year_with_no_data_skips_the_tile(capsys):
    def r(year, raster):
        a = world(year, raster)
        if year == 2025:
            a[:] = 0
        return rgl.arr_to_groups(a, KNOWN, GROUP_LUT, NATURAL_LUT)
    assert rgl.compute_tile(0, 0, r, YEARS, 2025, PARAMS, TARGETS, tile_km=TILE_KM) is None
    assert "skipped" in capsys.readouterr().out


def test_sparsely_mapped_year_warns_and_runs(capsys):
    for bad in (2021, 2025):
        rgl.compute_tile(0, 0, sparse_year(bad), YEARS, 2025, PARAMS, TARGETS, tile_km=TILE_KM)
        assert str(bad) in capsys.readouterr().out


def synthetic_regions():
    """West and east halves of a 60 km square at the projection origin, as regions.json (WGS84)."""
    to_ll = Transformer.from_crs(3978, 4326, always_xy=True)

    def box(x0, y0, x1, y1):
        ring = [to_ll.transform(x, y) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]
        return {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}

    feats = [
        {"type": "Feature", "properties": {"id": "west-sk", "name": "West", "area_km2": 1800.0}, "geometry": box(100, 100, 30000, 59900)},
        {"type": "Feature", "properties": {"id": "east-mb", "name": "East", "area_km2": 1800.0}, "geometry": box(30000, 100, 59900, 59900)},
    ]
    return {"type": "FeatureCollection", "features": feats}


@pytest.fixture
def patched(monkeypatch, tmp_path):
    """Service and downloads replaced by the synthetic world; counts fetches."""
    calls = []
    regs = synthetic_regions()
    monkeypatch.setattr(fx, "service_years", lambda: list(range(2009, 2026)))
    monkeypatch.setattr(rg, "load_regions", lambda path=None: regs)

    def fake_fetch(year, bbox, px=30, force=False):
        calls.append((year, tuple(int(v) for v in bbox)))
        return Path(f"fake_{year}_{'_'.join(str(int(v)) for v in bbox)}.tif")

    def fake_read(path):
        parts = Path(path).stem.split("_")
        year, bbox = int(parts[1]), tuple(int(v) for v in parts[2:])
        return world(year, bbox), type("T", (), {"a": 30.0, "e": -30.0})()

    monkeypatch.setattr(fx, "fetch_year", fake_fetch)
    monkeypatch.setattr(fx, "read_year", fake_read)
    monkeypatch.setattr(fx, "CACHE", tmp_path / "cache")
    return calls, regs


def test_resume_and_outputs(patched, tmp_path):
    calls, regs = patched
    out = tmp_path / "data"
    # first an interrupted run: only the first tile
    rgl.run_regions(out, None, PARAMS, tile_km=TILE_KM, workers=1, check_legend=False, area_id="t", limit=1)
    assert len(set(calls)) == len(YEARS)
    results = list((tmp_path / "cache" / rgl.RESULTS_DIR).glob("*/*.npz"))
    assert len(results) == 1
    # full run: reuses the finished tile, does the other three
    meta, index = rgl.run_regions(out, None, PARAMS, tile_km=TILE_KM, workers=2, check_legend=False, area_id="t",
                                  sensitivity=False)
    assert len(set(calls)) == 4 * len(YEARS)
    assert len(list((tmp_path / "cache" / rgl.RESULTS_DIR).glob("*/*.npz"))) == 4
    # and a third run fetches nothing
    before = len(calls)
    rgl.run_regions(out, None, PARAMS, tile_km=TILE_KM, workers=2, check_legend=False, area_id="t")
    assert len(calls) == before

    d = out / "t"
    meta = json.loads((d / "meta.json").read_text())
    assert meta["tiled"] and meta["contract_version"] == 3 and meta["regions"] == ["east-mb", "west-sk"]
    assert meta["targets"] == cl.TARGETS and "sensitivity" not in meta and "target_caveats" in meta
    index = json.loads((d / "index.json").read_text())
    assert index["area_id"] == "t" and index["cells"] == sum(t["cells"] for t in index["tiles"])
    assert {e["id"] for e in index["region_summary"]} == {"east-mb", "west-sk"}
    for t in index["tiles"]:
        tile = json.loads((d / t["file"]).read_text())
        assert len(tile["lon"]) == t["cells"] == len(tile["region"])
    assert json.loads((out / "areas.json").read_text())[0]["id"] == "t"
    summary = json.loads((d / "province_summary.json").read_text())
    assert summary["provinces"]["all"]["cells"] == index["cells"]


def test_assembled_tiles_match_the_single_file_writer(patched, tmp_path):
    """The streaming writer gives the same cells, regions and totals as tiling.write_tiles on one big cells dict."""
    _, regs = patched
    out = tmp_path / "data"
    rgl.run_regions(out, None, PARAMS, tile_km=TILE_KM, check_legend=False, area_id="t")
    index = json.loads((out / "t" / "index.json").read_text())

    big = rgl.compute_tile(0, 0, readers, YEARS, 2025, PARAMS, TARGETS, tile_km=60)
    m = big["keep"]
    cells = {"lon": big["lon"][m].tolist(), "lat": big["lat"][m].tolist(), "area_ha": big["area_ha"][m].tolist(),
             "intervals": rgl.build_intervals(big, TARGETS, m, 2025)}
    ids = rg.assign_regions(cells["lon"], cells["lat"], regs)
    ref_dir = tmp_path / "ref"
    ref, _ = tl.write_tiles(ref_dir, cells, big["x"][m], big["y"][m], ids, regs, area_id="t", tile_km=TILE_KM)
    inside = [i for i in ids if i is not None]
    assert index["cells"] == len(inside)
    ref_by = {e["id"]: e for e in ref["region_summary"]}
    for e in index["region_summary"]:
        r = ref_by[e["id"]]
        assert e["cells"] == r["cells"] and e["area_ha"] == pytest.approx(r["area_ha"], abs=0.1)
        for iv, tot in e["totals"].items():
            for c, v in tot["natural_ha"].items():
                assert v == pytest.approx(r["totals"][iv]["natural_ha"][c], abs=0.2)
            for t, by in tot["converted_ha"].items():
                for c, v in by.items():
                    assert v == pytest.approx(r["totals"][iv]["converted_ha"][t][c], abs=0.2)
    ref_tiles = {t["id"]: t["cells"] for t in ref["tiles"]}
    assert {t["id"]: t["cells"] for t in index["tiles"]} == ref_tiles


def test_region_subset_drops_other_regions(patched, tmp_path):
    _, regs = patched
    out = tmp_path / "data"
    rgl.run_regions(out, ["east-mb"], PARAMS, tile_km=TILE_KM, check_legend=False, area_id="t")
    index = json.loads((out / "t" / "index.json").read_text())
    assert [e["id"] for e in index["region_summary"]] == ["east-mb"]
    assert index["unassigned"]["cells"] == 0 and index["unassigned"]["dropped_outside_regions"] > 0
    for t in index["tiles"]:
        tile = json.loads((out / "t" / t["file"]).read_text())
        east = index["regions"].index("east-mb")
        assert set(tile["region"]) == {east}
    summary = json.loads((out / "t" / "province_summary.json").read_text())
    assert summary["coverage"]["regions_missing"] == ["west-sk"]


def test_sensitivity_block_matches_default_totals(patched, tmp_path):
    _, regs = patched
    out = tmp_path / "data"
    rgl.run_regions(out, None, PARAMS, tile_km=TILE_KM, check_legend=False, area_id="t", sensitivity=True)
    meta = json.loads((out / "t" / "meta.json").read_text())
    index = json.loads((out / "t" / "index.json").read_text())
    rows = {r["id"]: r for r in meta["sensitivity"]["settings"]}
    assert len(rows) == 8 and rows["default"]["is_default"]
    for iv, v in rows["default"]["intervals"].items():
        crop = sum(by.get("crop", {}).get(c, 0.0) for e in index["region_summary"]
                   for by in [e["totals"][iv]["converted_ha"]] for c in cl.NATURAL_CLASSES)
        nat = sum(sum(e["totals"][iv]["natural_ha"].values()) for e in index["region_summary"])
        assert v["converted_ha"] == pytest.approx(crop, rel=1e-3)
        assert v["natural_ha"] == pytest.approx(nat, rel=1e-3)
    # looser filters never convert less than the default
    assert rows["no_filter"]["intervals"]["2016-2025"]["converted_ha"] >= rows["default"]["intervals"]["2016-2025"]["converted_ha"]


def test_drop_rasters_removes_only_tile_rasters(patched, tmp_path, monkeypatch):
    calls, _ = patched
    removed = []
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: removed.append(self.name))
    rgl.run_regions(tmp_path / "data", None, PARAMS, tile_km=TILE_KM, check_legend=False, area_id="t", drop_rasters=True)
    assert len(removed) == 4 * len(YEARS) and all(n.endswith(".tif") for n in removed)


def test_cache_key_changes_with_settings():
    k = lambda **kw: rgl.cache_key(YEARS, 2025, kw.get("params", PARAMS), TARGETS, 100, kw.get("s", False), ROWS)
    assert k() == k()
    assert k() != k(params=cv.FilterParams(min_patch_ha=2.0))
    assert k() != k(s=True)
