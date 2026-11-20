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
