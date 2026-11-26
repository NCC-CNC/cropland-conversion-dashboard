import pytest
import numpy as np

from cropconv import aggregate as agg
from cropconv import classes as cl
from cropconv import convert as cv

OTHER, NATURAL, CROP, PASTURE = (cl.GROUPS.index(g) for g in ["other", "natural", "crop", "pasture"])
PX_M2 = 900.0  # one 30 m pixel


def grid(h=12, w=12, fill=OTHER):
    return np.full((h, w), fill, dtype=np.uint8)


def block(arr, r0, r1, c0, c1, v):
    arr[r0:r1, c0:c1] = v
    return arr


def params(**kw):
    base = dict(persistence=False, min_patch_ha=0.0, majority=False, pasture_is_crop=False, exclude_prior_crop=False)
    base.update(kw)
    return cv.FilterParams(**base)


def test_basic_conversion():
    nat = np.zeros((12, 12), bool)
    nat[2:6, 2:6] = True
    latest = block(grid(), 4, 8, 4, 8, CROP)
    m = cv.conversion_mask(nat, latest, None, params(), PX_M2)
    # overlap of natural (rows/cols 2..5) and crop (4..7) is 2x2
    assert m.sum() == 4
    assert m[4:6, 4:6].all()


def test_pasture_not_crop_by_default():
    nat = np.ones((4, 4), bool)
    latest = grid(4, 4, PASTURE)
    assert cv.conversion_mask(nat, latest, None, params(), PX_M2).sum() == 0
    assert cv.conversion_mask(nat, latest, None, params(pasture_is_crop=True), PX_M2).sum() == 16


def test_persistence_removes_one_year_flip():
    nat = np.ones((6, 6), bool)
    latest = grid(6, 6, CROP)
    persist = grid(6, 6, OTHER)
    block(persist, 0, 3, 0, 6, CROP)  # only the top half also crop earlier
    m = cv.conversion_mask(nat, latest, persist, params(persistence=True), PX_M2)
    assert m.sum() == 18
    assert m[:3].all() and not m[3:].any()
    # no persistence snapshot available: filter is skipped
    assert cv.conversion_mask(nat, latest, None, params(persistence=True), PX_M2).sum() == 36


def test_min_patch_size():
    nat = np.ones((12, 12), bool)
    latest = grid()
    block(latest, 0, 1, 0, 3, CROP)    # 3 px patch
    block(latest, 5, 10, 5, 10, CROP)  # 25 px patch
    # 0.5 ha = 5000 m2 = ceil(5000 / 900) = 6 px
    m = cv.conversion_mask(nat, latest, None, params(min_patch_ha=0.5), PX_M2)
    assert m.sum() == 25
    assert not m[0].any()
    # a very small threshold keeps everything
    assert cv.conversion_mask(nat, latest, None, params(min_patch_ha=0.05), PX_M2).sum() == 28


def test_patch_connectivity_diagonal():
    mask = np.zeros((6, 6), bool)
    for i in range(6):
        mask[i, i] = True
    assert cv.filter_patches(mask, 6, eight_connected=True).sum() == 6
    assert cv.filter_patches(mask, 6, eight_connected=False).sum() == 0


def test_majority_filter_removes_thin_lines():
    mask = np.zeros((9, 9), bool)
    mask[1:8, 1:8] = True   # solid block survives in its interior
    mask[4, 0] = True       # a stray pixel at the edge is removed
    out = cv.majority_filter(mask)
    assert not out[4, 0]
    assert out[4, 4]
    line = np.zeros((9, 9), bool)
    line[4, :] = True
    assert cv.majority_filter(line).sum() == 0


def test_conversion_requires_natural_baseline():
    nat = np.zeros((4, 4), bool)
    latest = grid(4, 4, CROP)
    assert cv.conversion_mask(nat, latest, None, params(), PX_M2).sum() == 0


def test_persistence_year_choice():
    assert cv.persistence_year(2011, 2025, [2011, 2016, 2021, 2024, 2025]) == 2024
    assert cv.persistence_year(2021, 2025, [2011, 2016, 2021, 2025]) is None
    assert cv.persistence_year(2011, 2024, [2011, 2016, 2021, 2024]) == 2021


def test_clean_baseline_drops_prior_crop():
    nat_idx = np.ones((4, 4), dtype=np.uint8)
    earlier = [block(grid(4, 4), 0, 2, 0, 4, CROP)]
    out = cv.clean_baseline(nat_idx, earlier, cv.FilterParams())
    assert out[:2].sum() == 0 and out[2:].all()
    assert cv.clean_baseline(nat_idx, [], cv.FilterParams()).all()  # no earlier snapshot
    assert cv.clean_baseline(nat_idx, earlier, cv.FilterParams(exclude_prior_crop=False)).all()


def test_aggregation_by_cell_and_class():
    # 4 x 4 px, 2 px cells would be 2 x 2 cells; use CELL_M = 1000 with px = 500
    shape = (4, 4)
    cells = agg.pixel_cells(shape, x_left=0.0, y_top_raster=2000.0, y_top_grid=2000.0, px=500.0, n_cols=2, n_rows=2)
    assert cells.tolist() == [[0, 0, 1, 1], [0, 0, 1, 1], [2, 2, 3, 3], [2, 2, 3, 3]]
    natural = np.zeros(shape, dtype=np.uint8)
    natural[:2, :2] = 2          # grassland in cell 0
    natural[2:, 2:] = 3          # wetland in cell 3
    conv = np.zeros(shape, bool)
    conv[0, 0] = True
    nat_c = agg.natural_counts(natural, cells, 4)
    conv_c = agg.converted_counts(natural, conv, cells, 4)
    assert nat_c["grassland"].tolist() == [4, 0, 0, 0]
    assert nat_c["wetland"].tolist() == [0, 0, 0, 4]
    assert conv_c["grassland"].tolist() == [1, 0, 0, 0]
    assert conv_c["wetland"].sum() == 0


def test_pixels_outside_grid_are_ignored():
    cells = agg.pixel_cells((2, 3), 0.0, 1000.0, 1000.0, 500.0, n_cols=1, n_rows=1)
    assert cells.tolist() == [[0, 0, -1], [0, 0, -1]]


# ---- conversion targets ---------------------------------------------------------

URBAN, BARREN = (cl.GROUPS.index(g) for g in ["urban", "barren"])


def stack():
    """Synthetic 6 x 6 stack (baseline natural everywhere; same latest and persistence class per column).

    Columns 0-1 flip natural to crop, 2-3 natural to pasture, 4 natural to urban, 5 natural to barren.
    """
    nat = np.ones((6, 6), bool)
    latest = grid(6, 6)
    for cols, g in [((0, 2), CROP), ((2, 4), PASTURE), ((4, 5), URBAN), ((5, 6), BARREN)]:
        latest[:, cols[0]:cols[1]] = g
    return nat, latest.copy(), latest.copy()


def test_masks_are_disjoint_and_cover_flips():
    nat, latest, persist = stack()
    masks = cv.conversion_masks(nat, latest, persist, params(persistence=True), PX_M2)
    assert list(masks) == cl.TARGETS
    total = sum(m.astype(int) for m in masks.values())
    assert total.max() == 1  # no cell in two targets
    assert masks["crop"][:, 0:2].all() and masks["crop"].sum() == 12
    assert masks["pasture"][:, 2:4].all() and masks["pasture"].sum() == 12
    assert masks["urban"][:, 4].all() and masks["urban"].sum() == 6
    assert masks["barren"][:, 5].all() and masks["barren"].sum() == 6


def test_masks_disjoint_on_random_stack():
    rng = np.random.default_rng(0)
    latest = rng.integers(0, len(cl.GROUPS), size=(40, 40)).astype(np.uint8)
    nat = rng.random((40, 40)) > 0.3
    for pic in (False, True):
        masks = cv.conversion_masks(nat, latest, latest, params(persistence=True, pasture_is_crop=pic), PX_M2)
        assert sum(m.astype(int) for m in masks.values()).max() <= 1


def test_same_filters_run_per_target():
    nat = np.ones((12, 12), bool)
    latest = grid()
    block(latest, 0, 1, 0, 3, URBAN)      # 3 px urban patch is dropped
    block(latest, 5, 10, 5, 10, URBAN)    # 25 px kept
    block(latest, 0, 1, 6, 9, PASTURE)    # 3 px pasture patch dropped
    masks = cv.conversion_masks(nat, latest, None, params(min_patch_ha=0.5), PX_M2)
    assert masks["urban"].sum() == 25 and masks["pasture"].sum() == 0


def test_persistence_is_per_target():
    # natural, then crop, then pasture: pasture only if the persistence year is also pasture
    nat = np.ones((4, 4), bool)
    latest = grid(4, 4, PASTURE)
    m = cv.conversion_masks(nat, latest, grid(4, 4, CROP), params(persistence=True), PX_M2)
    assert m["pasture"].sum() == 0 and m["crop"].sum() == 0
    m = cv.conversion_masks(nat, latest, grid(4, 4, PASTURE), params(persistence=True), PX_M2)
    assert m["pasture"].sum() == 16 and m["crop"].sum() == 0


def test_pasture_is_crop_only_changes_crop():
    nat = np.ones((4, 4), bool)
    m = cv.conversion_masks(nat, grid(4, 4, PASTURE), None, params(pasture_is_crop=True), PX_M2)
    assert m["crop"].sum() == 16
    assert m["pasture"].sum() == 0  # no double counting in the sensitivity mode
    m = cv.conversion_masks(nat, grid(4, 4, URBAN), None, params(pasture_is_crop=True), PX_M2)
    assert m["urban"].sum() == 16 and m["crop"].sum() == 0


def test_conversion_mask_default_target_is_crop():
    nat, latest, _ = stack()
    assert (cv.conversion_mask(nat, latest, None, params(), PX_M2)
            == cv.conversion_masks(nat, latest, None, params(), PX_M2)["crop"]).all()


def test_unknown_target():
    with pytest.raises(ValueError):
        cv.is_target(grid(2, 2), "greenhouse", params())


def test_baseline_exclusion_rules():
    nat_idx = np.ones((4, 4), dtype=np.uint8)
    for earlier_group, dropped_by_default in [(CROP, True), (PASTURE, False), (URBAN, False), (BARREN, False)]:
        earlier = [block(grid(4, 4), 0, 2, 0, 4, earlier_group)]
        out = cv.clean_baseline(nat_idx, earlier, cv.FilterParams())
        assert (out[:2].sum() == 0) == dropped_by_default, cl.GROUPS[earlier_group]
        # switch on: pasture and urban also remove the cell, barren never does
        out = cv.clean_baseline(nat_idx, earlier, cv.FilterParams(exclude_prior_pasture_urban=True))
        assert (out[:2].sum() == 0) == (earlier_group != BARREN), cl.GROUPS[earlier_group]
        # all switches off: nothing removed
        off = cv.FilterParams(exclude_prior_crop=False, exclude_prior_pasture_urban=False)
        assert cv.clean_baseline(nat_idx, earlier, off).all()


def test_prior_pasture_switch_without_crop_switch():
    nat_idx = np.ones((4, 4), dtype=np.uint8)
    earlier = [block(grid(4, 4), 0, 2, 0, 4, CROP), block(grid(4, 4), 2, 4, 0, 4, PASTURE)]
    p = cv.FilterParams(exclude_prior_crop=False, exclude_prior_pasture_urban=True)
    out = cv.clean_baseline(nat_idx, earlier, p)
    assert out[:2].all() and out[2:].sum() == 0


def test_crop_mask_unchanged_by_other_targets():
    """Crop output must not depend on which other targets are computed."""
    nat, latest, persist = stack()
    p = params(persistence=True)
    only = cv.conversion_masks(nat, latest, persist, p, PX_M2, ["crop"])["crop"]
    assert (only == cv.conversion_masks(nat, latest, persist, p, PX_M2)["crop"]).all()
