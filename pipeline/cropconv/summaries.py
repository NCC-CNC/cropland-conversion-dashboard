"""Province summary for a tiled area: pre-summed totals for Manitoba and Saskatchewan.

Reads the `region_summary` totals that tiling.py wrote to index.json (no tiles are
loaded), adds them up per province (region ids ending in -mb or -sk) and writes
`province_summary.json` next to the tiles. The file is self-describing: it copies
the method, source, caveats and dates from meta.json and states which regions have
been run, so partial coverage is never mistaken for a provincial total.

    python -m cropconv.summaries --area sk-mb-estevan-melville

See docs/design/05_regional_partitioning.md and docs/design/02_mvp_data_contract.md.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import regions as rg

SUMMARY_NAME = "province_summary.json"
PROVINCES = {"MB": "Manitoba", "SK": "Saskatchewan"}
ALL = "all"
# A region counts as covered when the area's cells span at least this share of its
# area. Cells with no natural cover and no conversion are not written, so cell area
# understates ground covered and the bar is below 1.
COVERED_FRACTION = 0.9
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "data"

NOTE = ("Totals add up only the farming-zone regions that have been run, over the years named in "
        "'years'. Show them as a provincial total only when the province's coverage.complete is "
        "true; otherwise label them as the covered regions only.")


def province_of(region_id: str):
    """'MB' or 'SK' from a region id such as 'aspen-parkland-sk', else None."""
    code = region_id.rsplit("-", 1)[-1].upper()
    return code if code in PROVINCES else None


def _fsum(values) -> float:
    return round(math.fsum(values), 2)


def add_totals(parts: list[dict]) -> dict:
    """Add region `totals` dicts (interval -> natural_ha / converted_ha) class by class."""
    out = {}
    for key in sorted({k for p in parts for k in p}):
        ivs = [p[key] for p in parts if key in p]
        natural = {c: _fsum(iv["natural_ha"].get(c, 0.0) for iv in ivs)
                   for c in sorted({c for iv in ivs for c in iv["natural_ha"]})}
        converted = {}
        for t in sorted({t for iv in ivs for t in iv["converted_ha"]}):
            by = [iv["converted_ha"].get(t, {}) for iv in ivs]
            converted[t] = {c: _fsum(b.get(c, 0.0) for b in by) for c in sorted({c for b in by for c in b})}
        out[key] = {"natural_ha": natural, "converted_ha": converted}
    return out


def _pct(conv: float, nat: float):
    return round(100.0 * conv / nat, 2) if nat > 0 else None


def with_percent(totals: dict) -> dict:
    """Per interval: natural_ha, converted_ha, converted_pct (target -> class) and a `total` block.

    `total` sums the natural classes (and each target over its classes); percent is
    converted over the natural hectares of the same classes, None when natural is 0.
    """
    out = {}
    for key, iv in totals.items():
        nat = iv["natural_ha"]
        nat_all = _fsum(nat.values())
        pct, tot_conv, tot_pct = {}, {}, {}
        for t, by in iv["converted_ha"].items():
            pct[t] = {c: _pct(v, nat.get(c, 0.0)) for c, v in by.items()}
            tot_conv[t] = _fsum(by.values())
            tot_pct[t] = _pct(tot_conv[t], _fsum(nat.get(c, 0.0) for c in by))
        out[key] = {
            "natural_ha": nat, "converted_ha": iv["converted_ha"], "converted_pct": pct,
            "total": {"natural_ha": nat_all, "converted_ha": tot_conv, "converted_pct": tot_pct},
        }
    return out


def _coverage_rows(entries: list[dict], areas_km2: dict, ids: list[str]) -> list[dict]:
    by_id = {e["id"]: e for e in entries}
    rows = []
    for rid in ids:
        full = areas_km2.get(rid)
        e = by_id.get(rid)
        cell_km2 = round(e["area_ha"] / 100.0, 1) if e else 0.0
        frac = round(min(1.0, cell_km2 / full), 3) if (e and full) else 0.0
        rows.append({"id": rid, "province": province_of(rid), "run": e is not None,
                     "region_area_km2": round(full, 1) if full else None,
                     "cell_area_km2": cell_km2, "fraction": frac, "covered": frac >= COVERED_FRACTION})
    return rows


def _block(rows: list[dict]) -> dict:
    full = math.fsum(r["region_area_km2"] or 0.0 for r in rows)
    got = math.fsum(min(r["cell_area_km2"], r["region_area_km2"] or 0.0) for r in rows)
    return {
        "complete": bool(rows) and all(r["covered"] for r in rows),
        "regions_total": len(rows),
        "regions_run": [r["id"] for r in rows if r["run"]],
        "regions_covered": [r["id"] for r in rows if r["covered"]],
        "regions_missing": [r["id"] for r in rows if not r["run"]],
        "regions_partial": [r["id"] for r in rows if r["run"] and not r["covered"]],
        "farming_zone_area_km2": round(full, 1),
        "covered_area_km2": round(got, 1),
        "fraction": round(got / full, 3) if full else 0.0,
    }


def _province(name: str, entries: list[dict], rows: list[dict]) -> dict:
    return {
        "name": name,
        "regions": [e["id"] for e in entries],
        "cells": sum(e["cells"] for e in entries),
        "area_ha": _fsum(e["area_ha"] for e in entries),
        "coverage": _block(rows),
        "intervals": with_percent(add_totals([e["totals"] for e in entries])),
    }


def build_summary(index: dict, meta: dict, regions: dict | None = None) -> dict:
    """The province summary dict from a tiled area's index.json and meta.json."""
    regions = regions if regions is not None else rg.load_regions()
    areas = rg.region_areas_km2(regions)
    entries = [e for e in index["region_summary"] if province_of(e["id"])]
    all_ids = sorted(i for i in areas if province_of(i))
    rows = _coverage_rows(entries, areas, all_ids)
    provinces = {}
    for code, name in PROVINCES.items():
        mine = [e for e in entries if province_of(e["id"]) == code]
        provinces[code] = _province(name, mine, [r for r in rows if r["province"] == code])
    provinces[ALL] = _province("Manitoba and Saskatchewan", entries, rows)
    un = index.get("unassigned", {"cells": 0})
    return {
        "contract_version": 3,
        "kind": "province_summary",
        "area_id": index["area_id"],
        "generated": meta.get("generated"),
        "latest": meta.get("latest"),
        "years": {"snapshots": meta.get("snapshots"), "intervals": meta.get("intervals")},
        "natural_classes": meta.get("natural_classes"),
        "targets": meta.get("targets"),
        "method": meta.get("method"),
        "source": meta.get("source"),
        "caveats": list(meta.get("caveats", [])),
        "coverage": {**_block(rows), "covered_fraction_min": COVERED_FRACTION, "regions": rows, "note": NOTE},
        "unassigned": {"cells": un.get("cells", 0), "area_ha": un.get("area_ha", 0.0),
                       "note": "Cells in no farming-zone region are left out of every total."},
        "provinces": provinces,
    }


def write_province_summary(area_dir: Path, regions: dict | None = None):
    """Write province_summary.json for a tiled area; None if it has no MB or SK region."""
    area_dir = Path(area_dir)
    index = json.loads((area_dir / "index.json").read_text(encoding="utf-8"))
    meta = json.loads((area_dir / "meta.json").read_text(encoding="utf-8"))
    if not any(province_of(e["id"]) for e in index["region_summary"]):
        return None
    summary = build_summary(index, meta, regions)
    path = area_dir / SUMMARY_NAME
    path.write_text(json.dumps(summary, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="data directory holding <area>/ (default: web/public/data)")
    a = ap.parse_args(argv)
    s = write_province_summary(a.out / a.area)
    if s is None:
        raise SystemExit(f"{a.area} has no Manitoba or Saskatchewan region; nothing written")
    c = s["coverage"]
    print(f"wrote {a.out / a.area / SUMMARY_NAME}: {len(c['regions_run'])}/{c['regions_total']} regions run, "
          f"fraction {c['fraction']:.3f}, complete={c['complete']}, unassigned cells {s['unassigned']['cells']}")


if __name__ == "__main__":
    main()
