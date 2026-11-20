"""Schema checks for the produced JSON under web/public/data (the data contract)."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
CLASSES = ["forest", "grassland", "wetland", "shrubland"]
TOL = 0.011  # rounding to 2 decimals


def area_dirs():
    areas_file = DATA / "areas.json"
    if not areas_file.exists():
        pytest.skip("no generated data; run python -m cropconv.run first")
    return [DATA / a["id"] for a in json.loads(areas_file.read_text(encoding="utf-8"))]


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
        assert (DATA / a["id"] / "cells.json").exists()


def test_meta_and_cells(dirs):
    for d in dirs:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        cells = json.loads((d / "cells.json").read_text(encoding="utf-8"))
        for k in ["area_id", "name", "bbox", "cell_size_m", "snapshots", "latest", "natural_classes",
                  "intervals", "method", "source", "generated", "caveats"]:
            assert k in meta, k
        assert meta["area_id"] == d.name
        assert meta["natural_classes"] == CLASSES
        assert meta["latest"] == meta["snapshots"][-1] == max(meta["snapshots"])
        assert isinstance(meta["caveats"], list) and meta["caveats"]

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
                nat, conv = iv["natural_ha"][c], iv["converted_ha"][c]
                assert len(nat) == n and len(conv) == n
                assert min(nat) >= 0 and min(conv) >= 0
                assert all(cv <= nv + TOL for nv, cv in zip(nat, conv)), f"{key} {c}: converted > natural"
            total_nat = [sum(iv["natural_ha"][c][j] for c in CLASSES) for j in range(n)]
            assert all(t <= a + 0.05 for t, a in zip(total_nat, cells["area_ha"])), "natural exceeds cell area"
            # cells are only kept when something natural exists somewhere in the area
        assert (d / "cells.json").stat().st_size < 5_000_000


def test_no_em_dashes(dirs):
    for d in dirs:
        for name in ["meta.json", "cells.json"]:
            assert chr(0x2014) not in (d / name).read_text(encoding="utf-8")
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        assert not any(chr(0x2014) in s for s in all_strings(meta))
