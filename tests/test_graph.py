"""Tests for tirtha.graph — synthetic build + save/load round-trip."""
from __future__ import annotations

import numpy as np

from tirtha.graph import (
    NODE_FACILITY,
    build_graph,
    load_graph,
    save_graph,
)


def _identity_affine(pixel_size_m: float):
    """A simple north-up affine for tests."""
    from affine import Affine

    return Affine.translation(0.0, 100.0) * Affine.scale(pixel_size_m, -pixel_size_m)


def test_build_graph_pixel_only():
    """Without an OSMnx graph, build a pure pixel grid + 8-connected edges."""
    friction = np.full((5, 5), 0.01, dtype=np.float32)
    affine = _identity_affine(10.0)
    g = build_graph(
        friction=friction,
        affine=affine,
        crs="EPSG:32618",
        pixel_size_m=10.0,
        region="synthetic",
        road_graph=None,
        facility_geoms=None,
    )
    assert g.n_pixel_nodes == 25
    assert g.n_road_nodes == 0
    # 8-connected over a 5x5 grid: corners contribute 3 outgoing, edges 5, interior 8.
    # Total directed edges = 4*3 + 12*5 + 9*8 = 12 + 60 + 72 = 144
    assert g.adj.nnz == 144


def test_build_graph_with_facilities_marks_seeds():
    """Facility centroids that fall inside the chip should be marked NODE_FACILITY."""
    from shapely.geometry import Point

    friction = np.full((5, 5), 0.01, dtype=np.float32)
    affine = _identity_affine(10.0)
    # Pixel (1, 2) center is at x=25, y=85 in this affine.
    geom = Point(25.0, 85.0)
    g = build_graph(
        friction=friction,
        affine=affine,
        crs="EPSG:32618",
        pixel_size_m=10.0,
        region="synthetic",
        facility_geoms=[geom],
    )
    assert len(g.facility_node_ids) == 1
    facility_idx = int(g.facility_node_ids[0])
    assert g.node_type[facility_idx] == NODE_FACILITY


def test_save_load_graph_roundtrip(tmp_path):
    """Saving and loading a graph should preserve every attribute."""
    from shapely.geometry import Point

    friction = (np.arange(25).reshape(5, 5) * 0.001).astype(np.float32)
    affine = _identity_affine(10.0)
    g = build_graph(
        friction=friction,
        affine=affine,
        crs="EPSG:4326",
        pixel_size_m=10.0,
        region="round-trip test",
        facility_geoms=[Point(25.0, 85.0)],
    )
    path = tmp_path / "test.graph.npz"
    save_graph(g, path)
    g2 = load_graph(path)
    assert g2.region == g.region
    assert g2.crs == g.crs
    assert g2.raster_shape == g.raster_shape
    assert g2.pixel_size_m == g.pixel_size_m
    np.testing.assert_array_equal(g2.node_xy, g.node_xy)
    np.testing.assert_array_equal(g2.node_type, g.node_type)
    np.testing.assert_array_equal(g2.facility_node_ids, g.facility_node_ids)
    # CSR matrices: compare via .toarray() round-trip
    np.testing.assert_array_equal(g2.adj.toarray(), g.adj.toarray())


def test_graph_summary_has_useful_info():
    """Summary string should mention region, dimensions, and node counts."""
    friction = np.full((4, 4), 0.01, dtype=np.float32)
    affine = _identity_affine(10.0)
    g = build_graph(
        friction=friction,
        affine=affine,
        crs="EPSG:32618",
        pixel_size_m=10.0,
        region="X",
    )
    s = g.summary()
    assert "X" in s
    assert "4×4" in s
    assert "10m" in s or "10 m" in s.replace("m", " m")
