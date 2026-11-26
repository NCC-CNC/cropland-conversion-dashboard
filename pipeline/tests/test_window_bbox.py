from cropconv import aggregate as agg
from cropconv.export_shapes import test_area_bbox
from cropconv.run import window_bbox


def test_window_bbox_covers_raster_in_whole_cells():
    bbox = test_area_bbox()
    grid, raster = window_bbox(bbox)
    assert raster == bbox
    assert grid[0] == bbox[0] and grid[3] == bbox[3]
    assert (grid[2] - grid[0]) % agg.CELL_M == 0
    assert (grid[3] - grid[1]) % agg.CELL_M == 0
    assert grid[2] >= bbox[2] and grid[1] <= bbox[1]
    assert grid[2] - bbox[2] < agg.CELL_M and bbox[1] - grid[1] < agg.CELL_M
