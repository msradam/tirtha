"""Accessibility metrics.

Population-weighted percentages within walking-time thresholds, the form
Weiss et al. (2020) reports in *Nature Medicine*. The intellectual lineage
of accessibility-as-percent-within-threshold goes back to Hansen (1959) on
gravity-based accessibility and Penchansky & Thomas (1981) on the five
dimensions of access. Tirtha measures the physical/temporal dimension only;
quality, insurance, continuity, and trust gaps are out of scope and we say
so explicitly in ``docs/methodology.md``.

Spearman and MAE raster comparisons follow standard nonparametric statistics
practice. The reporting bins (30, 60, 120, 180 min) match Weiss et al. (2020).

See ``docs/references.md`` for full citations.
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
    *,
    min_valid_pixels: int = 10,
) -> dict:
    """Per-pixel Spearman rho + MAE + bias between two rasters.

    Always returns a dict with the same keys; rho is ``None`` when there are
    fewer than ``min_valid_pixels`` valid (finite, non-NaN) pixels.
    """
    valid = np.isfinite(a) & np.isfinite(b)
    n = int(valid.sum())
    result: dict = {
        "valid_pixels": n,
        "spearman_rho": None,
        "mae_min": None,
        "bias_min": None,
        "label_a": label_a,
        "label_b": label_b,
    }
    if n < min_valid_pixels:
        return result
    a_v = a[valid].flatten()
    b_v = b[valid].flatten()
    rho, _ = spearmanr(a_v, b_v)
    diff = a_v - b_v
    result["spearman_rho"] = float(rho) if np.isfinite(rho) else None
    result["mae_min"] = float(np.abs(diff).mean())
    result["bias_min"] = float(diff.mean())
    return result
