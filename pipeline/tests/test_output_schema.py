"""Schema checks for the produced JSON under web/public/data (the data contract)."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
CLASSES = ["forest", "grassland", "wetland", "shrubland"]
TARGETS = ["crop", "pasture", "urban", "barren"]
TOL = 0.011  # rounding to 2 decimals


def area_dirs():
    areas_file = DATA / "areas.json"
    if not areas_file.exists():
        pytest.skip("no generated data; run python -m cropconv.run first")
    # The web app ships a synthetic demo fixture that the pipeline does not
    # produce; it is not held to the pipeline's output checks.
    areas = json.loads(areas_file.read_text(encoding="utf-8"))
    return [DATA / a["id"] for a in areas if "fixture" not in a["id"]]


def all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_strings(v)


@pytest.fixture(scope="module", params=[0], ids=["areas"])
def dirs(request):
    return area_dirs()


def test_areas_file(dirs):
    areas = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))
    assert areas
    for a in areas:
        assert set(a) == {"id", "name", "bbox"}
        w, s, e, n = a["bbox"]
        assert w < e and s < n
        assert (DATA / a["id"] / "meta.json").exists()
        d = DATA / a["id"]
        assert (d / "cells.json").exists() or (d / "index.json").exists()  # tiled areas have no cells.json


def converted_by_target(meta, iv):
    """Normalise converted_ha to {target: {class: array}}; a flat (version 1) file is crop only."""
    conv = iv["converted_ha"]
    if "targets" not in meta:
        assert set(conv) == set(CLASSES), "flat converted_ha must have every class"
        return {"crop": conv}
    assert set(conv) <= set(meta["targets"])
    return conv


def check_area(meta, cells, area_id):
    """Validate one area's meta and cells against the data contract (flat v1 and nested v2)."""
    for k in ["area_id", "name", "bbox", "cell_size_m", "snapshots", "latest", "natural_classes",
              "intervals", "method", "source", "generated", "caveats"]:
        assert k in meta, k
    assert meta["area_id"] == area_id
    assert meta["natural_classes"] == CLASSES
    assert meta["latest"] == meta["snapshots"][-1] == max(meta["snapshots"])
    assert isinstance(meta["caveats"], list) and meta["caveats"]
    if "sensitivity" in meta:  # optional, additive (contract version 2 and 3)
        sens = meta["sensitivity"]
        assert sens["target"] == "crop" and sens["settings"]
        assert sum(1 for r in sens["settings"] if r["is_default"]) == 1
        for r in sens["settings"]:
            assert set(r["intervals"]) <= {f"{i['from']}-{i['to']}" for i in meta["intervals"]}
            for v in r["intervals"].values():
                assert v["converted_ha"] >= 0 and v["natural_ha"] >= 0 and 0 <= v["percent"] <= 100
    if "targets" in meta:
        assert meta["targets"] and set(meta["targets"]) <= set(TARGETS)
        assert "crop" in meta["targets"]
        assert isinstance(meta["contract_version"], int) and meta["contract_version"] >= 2

    keys = [f"{i['from']}-{i['to']}" for i in meta["intervals"]]
    assert set(keys) == set(cells["intervals"])
    for i in meta["intervals"]:
        assert i["to"] == meta["latest"] and i["years"] == i["to"] - i["from"]

    n = len(cells["lon"])
    assert n > 0
    assert len(cells["lat"]) == n and len(cells["area_ha"]) == n
    w, s, e, nn = meta["bbox"]
    assert all(w <= x <= e for x in cells["lon"])
    assert all(s <= y <= nn for y in cells["lat"])
    assert all(a > 0 for a in cells["area_ha"])

    for key, iv in cells["intervals"].items():
        assert set(iv) == {"natural_ha", "converted_ha"}
        for c in CLASSES:
            assert len(iv["natural_ha"][c]) == n and min(iv["natural_ha"][c]) >= 0
        by_target = converted_by_target(meta, iv)
        for t, by_class in by_target.items():
            assert set(by_class) <= set(CLASSES)
            for c, conv in by_class.items():  # a missing class means all zero
                nat = iv["natural_ha"][c]
                assert len(conv) == n and min(conv) >= 0
                assert all(cv <= nv + TOL for nv, cv in zip(nat, conv)), f"{key} {t} {c}: converted > natural"
        # targets are disjoint, so across targets a class cannot convert more than it has
        for c in CLASSES:
            for j in range(n):
                tot = sum(by_class[c][j] for by_class in by_target.values() if c in by_class)
                assert tot <= iv["natural_ha"][c][j] + TOL, f"{key} {c} cell {j}: targets overlap"
        total_nat = [sum(iv["natural_ha"][c][j] for c in CLASSES) for j in range(n)]
        assert all(t <= a + 0.05 for t, a in zip(total_nat, cells["area_ha"])), "natural exceeds cell area"


def cell_files(d, meta):
    if meta.get("tiled"):
        files = sorted((d / "tiles").glob("*.json"))
        assert files and len(files) == len(json.loads((d / "index.json").read_text(encoding="utf-8"))["tiles"])
        return files
    return [d / "cells.json"]


def test_meta_and_cells(dirs):
    for d in dirs:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        for f in cell_files(d, meta):  # one cells.json, or every tile of a tiled area
            cells = json.loads(f.read_text(encoding="utf-8"))
            check_area(meta, cells, d.name)
            assert f.stat().st_size < 10_000_000


def synthetic(nested):
    meta = {
        "area_id": "syn", "name": "Synthetic", "bbox": [-1.0, -1.0, 1.0, 1.0], "cell_size_m": 1000,
        "snapshots": [2011, 2016, 2025], "latest": 2025, "natural_classes": CLASSES,
        "intervals": [{"from": 2011, "to": 2025, "years": 14}], "method": "m", "source": "s",
        "generated": "2026-11-26", "caveats": ["c"],
    }
    nat = {c: [10.0, 5.0] for c in CLASSES}
    if nested:
        meta.update({"targets": ["crop", "pasture"], "contract_version": 2})
        conv = {"crop": {"grassland": [2.0, 0.0]}, "pasture": {"grassland": [3.0, 1.0], "forest": [1.0, 0.0]}}
    else:
        conv = {c: [1.0, 0.0] for c in CLASSES}
    cells = {"lon": [0.0, 0.5], "lat": [0.0, 0.5], "area_ha": [100.0, 100.0],
             "intervals": {"2011-2025": {"natural_ha": nat, "converted_ha": conv}}}
    return meta, cells


def test_old_flat_files_still_validate():
    meta, cells = synthetic(nested=False)
    assert "targets" not in meta
    check_area(meta, cells, "syn")
    assert set(converted_by_target(meta, cells["intervals"]["2011-2025"])) == {"crop"}


def test_nested_files_validate_and_zero_arrays_may_be_omitted():
    meta, cells = synthetic(nested=True)
    check_area(meta, cells, "syn")


def test_overlapping_targets_are_rejected():
    meta, cells = synthetic(nested=True)
    cells["intervals"]["2011-2025"]["converted_ha"]["crop"]["grassland"] = [9.0, 0.0]  # 9 + 3 > 10
    with pytest.raises(AssertionError):
        check_area(meta, cells, "syn")


def test_unknown_target_is_rejected():
    meta, cells = synthetic(nested=True)
    meta["targets"] = ["crop", "greenhouse"]
    with pytest.raises(AssertionError):
        check_area(meta, cells, "syn")


def test_no_em_dashes(dirs):
    for d in dirs:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        extra = [d / "index.json", d / "province_summary.json"] if meta.get("tiled") else []
        for f in [d / "meta.json"] + extra + cell_files(d, meta):
            if f.exists():
                assert chr(0x2014) not in f.read_text(encoding="utf-8")
        assert not any(chr(0x2014) in s for s in all_strings(meta))
