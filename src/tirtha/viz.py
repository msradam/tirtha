"""Headline-figure generation for ``tirtha accessibility run``.

A compact 4-panel figure: travel-time raster, isochrones on RGB, accessibility
curve, threshold bars. Designed for both quick eyeballing and inclusion in
README / reports.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def save_headline_figure(result, path: Path, title: str | None = None) -> None:
    """Write a 4-panel summary figure for a PipelineResult."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tt = result.travel_time_min
    friction = result.friction_min_per_m
    H, W = tt.shape
    facilities = result.facilities_proj

    vmax = np.nanpercentile(tt, 99) if np.isfinite(np.nanpercentile(tt, 99)) else 30.0

    fig, axes = plt.subplots(2, 2, figsize=(13, 11))

    # --- 1. Travel-time raster + facilities ---
    ax = axes[0, 0]
    im = ax.imshow(tt, cmap="magma_r", vmin=0, vmax=vmax)
    if hasattr(facilities, "geometry") and len(facilities) > 0:
        # Convert centroids to raster row/col for plotting on top of imshow
        try:
            xs = facilities.geometry.centroid.x.to_numpy()
            ys = facilities.geometry.centroid.y.to_numpy()
            minx, miny, maxx, maxy = result.bbox_wsen
            cols = ((xs - minx) / (maxx - minx + 1e-9) * W).astype(float)
            rows = ((maxy - ys) / (maxy - miny + 1e-9) * H).astype(float)
            inside = (cols >= 0) & (cols < W) & (rows >= 0) & (rows < H)
            ax.scatter(cols[inside], rows[inside], marker="P", s=80, c="cyan",
                       edgecolor="black", linewidth=1)
        except Exception:
            pass
    ax.set_title(
        f"walking time to nearest destination\n"
        f"mean {np.nanmean(tt):.1f} min, max {np.nanmax(tt):.1f} min"
    )
    ax.set_xticks([])
    ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.045, label="minutes")

    # --- 2. Friction surface ---
    ax = axes[0, 1]
    im2 = ax.imshow(
        friction,
        cmap="cividis_r",
        vmin=np.nanpercentile(friction, 1),
        vmax=np.nanpercentile(friction, 98),
    )
    ax.set_title("hybrid friction surface\nTobler off-road + walking on roads")
    ax.set_xticks([])
    ax.set_yticks([])
    plt.colorbar(im2, ax=ax, fraction=0.045, label="min/m")

    # --- 3. Accessibility curve ---
    ax = axes[1, 0]
    thresholds = sorted(result.accessibility.thresholds_min)
    pcts = [result.accessibility.pct_within[t] for t in thresholds]
    ax.plot(thresholds, pcts, "o-", color="#2a9d8f", linewidth=2.5, markersize=9)
    for x in (15, 30, 60):
        ax.axvline(x, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("walking time threshold (min)")
    ax.set_ylabel("% built area within")
    ax.set_title("cumulative accessibility (built-area weighted)")
    ax.set_ylim(0, 105)
    ax.grid(alpha=0.3)

    # --- 4. Bar of threshold percentages ---
    ax = axes[1, 1]
    bars = ax.bar(range(len(thresholds)), pcts, color="#2a9d8f", edgecolor="black")
    for i, v in enumerate(pcts):
        ax.text(i, v + 1, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(range(len(thresholds)))
    ax.set_xticklabels([f"≤{t}" for t in thresholds])
    ax.set_xlabel("walking time (min)")
    ax.set_ylabel("% built area")
    ax.set_title("accessibility by threshold")
    ax.set_ylim(0, max(pcts) * 1.1 + 5)
    ax.grid(alpha=0.3, axis="y")

    suptitle = f"tirtha · {title or result.region}"
    fig.suptitle(suptitle, fontsize=13, y=0.995)
    plt.tight_layout()
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
