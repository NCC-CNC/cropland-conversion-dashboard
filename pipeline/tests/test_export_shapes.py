from cropconv import export_shapes as ex


def test_bbox_is_pixel_aligned_and_contains_corners():
    x0, y0, x1, y1 = ex.test_area_bbox()
    assert all(v % 30 == 0 for v in (x0, y0, x1, y1))
    assert x1 > x0 and y1 > y0


def test_rings_follow_shapefile_orientation():
    outer_ccw = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
    hole_cw = [(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]
    rings = ex._shp_rings({"coordinates": [outer_ccw, hole_cw]})
    assert ex._signed_area(rings[0][:-1]) < 0  # outer clockwise
    assert ex._signed_area(rings[1][:-1]) > 0  # hole counter-clockwise
    assert all(r[0] == r[-1] for r in rings)
