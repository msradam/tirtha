"""Tests for tirtha.route."""
from __future__ import annotations

import numpy as np
import pytest

from tirtha.route import multi_source_mcp, seeds_from_geometries


def test_mcp_single_seed_returns_zero_at_seed():
    """Travel time at the seed pixel must be zero."""
    friction = np.full((10, 10), 0.1, dtype=np.float32)
    tt = multi_source_mcp(friction, seeds=[(5, 5)], pixel_size_m=10.0)
    assert tt[5, 5] == 0.0


def test_mcp_monotonic_with_distance():
    """On a uniform friction raster, travel time should increase with distance from seed."""
    friction = np.full((11, 11), 0.1, dtype=np.float32)
    tt = multi_source_mcp(friction, seeds=[(5, 5)], pixel_size_m=10.0)
    # Far corner should be slower than adjacent pixel.
    assert tt[0, 0] > tt[5, 4]
    assert tt[10, 10] > tt[6, 6]


def test_mcp_two_seeds_use_nearest():
    """Multi-source MCP returns distance to NEAREST seed."""
    friction = np.full((11, 11), 0.1, dtype=np.float32)
    tt_two = multi_source_mcp(friction, seeds=[(0, 0), (10, 10)], pixel_size_m=10.0)
    tt_one = multi_source_mcp(friction, seeds=[(0, 0)], pixel_size_m=10.0)
    # The bottom-right pixel is closer to the second seed than the first;
    # adding the second seed should never increase its travel time.
    assert tt_two[10, 10] <= tt_one[10, 10]
    assert tt_two[10, 10] == 0.0


def test_mcp_low_friction_is_faster():
    """A pixel with much lower friction should produce lower travel times along its path."""
    friction_uniform = np.full((11, 11), 1.0, dtype=np.float32)
    friction_corridor = friction_uniform.copy()
    friction_corridor[5, :] = 0.01  # horizontal "highway" through the middle
    tt_uniform = multi_source_mcp(friction_uniform, seeds=[(5, 0)], pixel_size_m=10.0)
    tt_corridor = multi_source_mcp(friction_corridor, seeds=[(5, 0)], pixel_size_m=10.0)
    # Along the corridor, travel should be ~100× faster.
    assert tt_corridor[5, 10] < tt_uniform[5, 10] / 10


def test_mcp_empty_seeds_raises():
    """Routing with no seeds is a programming error."""
    friction = np.ones((5, 5), dtype=np.float32)
    with pytest.raises(ValueError):
        multi_source_mcp(friction, seeds=[], pixel_size_m=10.0)


def test_seeds_from_geometries_filters_outside_chip():
    """Geometries outside the raster bounds should be silently dropped."""
    from shapely.geometry import Point
    from affine import Affine

    affine = Affine.translation(0, 100) * Affine.scale(10.0, -10.0)
    shape = (10, 10)
    geoms = [Point(15, 85), Point(-50, 200), Point(95, 5)]
    seeds = seeds_from_geometries(geoms, affine, shape)
    # First and third points are inside; second is outside.
    assert len(seeds) == 2
