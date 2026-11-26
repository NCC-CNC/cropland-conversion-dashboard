"""Class harmonization driven by classes.csv (version controlled).

Groups: natural, crop, pasture, urban, barren, other. Each non-natural group
that is a conversion target (crop, pasture, urban, barren) has the same name
in the `target` column of classes.csv; other codes have no target. Pasture
(ACI 122, pasture and forages) is its own group so it can be switched into
crop for sensitivity runs, but it is not crop by default. Urban (34) and
barren (30) are separate groups so every ACI code maps to one target only.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

CLASSES_CSV = Path(__file__).resolve().parent.parent / "classes.csv"
NATURAL_CLASSES = ["forest", "grassland", "wetland", "shrubland"]
GROUPS = ["other", "natural", "crop", "pasture", "urban", "barren"]
TARGETS = ["crop", "pasture", "urban", "barren"]


def load_classes(path: Path = CLASSES_CSV) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["code"] = int(r["code"])
        if r["group"] not in GROUPS:
            raise ValueError(f"bad group {r['group']!r} for code {r['code']}")
        if (r["group"] == "natural") != bool(r["natural_class"]):
            raise ValueError(f"natural_class mismatch for code {r['code']}")
        if r["natural_class"] and r["natural_class"] not in NATURAL_CLASSES:
            raise ValueError(f"bad natural class for code {r['code']}")
        target = r["target"]
        if target and target not in TARGETS:
            raise ValueError(f"bad target {target!r} for code {r['code']}")
        if target and r["group"] == "natural":
            raise ValueError(f"natural code {r['code']} cannot have a target")
        if target != (r["group"] if r["group"] in TARGETS else ""):
            raise ValueError(f"target {target!r} does not match group {r['group']!r} for code {r['code']}")
    codes = [r["code"] for r in rows]
    if len(set(codes)) != len(codes):
        raise ValueError("duplicate codes in classes.csv")
    return rows


def build_luts(rows: list[dict] | None = None):
    """Return (group_lut, natural_lut), uint8 arrays of length 256.

    group_lut[code] is an index into GROUPS (unknown codes map to other).
    natural_lut[code] is 0 for not natural, else 1 + index in NATURAL_CLASSES.
    """
    rows = rows or load_classes()
    group_lut = np.zeros(256, dtype=np.uint8)
    natural_lut = np.zeros(256, dtype=np.uint8)
    for r in rows:
        group_lut[r["code"]] = GROUPS.index(r["group"])
        if r["natural_class"]:
            natural_lut[r["code"]] = 1 + NATURAL_CLASSES.index(r["natural_class"])
    return group_lut, natural_lut


def unknown_codes(values, rows: list[dict] | None = None) -> list[int]:
    """Codes present in the data that are not in classes.csv (excluding 0 nodata)."""
    known = {r["code"] for r in (rows or load_classes())}
    return sorted(int(v) for v in set(np.unique(values).tolist()) if v != 0 and v not in known)


def check_legend_labels(service_labels: list[str], rows: list[dict] | None = None) -> list[str]:
    """Compare a service legend (labels in code order) with classes.csv.

    Returns a list of problems, empty when they agree.
    """
    rows = rows or load_classes()
    expected = [r["label"].strip() for r in sorted(rows, key=lambda r: r["code"])]
    got = [s.strip() for s in service_labels]
    problems = []
    for lab in got:
        if lab not in expected:
            problems.append(f"label not in classes.csv: {lab!r}")
    for lab in expected:
        if lab not in got:
            problems.append(f"label missing from service legend: {lab!r}")
    if not problems and got != expected:
        problems.append("labels match but order differs, so code order may have changed")
    return problems
