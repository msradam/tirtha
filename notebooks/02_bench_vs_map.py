"""tirtha · benchmark vs MAP 2020 (Weiss et al., Nature Medicine).

Reactive marimo notebook. Point it at any directory produced by
``tirtha accessibility run`` and it computes the head-to-head against the
published MAP 2020 walking-only travel-time raster, downloaded once and
clipped to the region's bbox.

This lives in notebooks/, not the CLI, because benchmarking is a
research/validation operation, not a production primitive. The CLI's
job is to make accessibility maps. This notebook's job is to validate
them against the published reference.

Run with:
    uv run marimo edit notebooks/02_bench_vs_map.py
"""
from __future__ import annotations

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    mo.md(
        """
        # tirtha · benchmark vs MAP 2020

        Per-pixel comparison of any tirtha output against the published
        [Malaria Atlas Project 2020](https://malariaatlas.org/project-resources/accessibility-to-healthcare/)
        walking-only travel-time raster (Weiss et al., *Nature Medicine*).

        **How to use:**

        1. Run tirtha first to produce a travel-time raster for a region:

           ```
           uv run tirtha accessibility run --region "Blantyre, Malawi" --out ./blantyre
           ```

        2. Point this notebook at that output directory in the cell below.

        3. The notebook downloads MAP 2020 (one-time, ~460 MB cached),
           clips it to the same bbox, reprojects to the same grid, and
           reports Spearman ρ, MAE, and a 3-panel figure.
        """
    )
    return (mo,)


@app.cell
def _():
    # Edit this to point at your tirtha output directory.
    TIRTHA_OUT_DIR = "/tmp/tirtha-demo"
    MAP_CACHE_DIR = "/tmp/tirtha-cache"
    return MAP_CACHE_DIR, TIRTHA_OUT_DIR


@app.cell
def _(MAP_CACHE_DIR, TIRTHA_OUT_DIR, mo):
    mo.md(
        f"""
        ## Inputs

        - Tirtha output directory: `{TIRTHA_OUT_DIR}`
        - MAP 2020 cache directory: `{MAP_CACHE_DIR}`
        """
    )
    return


@app.cell
def _(TIRTHA_OUT_DIR):
    import json
    from pathlib import Path

    out_dir = Path(TIRTHA_OUT_DIR)
    metrics = json.loads((out_dir / "metrics.json").read_text())
    bbox = tuple(metrics["bbox_wsen"])
    region = metrics["region"]
    crs = metrics["crs"]
    return Path, bbox, crs, json, metrics, out_dir, region


@app.cell
def _(bbox, mo, region):
    mo.md(
        f"""
        ## Loaded tirtha run

        - **Region**: {region}
        - **Bbox (W, S, E, N)**: `{bbox}`
        """
    )
    return


@app.cell
def _(MAP_CACHE_DIR):
    from tirtha.data import download_map_2020_walking
    map_path = download_map_2020_walking(MAP_CACHE_DIR)
    return download_map_2020_walking, map_path


@app.cell
def _(bbox, map_path, out_dir):
    """Clip MAP 2020 to the tirtha bbox + reproject onto the same grid as tirtha's travel_time.tif."""
    import numpy as np
    import rioxarray
    from rasterio.enums import Resampling

    tirtha_tt = rioxarray.open_rasterio(out_dir / "travel_time.tif", masked=True).squeeze()

    map_global = rioxarray.open_rasterio(map_path, masked=True, chunks={"x": 2048, "y": 2048}).squeeze()
    buf = 0.05
    map_clip = map_global.rio.clip_box(bbox[0] - buf, bbox[1] - buf, bbox[2] + buf, bbox[3] + buf)
    map_local = map_clip.rio.reproject_match(tirtha_tt, resampling=Resampling.bilinear)

    tt_tirtha = np.where(np.isfinite(tirtha_tt.values), tirtha_tt.values, np.nan).astype(np.float32)
    tt_map = np.where(np.isfinite(map_local.values), map_local.values, np.nan).astype(np.float32)
    return Resampling, map_clip, map_global, map_local, np, rioxarray, tirtha_tt, tt_map, tt_tirtha


@app.cell
def _(mo, np, tt_map, tt_tirtha):
    valid = np.isfinite(tt_tirtha) & np.isfinite(tt_map)
    mo.md(
        f"""
        ## Raster comparison

        - Tirtha grid: `{tt_tirtha.shape}`, range `{np.nanmin(tt_tirtha):.1f}–{np.nanmax(tt_tirtha):.1f}` min
        - MAP 2020 grid: `{tt_map.shape}`, range `{np.nanmin(tt_map):.1f}–{np.nanmax(tt_map):.1f}` min
        - Valid (both finite) pixels: **{int(valid.sum()):,}** of `{tt_tirtha.size}`
        """
    )
    return (valid,)


@app.cell
def _(tt_map, tt_tirtha, valid):
    from tirtha.metrics import compare_rasters
    cmp_result = compare_rasters(tt_tirtha, tt_map, label_a="tirtha", label_b="MAP 2020")
    return cmp_result, compare_rasters


@app.cell
def _(cmp_result, mo):
    mo.md(
        f"""
        ## Head-to-head metrics

        | Metric | Value |
        |---|---|
        | Spearman ρ | **{cmp_result['spearman_rho']:.3f}** |
        | MAE | {cmp_result['mae_min']:.2f} min |
        | Bias (tirtha − MAP) | {cmp_result['bias_min']:+.2f} min |
        | Valid pixels | {cmp_result['valid_pixels']:,} |
        """
    )
    return


@app.cell
def _(np, tt_map, tt_tirtha, valid):
    # Weiss-bin accessibility, comparison head-to-head.
    # NOTE: This is area-weighted (not pop-weighted), since this notebook
    # doesn't load a population layer. The tirtha CLI output already has
    # pop-weighted numbers in metrics.json.
    thresholds = [5, 15, 30, 60, 120, 180]
    n = int(valid.sum())
    rows = []
    for t in thresholds:
        ti = float((valid & (tt_tirtha <= t)).sum()) / n * 100
        mp = float((valid & (tt_map <= t)).sum()) / n * 100
        rows.append((t, ti, mp, ti - mp))
    return n, rows, thresholds


@app.cell
def _(mo, rows):
    body = "\n".join(
        f"| ≤ {t:3d} min | {ti:5.1f}% | {mp:5.1f}% | {d:+5.1f} pp |"
        for t, ti, mp, d in rows
    )
    mo.md(
        f"""
        ## Area-weighted accessibility head-to-head

        | Threshold | Tirtha | MAP 2020 | Δ |
        |---|---|---|---|
        {body}

        Note: this is **area-weighted**, not population-weighted. For
        population-weighted numbers see `metrics.json` in the tirtha
        output directory (those use the tirtha pipeline's WorldPop or
        building-density population layer).
        """
    )
    return (body,)


@app.cell
def _(np, tt_map, tt_tirtha):
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    vmax = max(np.nanpercentile(tt_tirtha, 99), np.nanpercentile(tt_map, 99))
    diff = tt_tirtha - tt_map
    dlim = np.nanpercentile(np.abs(diff), 98)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    im0 = axes[0].imshow(tt_tirtha, cmap="magma_r", vmin=0, vmax=vmax)
    axes[0].set_title(f"Tirtha\nmean {np.nanmean(tt_tirtha):.1f} min", fontsize=11)
    axes[0].set_xticks([]); axes[0].set_yticks([])
    plt.colorbar(im0, ax=axes[0], fraction=0.046, label="min")

    im1 = axes[1].imshow(tt_map, cmap="magma_r", vmin=0, vmax=vmax)
    axes[1].set_title(f"MAP 2020 (Weiss et al.)\nmean {np.nanmean(tt_map):.1f} min", fontsize=11)
    axes[1].set_xticks([]); axes[1].set_yticks([])
    plt.colorbar(im1, ax=axes[1], fraction=0.046, label="min")

    im2 = axes[2].imshow(diff, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-dlim, vcenter=0, vmax=dlim))
    axes[2].set_title("Δ (tirtha − MAP)\nred = tirtha slower; blue = tirtha faster", fontsize=11)
    axes[2].set_xticks([]); axes[2].set_yticks([])
    plt.colorbar(im2, ax=axes[2], fraction=0.046, label="Δ min")

    plt.suptitle("tirtha · MAP 2020 head-to-head", fontsize=13, y=1.03)
    plt.tight_layout()
    fig
    return TwoSlopeNorm, axes, diff, dlim, fig, im0, im1, im2, plt, vmax


@app.cell
def _(mo):
    mo.md(
        """
        ## Interpretation guide

        - **Spearman ρ > 0.6**: tirtha agrees with MAP on the *rank ordering* of
          pixels by travel-time. Most chips at 10-30m hit this comfortably; the
          number is driven by MAP's ~925m resolution vs tirtha's finer grid.
        - **MAE in minutes**: typical chips land at 2-5 min absolute disagreement.
          Cox's Bazar shows ~125 min MAE because MAP's 2020 facility database
          missed the camp's internal clinics (see figure 20 in the repo).
        - **Bias**: tirtha is systematically slightly *slower* than MAP in dense
          urban chips because our finer grid captures longer paths around
          buildings that MAP's coarse resolution averages away.

        For the methodology paper case, you want all three: high Spearman
        (good ranking), small MAE (good absolute), and small bias (not
        systematically off).
        """
    )
    return


if __name__ == "__main__":
    app.run()
