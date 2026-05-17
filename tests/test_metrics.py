"""Tests for tirtha.metrics."""
from __future__ import annotations

import numpy as np
import pytest

from tirtha.metrics import (
    DEFAULT_THRESHOLDS_MIN,
    AccessibilityResult,
    compare_rasters,
    population_weighted_accessibility,
)


def test_accessibility_basic_thresholds():
    """50% of pop within 10 min, 100% within 30 min — simple synthetic check."""
    # 4 cells: travel times 5, 8, 15, 25 min; populations all equal to 1.
    tt = np.array([[5.0, 8.0], [15.0, 25.0]], dtype=np.float32)
    pop = np.ones_like(tt)
    res = population_weighted_accessibility(tt, pop, thresholds_min=(5, 10, 15, 30))
    assert res.total_population == 4.0
    assert res.pct_within[5] == 25.0  # only the 5-min cell
    assert res.pct_within[10] == 50.0  # 5 and 8
    assert res.pct_within[15] == 75.0
    assert res.pct_within[30] == 100.0


def test_accessibility_skips_zero_population():
    """Pixels with zero population shouldn't contribute to denominator or numerator."""
    tt = np.array([[1.0, 100.0]], dtype=np.float32)
    pop = np.array([[10.0, 0.0]], dtype=np.float32)
    res = population_weighted_accessibility(tt, pop, thresholds_min=(5,))
    assert res.total_population == 10.0
    assert res.pct_within[5] == 100.0  # only the populated cell counts


def test_accessibility_handles_nan_travel_time():
    """Unreachable cells (NaN travel time) should be ignored."""
    tt = np.array([[5.0, np.nan, 8.0]], dtype=np.float32)
    pop = np.array([[1.0, 100.0, 1.0]], dtype=np.float32)
    res = population_weighted_accessibility(tt, pop, thresholds_min=(10,))
    # Valid pop = 2; both within 10 min
    assert res.total_population == 2.0
    assert res.pct_within[10] == 100.0


def test_default_thresholds_include_weiss_bins():
    """The Weiss et al. 2020 reporting bins {30, 60, 120} must be in the defaults."""
    assert 30 in DEFAULT_THRESHOLDS_MIN
    assert 60 in DEFAULT_THRESHOLDS_MIN
    assert 120 in DEFAULT_THRESHOLDS_MIN


def test_accessibility_result_as_dict_is_json_serializable():
    """as_dict should produce a plain-dict structure with builtin numeric types."""
    import json

    res = AccessibilityResult(
        total_population=100.0,
        thresholds_min=(5, 10),
        pct_within={5: 25.0, 10: 75.0},
        population_within={5: 25.0, 10: 75.0},
    )
    d = res.as_dict()
    # Round-trip through JSON to verify serializability.
    s = json.dumps(d)
    d2 = json.loads(s)
    assert d2["total_population"] == 100.0


def test_compare_rasters_identity_perfect_correlation():
    """Comparing a raster to itself should give Spearman ~1, MAE=0."""
    a = np.random.default_rng(0).normal(size=(20, 20)).astype(np.float32)
    res = compare_rasters(a, a)
    assert res["spearman_rho"] == pytest.approx(1.0, abs=1e-9)
    assert res["mae_min"] == 0.0


def test_compare_rasters_constant_bias():
    """If b = a + 5, MAE should be 5 and rho should remain ~1."""
    a = np.random.default_rng(1).normal(size=(20, 20)).astype(np.float32)
    b = a + 5.0
    res = compare_rasters(a, b)
    assert res["spearman_rho"] == pytest.approx(1.0, abs=1e-9)
    np.testing.assert_allclose(res["mae_min"], 5.0, atol=1e-5)
    np.testing.assert_allclose(res["bias_min"], -5.0, atol=1e-5)


def test_compare_rasters_ignores_nans():
    """Pixels where either raster is NaN should be excluded from the comparison."""
    a = np.concatenate(
        [np.arange(20, dtype=np.float32), [np.nan, 999.0]]
    )
    b = np.concatenate(
        [np.arange(20, dtype=np.float32) + 0.5, [42.0, np.nan]]
    )
    res = compare_rasters(a, b)
    # 20 valid pixels (NaN in either raster excludes both index 20 and 21).
    assert res["valid_pixels"] == 20
    np.testing.assert_allclose(res["mae_min"], 0.5, atol=1e-5)


def test_compare_rasters_returns_none_keys_when_too_few_valid_pixels():
    """Below ``min_valid_pixels``, return None for rho/mae but keep the keys."""
    a = np.array([1.0, 2.0, np.nan], dtype=np.float32)
    b = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    res = compare_rasters(a, b)
    assert res["spearman_rho"] is None
    assert res["mae_min"] is None
    assert "valid_pixels" in res
