"""Tirtha command-line interface.

Typer-based CLI. The primary command is::

    tirtha accessibility run --region "Brownsville, Brooklyn" --out ./out

which executes the full pipeline and writes a GeoTIFF of walking times,
a JSON of accessibility metrics, and a headline figure. Defaults are tuned
for healthcare destinations; pass ``--destinations`` to override.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from tirtha import __version__

app = typer.Typer(
    help="Tirtha · open humanitarian accessibility mapping. "
    "Walking-time-to-nearest-essential-service for any region of the world.",
    no_args_is_help=True,
)

accessibility_app = typer.Typer(
    help="Accessibility analyses: walking-time-to-X for a region.",
    no_args_is_help=True,
)
app.add_typer(accessibility_app, name="accessibility")


@app.command()
def version() -> None:
    """Print the tirtha version."""
    typer.echo(__version__)


_PRESET_TAGS: dict[str, dict] = {
    "health": {
        "amenity": ["clinic", "hospital", "doctors", "urgent_care", "pharmacy"],
        "healthcare": True,
    },
    "schools": {"amenity": ["school", "kindergarten", "college", "university"]},
    "water": {"amenity": ["drinking_water"], "man_made": ["water_well", "water_tap"]},
    "shelter": {"emergency": ["shelter"], "amenity": ["shelter"]},
}


def _parse_destinations(spec: str | None, preset: str) -> dict:
    """Build an OSMnx tag dict from a ``--destinations`` string or a preset.

    Accepts forms like ``"amenity=clinic|hospital|doctors"`` (single key) or
    falls back to the named preset.
    """
    if spec:
        if "=" not in spec:
            raise typer.BadParameter(
                f"--destinations must be 'key=value|value|...' (got {spec!r})"
            )
        key, vals = spec.split("=", 1)
        return {key.strip(): [v.strip() for v in vals.split("|") if v.strip()]}
    if preset not in _PRESET_TAGS:
        raise typer.BadParameter(
            f"unknown preset {preset!r}; choose one of {sorted(_PRESET_TAGS)}"
        )
    return _PRESET_TAGS[preset]


@accessibility_app.command("run")
def accessibility_run(
    region: str = typer.Option(
        ...,
        "--region",
        "-r",
        help="Region to analyze. Anything OSMnx can geocode — "
        "'Brownsville, Brooklyn', 'Sierra Leone', \"Cox's Bazar, Bangladesh\".",
    ),
    preset: str = typer.Option(
        "health",
        "--preset",
        "-p",
        help="Destination preset: health | schools | water | shelter.",
    ),
    destinations: Optional[str] = typer.Option(
        None,
        "--destinations",
        "-d",
        help="Explicit OSM tag spec like 'amenity=clinic|hospital'. "
        "Overrides --preset if given.",
    ),
    resolution_m: int = typer.Option(
        10, "--resolution", "-R", min=10, max=300, help="Raster resolution in meters."
    ),
    crs: Optional[str] = typer.Option(
        None, "--crs", help="Target CRS (auto-picks UTM zone if not given)."
    ),
    out: Path = typer.Option(
        Path("./out"), "--out", "-o", help="Output directory for rasters + figures."
    ),
    no_figure: bool = typer.Option(False, "--no-figure", help="Skip the headline figure."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress lines."),
) -> None:
    """Run the accessibility pipeline for one region.

    Outputs (in --out):
      - travel_time.tif       Walking-time raster in minutes
      - friction.tif          Friction surface in min/m
      - facilities.geojson    Input destinations
      - metrics.json          Population-weighted accessibility numbers
      - summary.txt           Human-readable summary
      - figures/headline.png  (unless --no-figure)
    """
    from tirtha.io import write_outputs
    from tirtha.pipeline import run_accessibility
    from tirtha.viz import save_headline_figure

    out.mkdir(parents=True, exist_ok=True)
    tag_dict = _parse_destinations(destinations, preset)

    if not quiet:
        typer.echo(f"region:               {region}")
        typer.echo(f"preset:               {preset}{' (overridden)' if destinations else ''}")
        typer.echo(f"destination tag set:  {tag_dict}")
        typer.echo(f"resolution:           {resolution_m} m")
        typer.echo(f"output dir:           {out}")
        typer.echo("")

    result = run_accessibility(
        region=region,
        destination_tags=tag_dict,
        resolution_m=resolution_m,
        crs=crs,
        verbose=not quiet,
    )

    write_outputs(result, out)

    if not no_figure:
        save_headline_figure(result, out / "figures" / "headline.png", title=region)

    typer.echo("")
    typer.echo(f"✓ done. wrote {out}/")
    for k, v in result.accessibility.pct_within.items():
        typer.echo(f"   ≤ {k:3d} min  |  {v:5.1f}% of built area")


@app.command("cache-info")
def cache_info(
    cache_dir: Path = typer.Option(
        Path.home() / ".cache" / "tirtha",
        "--cache-dir",
        help="Tirtha cache directory.",
    ),
) -> None:
    """Print the contents and total size of the tirtha cache."""
    if not cache_dir.exists():
        typer.echo(f"cache empty: {cache_dir} (does not exist yet)")
        return
    total = 0
    for p in cache_dir.rglob("*"):
        if p.is_file():
            sz = p.stat().st_size
            total += sz
            typer.echo(f"{sz / 1e6:8.1f} MB  {p.relative_to(cache_dir)}")
    typer.echo(f"{'-' * 40}")
    typer.echo(f"{total / 1e6:8.1f} MB  total")


if __name__ == "__main__":
    app()
