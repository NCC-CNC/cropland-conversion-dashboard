"""Conversion logic: natural in baseline, crop in latest, with noise filters."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .classes import GROUPS

CROP = GROUPS.index("crop")
PASTURE = GROUPS.index("pasture")


@dataclass(frozen=True)
class FilterParams:
    persistence: bool = True       # also crop in the persistence snapshot
    min_patch_ha: float = 0.5      # drop connected patches smaller than this (0 = off)
    majority: bool = False         # 3x3 majority filter on the converted mask
    pasture_is_crop: bool = False  # count ACI 122 pasture/forages as crop
    eight_connected: bool = True   # patch connectivity
    exclude_prior_crop: bool = True  # baseline natural excludes cells crop in an earlier snapshot


def is_crop(group_arr: np.ndarray, pasture_is_crop: bool = False) -> np.ndarray:
    m = group_arr == CROP
    if pasture_is_crop:
        m |= group_arr == PASTURE
    return m


def clean_baseline(natural_idx: np.ndarray, earlier_groups: list[np.ndarray], params: FilterParams) -> np.ndarray:
    """Baseline natural class index with cells that were crop in an earlier snapshot removed.

    A cell mapped natural in the baseline year but crop in an earlier year is
    far more likely a fallow, forage or classification flip than natural cover.
    Baselines with no earlier snapshot are returned unchanged.
    """
    if not params.exclude_prior_crop or not earlier_groups:
        return natural_idx
    prior = np.zeros(natural_idx.shape, dtype=bool)
    for g in earlier_groups:
        prior |= is_crop(g, params.pasture_is_crop)
    return np.where(prior, 0, natural_idx).astype(natural_idx.dtype)


def persistence_year(baseline: int, latest: int, available: list[int]) -> int | None:
    """Most recent available snapshot strictly between baseline and latest."""
    mid = [y for y in available if baseline < y < latest]
    return max(mid) if mid else None


def filter_patches(mask: np.ndarray, min_px: int, eight_connected: bool = True) -> np.ndarray:
    """Remove connected components with fewer than min_px pixels."""
    if min_px <= 1 or not mask.any():
        return mask
    structure = np.ones((3, 3), dtype=int) if eight_connected else None
    labels, n = ndimage.label(mask, structure=structure)
    sizes = np.bincount(labels.ravel(), minlength=n + 1)
    keep = sizes >= min_px
    keep[0] = False
    return keep[labels]


def majority_filter(mask: np.ndarray) -> np.ndarray:
    """Keep a pixel only if at least 5 of its 3x3 neighbourhood (self included) are set."""
    counts = ndimage.uniform_filter(mask.astype(np.float32), size=3, mode="constant") * 9.0
    return mask & (counts > 4.5)


def conversion_mask(
    baseline_natural: np.ndarray,
    latest_group: np.ndarray,
    persist_group: np.ndarray | None,
    params: FilterParams,
    pixel_area_m2: float,
) -> np.ndarray:
    """Boolean mask of converted pixels.

    baseline_natural: bool, natural cover in the baseline snapshot.
    latest_group / persist_group: group index arrays (see classes.GROUPS).
    """
    m = baseline_natural & is_crop(latest_group, params.pasture_is_crop)
    if params.persistence and persist_group is not None:
        m &= is_crop(persist_group, params.pasture_is_crop)
    if params.majority:
        m = majority_filter(m)
    if params.min_patch_ha > 0:
        min_px = int(np.ceil(params.min_patch_ha * 1e4 / pixel_area_m2))
        m = filter_patches(m, min_px, params.eight_connected)
    return m
