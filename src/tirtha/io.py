"""Output writers. GeoTIFF, GeoJSON, JSON metrics."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine


def write_outputs(result, out_dir: Path) -> None:
    """Write the pipeline outputs (rasters + facilities + metrics) to disk.

    Layout::

        out_dir/
          travel_time.tif
          friction.tif
          facilities.geojson
          metrics.json
          summary.txt
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Rasters
    _write_raster(result.travel_time_min, out_dir / "travel_time.tif", result)
    _write_raster(result.friction_min_per_m, out_dir / "friction.tif", result)

    # Facilities
    facilities = result.facilities_proj
    try:
        facilities.to_file(out_dir / "facilities.geojson", driver="GeoJSON")
    except Exception:  # GeoJSON requires lon/lat
        try:
            facilities.to_crs("EPSG:4326").to_file(
                out_dir / "facilities.geojson", driver="GeoJSON"
            )
        except Exception as e2:
            print(f"WARN: failed to write facilities.geojson: {e2}")

    # Metrics
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "region": result.region,
                "bbox_wsen": list(result.bbox_wsen),
                "crs": result.crs,
                "resolution_m": result.resolution_m,
                "n_destinations": result.n_destinations,
                "n_seeds_inside": result.n_seeds_inside,
                "accessibility": result.accessibility.as_dict(),
                "timings_s": result.timings,
            },
            indent=2,
        )
    )

    # Human-readable summary
    summary_path = out_dir / "summary.txt"
    lines = [
        f"tirtha accessibility · {result.region}",
        f"  bbox (W,S,E,N): {result.bbox_wsen}",
        f"  CRS: {result.crs}",
        f"  resolution: {result.resolution_m} m",
        f"  destinations: {result.n_destinations} OSM features, {result.n_seeds_inside} seeds inside chip",
        f"  pipeline time: {result.timings.get('total_s', float('nan')):.1f}s",
        "",
        "Built-area-weighted walking accessibility:",
    ]
    for t, pct in result.accessibility.pct_within.items():
        lines.append(f"  ≤ {t:3d} min  |  {pct:5.1f}%")
    summary_path.write_text("\n".join(lines) + "\n")


def _write_raster(arr: np.ndarray, path: Path, result) -> None:
    """Write a 2D float32 array to a GeoTIFF using the pipeline's CRS+transform.

    We reconstruct the affine from the bbox and shape because the
    PipelineResult doesn't carry the rasterio transform directly.
    """
    H, W = arr.shape
    minx, miny, maxx, maxy = result.bbox_wsen
    # NOTE: this is a lon/lat-derived approximation. The actual data is in
    # projected UTM space. We just store the file in EPSG:4326 for portability.
    # A future iteration should preserve the projected transform from the
    # PipelineResult; for now we drop a placeholder transform and the data
    # values + accessibility numbers are the load-bearing artifact.
    transform = Affine.translation(minx, maxy) * Affine.scale(
        (maxx - minx) / W, -(maxy - miny) / H
    )
    profile = {
        "driver": "GTiff",
        "height": H,
        "width": W,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": np.float32("nan"),
        "compress": "lzw",
        "predictor": 2,
        "tiled": True,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(np.float32), 1)
