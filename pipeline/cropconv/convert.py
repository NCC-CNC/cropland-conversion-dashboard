"""Conversion logic: natural in baseline, a target class in latest, with noise filters.

Targets are crop, pasture, urban and barren (see classes.TARGETS). They key on
the latest class, so the masks are disjoint by construction.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .classes import GROUPS, TARGETS

CROP = GROUPS.index("crop")
PASTURE = GROUPS.index("pasture")
URBAN = GROUPS.index("urban")
BARREN = GROUPS.index("barren")


@dataclass(frozen=True)
class FilterParams:
    persistence: bool = True       # also crop in the persistence snapshot
    min_patch_ha: float = 0.5      # drop connected patches smaller than this (0 = off)
    majority: bool = False         # 3x3 majority filter on the converted mask
    pasture_is_crop: bool = False  # count ACI 122 pasture/forages as crop
    eight_connected: bool = True   # patch connectivity
    exclude_prior_crop: bool = True  # baseline natural excludes cells crop in an earlier snapshot
    # also exclude cells that were pasture or urban in an earlier snapshot (barren is never
    # excluded: it flickers with roads and bare soil). On by default since the owner decision of
    # 2026-11-26; this lowers crop figures (Stettler 2016 to 2025 falls from 3,888 to 1,257 ha).
    # Set False (--keep-prior-pasture-urban) to restore the earlier behaviour.
    exclude_prior_pasture_urban: bool = True


def is_crop(group_arr: np.ndarray, pasture_is_crop: bool = False) -> np.ndarray:
    m = group_arr == CROP
    if pasture_is_crop:
        m |= group_arr == PASTURE
    return m


def is_target(group_arr: np.ndarray, target: str, params: FilterParams) -> np.ndarray:
    """Pixels whose class group belongs to the target.

    pasture_is_crop only changes the crop target. In that sensitivity mode
    pasture is part of crop, so the pasture target is empty to keep targets disjoint.
    """
    if target == "crop":
        return is_crop(group_arr, params.pasture_is_crop)
    if target == "pasture":
        if params.pasture_is_crop:
            return np.zeros(group_arr.shape, dtype=bool)
        return group_arr == PASTURE
    if target == "urban":
        return group_arr == URBAN
    if target == "barren":
        return group_arr == BARREN
    raise ValueError(f"unknown target {target!r}")


def clean_baseline(natural_idx: np.ndarray, earlier_groups: list[np.ndarray], params: FilterParams) -> np.ndarray:
    """Baseline natural class index with cells already put to use in an earlier snapshot removed.

    A cell mapped natural in the baseline year but crop in an earlier year is
    far more likely a fallow, forage or classification flip than natural cover.
    The same holds for earlier pasture and urban use (switch
    exclude_prior_pasture_urban). Earlier barren does not remove a cell.
    Baselines with no earlier snapshot are returned unchanged.
    """
    if not earlier_groups or not (params.exclude_prior_crop or params.exclude_prior_pasture_urban):
        return natural_idx
    prior = np.zeros(natural_idx.shape, dtype=bool)
    for g in earlier_groups:
        if params.exclude_prior_crop:
            prior |= is_crop(g, params.pasture_is_crop)
        if params.exclude_prior_pasture_urban:
            prior |= (g == PASTURE) | (g == URBAN)
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
    target: str = "crop",
) -> np.ndarray:
    """Boolean mask of pixels converted to one target.

    baseline_natural: bool, natural cover in the baseline snapshot.
    latest_group / persist_group: group index arrays (see classes.GROUPS).
    The same filters (persistence, majority, patch size) run for every target;
    persistence requires the target class in the persistence snapshot too.
    """
    m = baseline_natural & is_target(latest_group, target, params)
    if params.persistence and persist_group is not None:
        m &= is_target(persist_group, target, params)
    if params.majority:
        m = majority_filter(m)
    if params.min_patch_ha > 0:
        min_px = int(np.ceil(params.min_patch_ha * 1e4 / pixel_area_m2))
        m = filter_patches(m, min_px, params.eight_connected)
    return m


def conversion_masks(
    baseline_natural: np.ndarray,
    latest_group: np.ndarray,
    persist_group: np.ndarray | None,
    params: FilterParams,
    pixel_area_m2: float,
    targets: list[str] | None = None,
) -> dict[str, np.ndarray]:
    """One conversion mask per target (default: all of classes.TARGETS)."""
    return {
        t: conversion_mask(baseline_natural, latest_group, persist_group, params, pixel_area_m2, t)
        for t in (targets or TARGETS)
    }
