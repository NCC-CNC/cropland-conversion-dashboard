import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cropconv import summaries as sm

CLASSES = ["forest", "grassland"]


def regions():
    def f(rid, km2):
        return {"type": "Feature", "properties": {"id": rid, "area_km2": km2}, "geometry": None}
    return {"type": "FeatureCollection", "features": [
        f("a-mb", 1000.0), f("b-mb", 500.0), f("c-sk", 2000.0), f("d-sk", 1000.0)]}


def totals(nat_f, nat_g, crop_f, crop_g, urban_g):
    return {"2016-2025": {
        "natural_ha": {"forest": nat_f, "grassland": nat_g},
        "converted_ha": {"crop": {"forest": crop_f, "grassland": crop_g}, "urban": {"grassland": urban_g}},
    }}


def entry(rid, cells, area_ha, tot):
    return {"id": rid, "name": rid, "cells": cells, "area_ha": area_ha, "tiles": ["0_0"], "totals": tot}


def index(entries, unassigned=None):
    return {"area_id": "t", "region_summary": entries, "unassigned": unassigned or {"cells": 0}}


META = {"generated": "2026-11-26", "latest": 2025, "snapshots": [2016, 2025], "natural_classes": CLASSES,
        "targets": ["crop", "urban"], "intervals": [{"from": 2016, "to": 2025, "years": 9}],
        "method": "Method text.", "source": "AAFC", "caveats": ["One caveat."]}


def partial():
    return index([
        entry("a-mb", 1000, 100000.0, totals(100.0, 900.0, 10.0, 90.0, 1.0)),  # full 1000 km2
        entry("c-sk", 500, 50000.0, totals(200.0, 300.0, 20.0, 30.0, 2.0)),  # 500 of 2000 km2
    ], {"cells": 7, "area_ha": 700.0})


def test_province_sums_and_percent():
    s = sm.build_summary(partial(), META, regions())
    mb = s["provinces"]["MB"]["intervals"]["2016-2025"]
    assert mb["natural_ha"] == {"forest": 100.0, "grassland": 900.0}
    assert mb["converted_ha"]["crop"] == {"forest": 10.0, "grassland": 90.0}
    assert mb["converted_pct"]["crop"] == {"forest": 10.0, "grassland": 10.0}
    assert mb["total"]["natural_ha"] == 1000.0
    assert mb["total"]["converted_ha"]["crop"] == 100.0
    assert mb["total"]["converted_pct"]["crop"] == 10.0
    assert mb["total"]["converted_pct"]["urban"] == pytest.approx(0.11)  # 1 of 900 ha grassland
    sk = s["provinces"]["SK"]
    assert sk["cells"] == 500 and sk["regions"] == ["c-sk"]
    both = s["provinces"]["all"]["intervals"]["2016-2025"]
    assert both["natural_ha"]["forest"] == 300.0
    assert both["converted_ha"]["crop"]["grassland"] == 120.0
    assert s["provinces"]["all"]["cells"] == 1500
    assert s["unassigned"] == {"cells": 7, "area_ha": 700.0, "note": s["unassigned"]["note"]}


def test_partial_coverage_is_flagged():
    s = sm.build_summary(partial(), META, regions())
    c = s["coverage"]
    assert c["complete"] is False
    assert c["regions_run"] == ["a-mb", "c-sk"]
    assert c["regions_missing"] == ["b-mb", "d-sk"]
    assert c["regions_partial"] == ["c-sk"]
    assert c["farming_zone_area_km2"] == 4500.0
    assert c["covered_area_km2"] == 1500.0
    assert c["fraction"] == pytest.approx(1500 / 4500, abs=1e-3)
    assert s["provinces"]["MB"]["coverage"]["complete"] is False  # b-mb not run
    assert s["provinces"]["SK"]["coverage"]["fraction"] == pytest.approx(500 / 3000, abs=1e-3)
    rows = {r["id"]: r for r in c["regions"]}
    assert rows["a-mb"]["covered"] and not rows["c-sk"]["covered"] and not rows["b-mb"]["run"]


def test_complete_coverage():
    full = index([
        entry("a-mb", 1000, 100000.0, totals(1, 1, 0, 0, 0)), entry("b-mb", 500, 50000.0, totals(1, 1, 0, 0, 0)),
        entry("c-sk", 2000, 200000.0, totals(1, 1, 0, 0, 0)), entry("d-sk", 950, 95000.0, totals(1, 1, 0, 0, 0)),
    ])
    s = sm.build_summary(full, META, regions())
    assert s["coverage"]["complete"] is True
    assert s["provinces"]["SK"]["coverage"]["complete"] is True
    assert s["coverage"]["regions_missing"] == []


def test_zero_natural_gives_null_percent():
    idx = index([entry("a-mb", 1, 100.0, totals(0.0, 0.0, 0.0, 0.0, 0.0))])
    iv = sm.build_summary(idx, META, regions())["provinces"]["MB"]["intervals"]["2016-2025"]
    assert iv["converted_pct"]["crop"]["forest"] is None
    assert iv["total"]["converted_pct"]["crop"] is None


def test_other_regions_ignored_and_no_prairie_region_writes_nothing(tmp_path):
    idx = index([entry("zzz-bc", 5, 500.0, totals(1, 1, 0, 0, 0))])
    (tmp_path / "index.json").write_text(json.dumps(idx))
    (tmp_path / "meta.json").write_text(json.dumps(META))
    assert sm.write_province_summary(tmp_path, regions()) is None
    assert not (tmp_path / sm.SUMMARY_NAME).exists()


# ---- schema validation (small hand-rolled checker, no extra dependency)

NUM = (int, float)
PCT_MAP = {"*": {"*": (type(None),) + NUM}}


def check(node, spec, path="$"):
    """spec: a type or tuple of types, a dict of required keys, {'*': spec} for any key, or [spec]."""
    if isinstance(spec, dict):
        assert isinstance(node, dict), f"{path} is not an object"
        if "*" in spec:
            for k, v in node.items():
                check(v, spec["*"], f"{path}.{k}")
        else:
            for k, sub in spec.items():
                assert k in node, f"{path} lacks {k}"
                check(node[k], sub, f"{path}.{k}")
    elif isinstance(spec, list):
        assert isinstance(node, list), f"{path} is not an array"
        for i, v in enumerate(node):
            check(v, spec[0], f"{path}[{i}]")
    else:
        types = spec if isinstance(spec, tuple) else (spec,)
        assert isinstance(node, types) and not (isinstance(node, bool) and bool not in types), f"{path} has type {type(node).__name__}"


COVERAGE = {"complete": bool, "regions_total": int, "regions_run": [str], "regions_covered": [str],
            "regions_missing": [str], "regions_partial": [str], "farming_zone_area_km2": NUM,
            "covered_area_km2": NUM, "fraction": NUM}
SCHEMA = {
    "contract_version": int, "kind": str, "area_id": str, "generated": str, "latest": int,
    "years": {"snapshots": [int], "intervals": [{"from": int, "to": int, "years": int}]},
    "natural_classes": [str], "targets": [str], "method": str, "source": str, "caveats": [str],
    "coverage": {**COVERAGE, "covered_fraction_min": NUM, "note": str,
                 "regions": [{"id": str, "province": str, "run": bool, "region_area_km2": NUM,
                              "cell_area_km2": NUM, "fraction": NUM, "covered": bool}]},
    "unassigned": {"cells": int, "area_ha": NUM, "note": str},
    "provinces": {"*": {
        "name": str, "regions": [str], "cells": int, "area_ha": NUM, "coverage": COVERAGE,
        "intervals": {"*": {
            "natural_ha": {"*": NUM}, "converted_ha": {"*": {"*": NUM}},
            "converted_pct": PCT_MAP,
            "total": {"natural_ha": NUM, "converted_ha": {"*": NUM}, "converted_pct": {"*": (type(None),) + NUM}},
        }},
    }},
}


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def test_schema_and_no_em_dashes(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps(partial()))
    (tmp_path / "meta.json").write_text(json.dumps(META))
    sm.write_province_summary(tmp_path, regions())
    s = json.loads((tmp_path / sm.SUMMARY_NAME).read_text(encoding="utf-8"))
    check(s, SCHEMA)
    assert set(s["provinces"]) == {"MB", "SK", "all"}
    for text in strings(s):
        assert "\u2014" not in text and "\u2013" not in text
    # the self-describing fields are copied from meta
    assert s["method"] == META["method"] and s["caveats"] == META["caveats"] and s["generated"] == META["generated"]


def test_schema_checker_rejects_bad_shape():
    with pytest.raises(AssertionError):
        check({"kind": 1}, {"kind": str})
