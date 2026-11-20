"""Aggregate pixel results onto a metric 1 km grid and build contract JSON."""
from __future__ import annotations

import numpy as np

from .classes import NATURAL_CLASSES

CELL_M = 1000


def pixel_cells(shape, x_left, y_top_raster, y_top_grid, px, n_cols, n_rows):
    """Flat grid cell index for every pixel, by pixel centre.

    Cells are numbered from the top left of the grid, whose top edge is
    y_top_grid. Pixels whose centre falls outside the grid get -1.
    """
    h, w = shape
    xc = x_left + (np.arange(w) + 0.5) * px
    yc = y_top_raster - (np.arange(h) + 0.5) * px
    col = np.floor((xc - x_left) / CELL_M).astype(np.int64)
    row = np.floor((y_top_grid - yc) / CELL_M).astype(np.int64)
    col_ok = (col >= 0) & (col < n_cols)
    row_ok = (row >= 0) & (row < n_rows)
    idx = row[:, None] * n_cols + col[None, :]
    ok = row_ok[:, None] & col_ok[None, :]
    return np.where(ok, idx, -1)


def sum_by_cell(values_mask: np.ndarray, cells: np.ndarray, n_cells: int) -> np.ndarray:
    """Count of True pixels per cell."""
    sel = values_mask & (cells >= 0)
    return np.bincount(cells[sel], minlength=n_cells)


def natural_counts(natural_idx: np.ndarray, cells: np.ndarray, n_cells: int) -> dict[str, np.ndarray]:
    """Pixel counts per natural class per cell (natural_idx: 0 none, 1..4 class)."""
    return {c: sum_by_cell(natural_idx == i + 1, cells, n_cells) for i, c in enumerate(NATURAL_CLASSES)}


def converted_counts(natural_idx: np.ndarray, conv: np.ndarray, cells: np.ndarray, n_cells: int) -> dict[str, np.ndarray]:
    return {c: sum_by_cell((natural_idx == i + 1) & conv, cells, n_cells) for i, c in enumerate(NATURAL_CLASSES)}


def to_ha(counts: np.ndarray, pixel_ha: np.ndarray, keep: np.ndarray) -> list[float]:
    return np.round(counts[keep] * pixel_ha[keep], 2).tolist()
