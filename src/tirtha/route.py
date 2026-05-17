"""Shortest-path routing primitives.

Thin wrappers around ``scikit-image.graph.MCP_Geometric`` for multi-source
Dijkstra over a friction raster. The fusion-graph (pixel grid + OSMnx) lives
here too as a separate function; default routing uses raster-only because the
pixel-grid IS a valid road graph at 10–100m resolution with dense OSM coverage.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
from skimage.graph import MCP_Geometric


def seeds_from_geometries(
    geoms: Iterable,
    affine,
    shape: tuple[int, int],
) -> list[tuple[int, int]]:
    """Convert vector geometry centroids to (row, col) pixel coordinates.

    Args:
        geoms: iterable of shapely geometries (in the same CRS as ``affine``)
        affine: rasterio/odc-geo Affine transform
        shape: (H, W) of the friction raster

    Returns:
        List of (row, col) tuples for geometries that fall inside the raster.
    """
    H, W = shape
    seeds = []
    for geom in geoms:
        c = geom.centroid
        col = int((c.x - affine.c) / affine.a)
        row = int((c.y - affine.f) / affine.e)
        if 0 <= row < H and 0 <= col < W:
            seeds.append((row, col))
    return seeds


def multi_source_mcp(
    friction_min_per_m: np.ndarray,
    seeds: list[tuple[int, int]],
    pixel_size_m: float,
) -> np.ndarray:
    """Multi-source Dijkstra over a friction raster.

    Args:
        friction_min_per_m: 2D float32 array, walking cost in min per meter.
        seeds: list of (row, col) source pixel positions (typically facilities).
        pixel_size_m: physical pixel size (10 or 100 in our pipelines).

    Returns:
        Travel-time raster in minutes, NaN where unreachable.
    """
    if not seeds:
        raise ValueError("multi_source_mcp requires at least one seed")
    mcp = MCP_Geometric(friction_min_per_m.astype(np.float32), fully_connected=True)
    cumulative, _ = mcp.find_costs(starts=seeds)
    travel_time = cumulative * pixel_size_m
    return np.where(np.isinf(travel_time), np.nan, travel_time).astype(np.float32)
