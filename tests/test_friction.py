"""Tests for tirtha.friction.

Focus: the Tobler hiking function math, the hybrid override behaviour, and
the FM blend formula. Synthetic inputs only; no network, no GPU.
"""
from __future__ import annotations

import numpy as np

from tirtha.friction import (
    HIGHWAY_RANK,
    WALK_KMH_BY_HIGHWAY_RANK,
    fm_blended_friction,
    hybrid_friction,
    rank_of_highway_tag,
    tobler_friction,
)


def test_tobler_flat_terrain_close_to_max_speed():
    """On flat terrain, Tobler walking speed is ~5 km/h (the 6 * exp(-0.175) base)."""
    slope_rad = np.zeros((10, 10), dtype=np.float32)
    friction = tobler_friction(slope_rad)
    # 6 km/h * exp(-3.5 * 0.05) = 5.038 km/h → friction = 60 / (5.038 * 1000) ≈ 0.0119
    np.testing.assert_allclose(friction, 0.01191, atol=0.0005)


def test_tobler_steep_uphill_is_slower():
    """Walking uphill at +30% slope must be slower (higher friction) than flat."""
    flat = tobler_friction(np.zeros((1, 1), dtype=np.float32))
    steep_up = tobler_friction(np.full((1, 1), np.arctan(0.30), dtype=np.float32))
    assert steep_up[0, 0] > flat[0, 0]
    # Tobler optimum is at slope ≈ -0.05; +0.30 slope should be much slower.
    # v_kmh(slope=arctan(0.30)) = 6 * exp(-3.5 * |0.30 + 0.05|) = 6 * exp(-1.225) ≈ 1.76 km/h
    # friction ≈ 60 / (1.76 * 1000) ≈ 0.034
    np.testing.assert_allclose(steep_up[0, 0], 0.034, atol=0.005)


def test_tobler_optimum_is_slight_downhill():
    """Tobler's hiking function maxes out at slope = -0.05 (slight downhill)."""
    grid = np.array([[np.arctan(-0.10)], [np.arctan(-0.05)], [np.arctan(0.0)]], dtype=np.float32)
    fr = tobler_friction(grid)
    # Friction is minimised (speed maximised) at the middle row, slope=-0.05.
    assert fr[1, 0] < fr[0, 0]
    assert fr[1, 0] < fr[2, 0]


def test_tobler_caps_at_max_friction():
    """Extreme slopes should be clipped to the configured ceiling."""
    insane_slope = np.full((1, 1), np.arctan(2.0), dtype=np.float32)
    fr = tobler_friction(insane_slope, max_friction_min_per_m=5.0)
    assert fr[0, 0] == 5.0


def test_tobler_handles_nan_slopes():
    """NaN slope inputs (e.g. raster edge artifacts) should not propagate."""
    slope = np.array([[np.nan, 0.0], [0.0, np.nan]], dtype=np.float32)
    fr = tobler_friction(slope)
    assert np.all(np.isfinite(fr))


def test_hybrid_friction_uses_road_speed_where_faster():
    """Where roads exist, friction = min(Tobler, road_walking)."""
    H, W = 5, 5
    # Off-road Tobler ~ 0.012; road walk @ 5 km/h = 0.012; road walk @ 6 km/h = 0.010.
    tobler = np.full((H, W), 0.020, dtype=np.float32)  # slow off-road
    road = np.zeros((H, W), dtype=np.uint8)
    road[2, 2] = 6  # motorway rank → 6 km/h on foot
    fr = hybrid_friction(tobler, road)
    # Off-road cells unchanged
    assert fr[0, 0] == np.float32(0.020)
    # Road cell uses the faster road walking speed
    expected_road = np.float32(60.0 / (6.0 * 1000.0))
    np.testing.assert_allclose(fr[2, 2], expected_road, atol=1e-6)


def test_hybrid_friction_keeps_tobler_when_already_faster():
    """If Tobler off-road is already faster than the road walking speed
    (e.g. a steep downhill), the road override does not slow things down."""
    fast_tobler = np.full((3, 3), 0.005, dtype=np.float32)  # implausibly fast, for test
    road = np.full((3, 3), 1, dtype=np.uint8)  # local road, 5 km/h → friction 0.012
    fr = hybrid_friction(fast_tobler, road)
    assert np.all(fr <= 0.012)
    assert np.all(fr == 0.005)


def test_fm_blended_friction_interpolates():
    """fm_blended_friction is a convex combination of off-road and road-walk."""
    H, W = 3, 3
    tobler = np.full((H, W), 0.030, dtype=np.float32)
    # P(road) = 0 → pure Tobler
    p0 = np.zeros((H, W), dtype=np.float32)
    f0 = fm_blended_friction(tobler, p0)
    np.testing.assert_allclose(f0, tobler)
    # P(road) = 1 → pure road-walk
    p1 = np.ones((H, W), dtype=np.float32)
    f1 = fm_blended_friction(tobler, p1, road_walk_kmh=5.5)
    expected = np.full((H, W), 60.0 / (5.5 * 1000.0), dtype=np.float32)
    np.testing.assert_allclose(f1, expected, atol=1e-6)
    # P(road) = 0.5 → midway
    fhalf = fm_blended_friction(tobler, np.full((H, W), 0.5, dtype=np.float32))
    assert np.all(fhalf < tobler)
    assert np.all(fhalf > expected)


def test_rank_of_highway_tag_handles_string_iterable_and_unknown():
    """Tag mapper should accept str, iterable, and unknown values."""
    assert rank_of_highway_tag("motorway") == 6
    assert rank_of_highway_tag("primary") == 4
    assert rank_of_highway_tag("residential") == 1
    assert rank_of_highway_tag(["secondary", "tertiary"]) == 3
    assert rank_of_highway_tag("not_a_real_highway_class") == 1  # fallback to local
    assert rank_of_highway_tag([]) == 1


def test_highway_rank_table_covers_walking_speeds():
    """Every rank used in HIGHWAY_RANK should have a corresponding walking speed."""
    for tag, rank in HIGHWAY_RANK.items():
        assert rank in WALK_KMH_BY_HIGHWAY_RANK, f"rank {rank} (from {tag!r}) has no speed"
