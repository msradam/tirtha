"""End-to-end accessibility pipeline orchestration.

Single ``run_accessibility(...)`` entry point used by the CLI and by
notebooks. Builds the polyglot Dataset, computes friction, runs multi-source
MCP, and reports population-weighted accessibility metrics for the region.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import xrspatial
from rasterio.features import rasterize

from tirtha.data import (
    geocode_region,
    load_dem,
    load_osm_buildings,
    load_osm_facilities,
    load_osm_roads,
)
from tirtha.friction import hybrid_friction, rank_of_highway_tag, tobler_friction
from tirtha.metrics import AccessibilityResult, population_weighted_accessibility
from tirtha.route import multi_source_mcp, seeds_from_geometries


@dataclass(slots=True)
class PipelineResult:
    """Outputs of one ``run_accessibility`` invocation."""

    region: str
    bbox_wsen: tuple[float, float, float, float]
    crs: str
    resolution_m: int
    n_destinations: int
    n_seeds_inside: int
    travel_time_min: np.ndarray
    friction_min_per_m: np.ndarray
    facilities_proj: object  # GeoDataFrame
    accessibility: AccessibilityResult
    timings: dict[str, float] = field(default_factory=dict)


def _utm_zone_for_bbox(bbox: tuple[float, float, float, float]) -> str:
    """Best-effort UTM zone for a (W, S, E, N) bbox centroid in lon/lat."""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    zone = int((cx + 180) / 6) + 1
    south = cy < 0
    return f"EPSG:{32700 + zone if south else 32600 + zone}"


def run_accessibility(
    region: str,
    *,
    destination_tags: dict | None = None,
    resolution_m: int = 10,
    crs: str | None = None,
    bbox_override: tuple[float, float, float, float] | None = None,
    cap_friction_min_per_m: float = 5.0,
    verbose: bool = True,
) -> PipelineResult:
    """Compute walking-time accessibility for a region.

    Args:
        region: geocodable region name (e.g. "Brownsville, Brooklyn",
            "Sierra Leone", "Cox's Bazar, Bangladesh").
        destination_tags: OSM amenity tag dict for the destinations. Default
            is healthcare (clinics, hospitals, doctors, urgent care, pharmacy).
        resolution_m: target raster resolution. 10 for chips, 30-100 for
            country-scale.
        crs: target CRS; if None, auto-pick UTM zone for the bbox centroid.
        cap_friction_min_per_m: upper bound on Tobler friction for extreme
            slopes (default 5 ≈ 12 km/h). Higher values let pathological steep
            terrain dominate MCP outputs.
        verbose: print step timings.

    Returns:
        PipelineResult containing the travel-time raster, friction surface,
        facilities GeoDataFrame, population-weighted accessibility, and
        per-step timings.
    """
    timings: dict[str, float] = {}

    def _log(msg: str) -> None:
        if verbose:
            print(msg)

    def _time(label: str, t0: float) -> None:
        timings[label] = time.time() - t0
        _log(f"  [{label}] {timings[label]:.1f}s")

    # --- 1. Geocode region -> bbox (or use bbox_override directly) -------
    t0 = time.time()
    if bbox_override is not None:
        bbox = tuple(float(x) for x in bbox_override)  # type: ignore[assignment]
        _log(f"[1/6] Using --bbox: {bbox} (no geocoding)")
    else:
        _log(f"[1/6] Geocoding region: {region!r}")
        try:
            boundary = geocode_region(region)
            bbox = tuple(float(x) for x in boundary.total_bounds)  # type: ignore[assignment]
        except TypeError as e:
            # Nominatim didn't return a polygon — likely a point/node OSM record.
            raise RuntimeError(
                f"Geocoding {region!r} did not return a polygon. Pass --bbox 'W,S,E,N' "
                f"directly for places Nominatim doesn't have as a polygon "
                f"(neighborhoods, custom AOIs). Underlying error: {e}"
            )
    if crs is None:
        crs = _utm_zone_for_bbox(bbox)
    _log(f"  bbox (W,S,E,N) = {bbox}")
    _log(f"  CRS = {crs}")
    _time("geocode", t0)

    # --- 2. NASADEM + slope + Tobler friction -----------------------------
    t0 = time.time()
    _log(f"[2/6] Fetching NASADEM at {resolution_m}m + computing slope ...")
    elev_da = load_dem(bbox, crs=crs, resolution_m=resolution_m)
    elev = np.where(np.isfinite(elev_da.values), elev_da.values, 0.0).astype(np.float32)
    H, W = elev.shape
    affine = elev_da.odc.geobox.affine  # type: ignore[attr-defined]
    slope_deg = xrspatial.slope(elev_da)
    slope_rad = np.deg2rad(slope_deg.values).astype(np.float32)
    tobler = tobler_friction(slope_rad, max_friction_min_per_m=cap_friction_min_per_m)
    _log(f"  raster {H}x{W}, elev {elev.min():.0f}-{elev.max():.0f}m")
    _time("dem+tobler", t0)

    # --- 3. OSM roads + rasterize ----------------------------------------
    t0 = time.time()
    _log("[3/6] Fetching OSM roads ...")
    roads = load_osm_roads(bbox, crs=crs)
    roads = roads.assign(rank=roads["highway"].apply(rank_of_highway_tag))
    road_class = rasterize(
        shapes=zip(roads.geometry, roads["rank"]),
        out_shape=(H, W),
        transform=affine,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    _log(f"  {len(roads)} road features → {(road_class > 0).sum():,} road pixels")
    _time("roads", t0)

    # --- 4. Hybrid friction ----------------------------------------------
    t0 = time.time()
    friction = hybrid_friction(tobler, road_class)
    _time("friction", t0)

    # --- 5. Destinations (facilities) + multi-source MCP -----------------
    t0 = time.time()
    _log("[5/6] Fetching destinations + multi-source MCP ...")
    facilities = load_osm_facilities(bbox, crs=crs, tags=destination_tags)
    seeds = seeds_from_geometries(facilities.geometry, affine, (H, W))
    _log(f"  destinations: {len(facilities)} ({len(seeds)} seeds inside chip)")
    if not seeds:
        raise RuntimeError(
            f"No destination seeds inside the chip — check destination_tags or region scope. "
            f"Got {len(facilities)} OSM features but none with centroids in the raster."
        )
    travel_time = multi_source_mcp(friction, seeds, pixel_size_m=resolution_m)
    _log(
        f"  travel time: min {np.nanmin(travel_time):.1f} max {np.nanmax(travel_time):.1f} "
        f"mean {np.nanmean(travel_time):.1f} median {np.nanmedian(travel_time):.1f} min"
    )
    _time("mcp", t0)

    # --- 6. Building density (pop proxy) + accessibility metrics ---------
    t0 = time.time()
    _log("[6/6] Computing building density pop-proxy + accessibility ...")
    buildings = load_osm_buildings(bbox, crs=crs)
    build_count = rasterize(
        ((g, 1) for g in buildings.geometry),
        out_shape=(H, W),
        transform=affine,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    accessibility = population_weighted_accessibility(travel_time, build_count.astype(np.float32))
    for t in accessibility.thresholds_min:
        _log(f"  ≤ {t:3d} min  |  {accessibility.pct_within[t]:5.1f}% of built area")
    _time("metrics", t0)

    timings["total_s"] = sum(timings.values())
    _log(f"\nTotal pipeline: {timings['total_s']:.1f}s")

    return PipelineResult(
        region=region,
        bbox_wsen=bbox,
        crs=crs,
        resolution_m=resolution_m,
        n_destinations=len(facilities),
        n_seeds_inside=len(seeds),
        travel_time_min=travel_time,
        friction_min_per_m=friction,
        facilities_proj=facilities,
        accessibility=accessibility,
        timings=timings,
    )
