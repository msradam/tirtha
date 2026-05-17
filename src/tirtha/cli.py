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

graph_app = typer.Typer(
    help="Build, inspect, and export the unified pixel + road graph for a region.",
    no_args_is_help=True,
)
app.add_typer(graph_app, name="graph")


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


def _parse_bbox(spec: str | None) -> tuple[float, float, float, float] | None:
    """Parse a 'W,S,E,N' string into a bbox tuple. Returns None on empty input."""
    if not spec:
        return None
    try:
        parts = [float(p.strip()) for p in spec.split(",")]
    except ValueError as e:
        raise typer.BadParameter(f"--bbox must be 'W,S,E,N' floats (got {spec!r}): {e}")
    if len(parts) != 4:
        raise typer.BadParameter(f"--bbox must have 4 comma-separated floats W,S,E,N (got {spec!r})")
    return tuple(parts)  # type: ignore[return-value]


@accessibility_app.command("run")
def accessibility_run(
    region: str = typer.Option(
        "",
        "--region",
        "-r",
        help="Region name to geocode (e.g. 'Brownsville, Brooklyn'). "
        "Falls back to --bbox if Nominatim has no polygon for the name.",
    ),
    bbox: Optional[str] = typer.Option(
        None,
        "--bbox",
        "-b",
        help="Explicit bbox as 'W,S,E,N' decimal degrees. Overrides --region geocoding. "
        "Useful for places Nominatim doesn't have as a polygon — e.g. neighborhoods, "
        "informal settlements, custom AOIs.",
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
    bbox_tuple = _parse_bbox(bbox)

    if not region and not bbox_tuple:
        raise typer.BadParameter("must specify either --region or --bbox")

    if not quiet:
        typer.echo(f"region:               {region or '(from bbox)'}")
        if bbox_tuple:
            typer.echo(f"bbox (W,S,E,N):       {bbox_tuple}")
        typer.echo(f"preset:               {preset}{' (overridden)' if destinations else ''}")
        typer.echo(f"destination tag set:  {tag_dict}")
        typer.echo(f"resolution:           {resolution_m} m")
        typer.echo(f"output dir:           {out}")
        typer.echo("")

    result = run_accessibility(
        region=region or f"bbox:{bbox_tuple}",
        bbox_override=bbox_tuple,
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


@graph_app.command("build")
def graph_build(
    region: str = typer.Option("", "--region", "-r", help="Region to build the graph for."),
    bbox: Optional[str] = typer.Option(
        None,
        "--bbox",
        "-b",
        help="Explicit bbox as 'W,S,E,N' decimal degrees; overrides --region geocoding.",
    ),
    preset: str = typer.Option(
        "health",
        "--preset",
        "-p",
        help="Destination preset (facilities marked as NODE_FACILITY seeds).",
    ),
    destinations: Optional[str] = typer.Option(
        None,
        "--destinations",
        "-d",
        help="Explicit OSM tag spec; overrides --preset.",
    ),
    resolution_m: int = typer.Option(30, "--resolution", "-R", min=10, max=300),
    crs: Optional[str] = typer.Option(None, "--crs"),
    out: Path = typer.Option(
        Path("./graph.npz"),
        "--out",
        "-o",
        help="Output path for the .npz graph artifact.",
    ),
    no_osmnx_roads: bool = typer.Option(
        False,
        "--no-osmnx-roads",
        help="Skip building OSMnx road-node sub-graph (pixel grid only).",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
) -> None:
    """Build a TirthaGraph artifact for a region and save it to disk.

    The output is a single ``.npz`` file bundling:
      - sparse CSR adjacency matrix (pixel + road edges, joined at coincident locations)
      - per-node attributes: (x, y) coordinates, type (pixel/road/facility), friction
      - facility seed indices
      - metadata: region, CRS, affine, raster shape, pixel size

    Load downstream with::

        from tirtha.graph import load_graph
        g = load_graph("region.graph.npz")
        # then any graph algorithm: scipy.sparse.csgraph, networkx, igraph, ...
    """
    import time

    import xrspatial
    from rasterio.features import rasterize

    from tirtha.data import (
        geocode_region,
        load_dem,
        load_osm_facilities,
        load_osm_roads,
    )
    from tirtha.friction import (
        hybrid_friction,
        rank_of_highway_tag,
        tobler_friction,
    )
    from tirtha.graph import build_graph, save_graph
    from tirtha.pipeline import _utm_zone_for_bbox

    tag_dict = _parse_destinations(destinations, preset)
    bbox_tuple = _parse_bbox(bbox)
    if not region and not bbox_tuple:
        raise typer.BadParameter("must specify either --region or --bbox")
    t0 = time.time()

    if not quiet:
        typer.echo(f"region:        {region or '(from bbox)'}")
        if bbox_tuple:
            typer.echo(f"bbox:          {bbox_tuple}")
        typer.echo(f"resolution:    {resolution_m} m")
        typer.echo(f"destinations:  {tag_dict}")
        typer.echo(f"output:        {out}")
        typer.echo("")
        typer.echo("[1/4] geocoding + DEM + Tobler ...")

    if bbox_tuple is not None:
        bbox_w = bbox_tuple
        boundary = None
    else:
        boundary = geocode_region(region)
        bbox_w = tuple(float(x) for x in boundary.total_bounds)
    crs = crs or _utm_zone_for_bbox(bbox_w)
    elev_da = load_dem(bbox_w, crs=crs, resolution_m=resolution_m)
    H, W = elev_da.shape
    affine = elev_da.odc.geobox.affine
    import numpy as np

    elev = np.where(np.isfinite(elev_da.values), elev_da.values, 0.0).astype(np.float32)
    slope_rad = np.deg2rad(xrspatial.slope(elev_da).values).astype(np.float32)
    tobler = tobler_friction(slope_rad)

    if not quiet:
        typer.echo(f"[2/4] roads ({'including OSMnx graph' if not no_osmnx_roads else 'rasterize only'}) ...")
    roads_gdf = load_osm_roads(bbox_w, crs=crs)
    roads_gdf = roads_gdf.assign(rank=roads_gdf["highway"].apply(rank_of_highway_tag))
    road_class = rasterize(
        zip(roads_gdf.geometry, roads_gdf["rank"]),
        out_shape=(H, W),
        transform=affine,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    friction = hybrid_friction(tobler, road_class)

    osm_graph = None
    if not no_osmnx_roads:
        import osmnx as ox

        try:
            if boundary is not None:
                osm_graph = ox.graph_from_polygon(
                    boundary.geometry.iloc[0],
                    network_type="walk",
                    simplify=True,
                )
            else:
                osm_graph = ox.graph_from_bbox(bbox=bbox_w, network_type="walk", simplify=True)
            osm_graph = ox.project_graph(osm_graph, to_crs=crs)
        except Exception as e:
            typer.echo(f"  WARN: OSMnx graph build failed: {e}; continuing with pixel grid only")

    if not quiet:
        typer.echo("[3/4] facilities ...")
    facilities = load_osm_facilities(bbox_w, crs=crs, tags=tag_dict)
    facility_geoms = list(facilities.geometry) if len(facilities) else None

    if not quiet:
        typer.echo("[4/4] building unified graph ...")
    g = build_graph(
        friction=friction,
        affine=affine,
        crs=crs,
        pixel_size_m=float(resolution_m),
        region=region or f"bbox:{bbox_tuple}",
        road_graph=osm_graph,
        facility_geoms=facility_geoms,
    )
    save_graph(g, out)

    typer.echo("")
    typer.echo(g.summary())
    typer.echo(f"saved → {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    typer.echo(f"total time: {time.time() - t0:.1f}s")


@graph_app.command("inspect")
def graph_inspect(
    path: Path = typer.Argument(..., help="Path to a saved .npz graph artifact."),
) -> None:
    """Print a one-line summary of a saved graph artifact."""
    from tirtha.graph import load_graph

    g = load_graph(path)
    typer.echo(g.summary())


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
