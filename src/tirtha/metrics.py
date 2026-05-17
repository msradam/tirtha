"""Accessibility metrics.

Population-weighted percentages within walking-time thresholds — the form
Weiss et al. 2020 reports in *Nature Medicine*. Spearman and MAE comparisons
against benchmark rasters.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import spearmanr


# Standard Weiss-bin thresholds (minutes). Keep this list aligned with the
# methodology paper figure conventions.
DEFAULT_THRESHOLDS_MIN: tuple[int, ...] = (5, 10, 15, 30, 60, 120, 180)


@dataclass(frozen=True, slots=True)
class AccessibilityResult:
    """Population-weighted accessibility numbers for a region."""

    total_population: float
    thresholds_min: tuple[int, ...]
    pct_within: dict[int, float]
    population_within: dict[int, float]

    def as_dict(self) -> dict:
        return {
            "total_population": float(self.total_population),
            "thresholds_min": list(self.thresholds_min),
            "pct_within": {int(k): float(v) for k, v in self.pct_within.items()},
            "population_within": {int(k): float(v) for k, v in self.population_within.items()},
        }


def population_weighted_accessibility(
    travel_time_min: np.ndarray,
    population: np.ndarray,
    thresholds_min: tuple[int, ...] = DEFAULT_THRESHOLDS_MIN,
) -> AccessibilityResult:
    """% of population within each walking-time threshold."""
    valid = np.isfinite(travel_time_min) & np.isfinite(population) & (population > 0)
    total = float(population[valid].sum())
    pct_within: dict[int, float] = {}
    pop_within: dict[int, float] = {}
    for t in thresholds_min:
        pop_t = float(population[valid & (travel_time_min <= t)].sum())
        pop_within[t] = pop_t
        pct_within[t] = 100.0 * pop_t / total if total > 0 else 0.0
    return AccessibilityResult(
        total_population=total,
        thresholds_min=thresholds_min,
        pct_within=pct_within,
        population_within=pop_within,
    )


def compare_rasters(
    a: np.ndarray,
    b: np.ndarray,
    label_a: str = "a",
    label_b: str = "b",
) -> dict:
    """Per-pixel Spearman rho, Pearson r, MAE between two rasters."""
    valid = np.isfinite(a) & np.isfinite(b)
    if valid.sum() < 100:
        return {"valid_pixels": int(valid.sum()), "rho": None, "mae": None}
    rho, _ = spearmanr(a[valid].flatten(), b[valid].flatten())
    diff = a[valid] - b[valid]
    return {
        "valid_pixels": int(valid.sum()),
        "spearman_rho": float(rho),
        "mae_min": float(np.abs(diff).mean()),
        "bias_min": float(diff.mean()),
        "label_a": label_a,
        "label_b": label_b,
    }
