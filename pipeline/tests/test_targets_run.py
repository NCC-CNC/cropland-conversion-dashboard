"""Target handling in run.py: a synthetic stack through interval_masks and aggregation, and caveats."""
import json

import numpy as np

from cropconv import aggregate as agg
from cropconv import classes as cl
from cropconv import convert as cv
from cropconv import run as rn

OTHER, NATURAL, CROP, PASTURE, URBAN, BARREN = (
    cl.GROUPS.index(g) for g in ["other", "natural", "crop", "pasture", "urban", "barren"]
)
PX_M2 = 900.0


def synthetic_stack():
    """One cell per row of 6 px: natural in 2011 and 2016, flips in 2024/2025 by column pair."""
    shape = (6, 6)
    nat_idx = np.full(shape, 2, dtype=np.uint8)  # grassland
    base = np.full(shape, NATURAL, dtype=np.uint8)
    late = np.full(shape, OTHER, dtype=np.uint8)
    for cols, g in [((0, 2), CROP), ((2, 4), PASTURE), ((4, 5), URBAN), ((5, 6), BARREN)]:
        late[:, cols[0]:cols[1]] = g
    groups = {2011: base, 2016: base, 2021: late.copy(), 2024: late.copy(), 2025: late.copy()}
    naturals = {2011: nat_idx, 2016: nat_idx, 2021: np.zeros(shape, np.uint8), 2024: np.zeros(shape, np.uint8), 2025: np.zeros(shape, np.uint8)}
    return groups, naturals


def test_interval_masks_flips_by_target():
    groups, naturals = synthetic_stack()
    p = cv.FilterParams(min_patch_ha=0.0)
    res = rn.interval_masks(groups, naturals, 2025, p, PX_M2, [2011, 2016, 2021, 2024, 2025])
    for b in (2011, 2016):
        nat, conv, py = res[b]
        assert py == 2024
        assert list(conv) == cl.TARGETS
        assert [int(conv[t].sum()) for t in cl.TARGETS] == [12, 12, 6, 6]
        assert sum(m.astype(int) for m in conv.values()).max() == 1


def test_converted_counts_per_target_sum_to_natural():
    groups, naturals = synthetic_stack()
    p = cv.FilterParams(min_patch_ha=0.0)
    res = rn.interval_masks(groups, naturals, 2025, p, PX_M2, [2011, 2016, 2021, 2024, 2025])
    nat, conv, _ = res[2011]
    cells = np.zeros((6, 6), dtype=np.int64)  # all pixels in one cell
    per_target = {t: agg.converted_counts(nat, conv[t], cells, 1)["grassland"][0] for t in cl.TARGETS}
    assert per_target == {"crop": 12, "pasture": 12, "urban": 6, "barren": 6}
    assert sum(per_target.values()) == agg.natural_counts(nat, cells, 1)["grassland"][0]


def test_prior_pasture_exclusion_on_stack():
    groups, naturals = synthetic_stack()
    groups[2011] = groups[2011].copy()
    groups[2011][:, 2:4] = PASTURE  # earlier pasture where 2016 says natural and 2025 says pasture
    avail = [2011, 2016, 2021, 2024, 2025]
    off = rn.interval_masks(groups, naturals, 2025,
                            cv.FilterParams(min_patch_ha=0.0, exclude_prior_pasture_urban=False), PX_M2, avail)
    on = rn.interval_masks(groups, naturals, 2025, cv.FilterParams(min_patch_ha=0.0), PX_M2, avail)
    assert off[2016][1]["pasture"].sum() == 12 and on[2016][1]["pasture"].sum() == 0
    assert off[2016][1]["crop"].sum() == on[2016][1]["crop"].sum() == 12  # crop figure unaffected here
    assert (on[2016][0][:, 2:4] == 0).all() and (on[2016][0][:, :2] > 0).all()


def test_caveats_crop_only_is_unchanged():
    assert rn.build_caveats(["crop"]) == rn.CAVEATS


def test_target_caveats_keyed_by_present_target():
    assert rn.build_target_caveats(["crop"]) == {}
    t = rn.build_target_caveats(["crop", "urban", "barren"])
    assert t == {"urban": rn.TARGET_CAVEATS["urban"], "barren": rn.TARGET_CAVEATS["barren"]}
    assert all(v in rn.build_caveats(["crop", "urban", "barren"]) for v in t.values())


def test_caveats_only_for_present_targets():
    c = rn.build_caveats(["crop", "urban"])
    assert rn.TARGET_CAVEATS["urban"] in c
    assert rn.TARGET_CAVEATS["pasture"] not in c and rn.TARGET_CAVEATS["barren"] not in c
    c = rn.build_caveats(cl.TARGETS)
    assert all(rn.TARGET_CAVEATS[t] in c for t in ("pasture", "urban", "barren"))
    # the crop-only statements that would now be wrong are replaced
    assert rn.CAVEATS[4] not in c and rn.CAVEATS[3] not in c
    assert all(chr(0x2014) not in s for s in c)


def test_caveat_wording_is_verbatim_from_design_note():
    note = (rn.REPO / "docs" / "design" / "04_conversion_targets.md").read_text(encoding="utf-8")
    flat = " ".join(note.split())
    for text in rn.TARGET_CAVEATS.values():
        assert f'"{text}"' in flat


def test_method_text_names_targets():
    p = cv.FilterParams()
    crop_only = rn.describe_method(2025, p, {2011: 2024})
    multi = rn.describe_method(2025, p, {2011: 2024}, cl.TARGETS)
    assert "pasture and forage (122)" in multi and "one target only" in multi
    assert "one target only" not in crop_only
    assert chr(0x2014) not in multi


def test_contract_version_constant_and_json_roundtrip():
    assert rn.CONTRACT_VERSION == 2
    assert json.loads(json.dumps({"targets": cl.TARGETS}))["targets"] == cl.TARGETS


def test_method_text_states_prior_pasture_urban_rule_only_when_on():
    persist = {2011: 2016}
    on = rn.describe_method(2025, cv.FilterParams(), persist, cl.TARGETS)
    assert "mapped as pasture or forage or urban in an earlier snapshot" in on
    assert "lower than in earlier versions of this dashboard" in on
    off = rn.describe_method(2025, cv.FilterParams(exclude_prior_pasture_urban=False), persist, cl.TARGETS)
    assert "pasture or forage or urban" not in off and "earlier versions" not in off
    crop_on = rn.describe_method(2025, cv.FilterParams(), persist)
    assert "pasture or forage or urban" in crop_on
    assert "pasture or forage or urban" not in rn.describe_method(
        2025, cv.FilterParams(exclude_prior_pasture_urban=False), persist)


def test_sensitivity_rows_ordering_and_json():
    groups, naturals = synthetic_stack()
    avail = [2011, 2016, 2021, 2024, 2025]
    rows = rn.sensitivity_rows(groups, naturals, 2025, avail, PX_M2, cv.FilterParams(min_patch_ha=0.0))
    assert [r["id"] for r in rows] == [p[0] for p in rn.PRESETS]
    assert sum(r["is_default"] for r in rows) == 1
    by = {r["id"]: r["intervals"]["2011-2025"] for r in rows}
    assert set(rows[0]["intervals"]) == {"2011-2025", "2016-2025", "2021-2025"}
    # looser filters never convert less than the default, and the default is positive here
    assert by["no_filter"]["converted_ha"] >= by["persistence"]["converted_ha"] >= by["default"]["converted_ha"]
    assert by["default"]["converted_ha"] > 0
    assert by["pasture_as_crop"]["converted_ha"] >= by["default"]["converted_ha"]
    assert 0 < by["default"]["percent"] <= 100
    meta = rn.sensitivity_meta(rows)
    assert json.loads(json.dumps(meta)) == meta
    assert "\u2014" not in json.dumps(meta, ensure_ascii=False)
