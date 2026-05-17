"""tirtha · TerraMind smoke test (Phase A: polyglot Dataset).

Builds the polyglot xarray Dataset for a ~2.5km square around
Queen Elizabeth Central Hospital, Blantyre, Malawi:

    - Sentinel-2 L2A chip from Microsoft Planetary Computer (via odc-stac)
    - OSM roads + healthcare facilities (via OSMnx)
    - Roads rasterized onto the S2 grid (highway rank as pixel value)

Phase B (TerraMind inference) lives downstream of this; the data
substrate must be correct first.

Run with:
    uv run marimo edit notebooks/01_terramind_smoke.py
"""

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    mo.md(
        """
        # tirtha · TerraMind smoke test — Phase A

        Smallest possible proof: a single xarray `Dataset` holding
        Sentinel-2 raster bands and OSM-rasterized vector data on the
        same coordinate grid, with a sidecar `GeoDataFrame` of facilities
        joining on lat/lon.
        """
    )
    return (mo,)


@app.cell
def _():
    BBOX_LATLON = (34.9939, -15.7976, 35.0177, -15.7746)
    DATE_RANGE = "2024-06-01/2024-09-30"
    MAX_CLOUD_PCT = 10
    TARGET_CRS = "EPSG:32736"
    TARGET_RES_M = 10
    BANDS = ["B02", "B03", "B04", "B08"]
    return BANDS, BBOX_LATLON, DATE_RANGE, MAX_CLOUD_PCT, TARGET_CRS, TARGET_RES_M


@app.cell
def _(BBOX_LATLON, DATE_RANGE, MAX_CLOUD_PCT, mo):
    mo.md(
        f"""
        ## Target

        - **Region**: Blantyre, Malawi — Queen Elizabeth Central Hospital
        - **BBox (W, S, E, N)**: `{BBOX_LATLON}`
        - **Date**: `{DATE_RANGE}` (dry season)
        - **Max cloud**: `{MAX_CLOUD_PCT}%`
        """
    )
    return


@app.cell
def _(BBOX_LATLON, DATE_RANGE, MAX_CLOUD_PCT):
    import planetary_computer
    import pystac_client

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = list(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=BBOX_LATLON,
            datetime=DATE_RANGE,
            query={"eo:cloud_cover": {"lt": MAX_CLOUD_PCT}},
        ).items()
    )
    items.sort(key=lambda i: i.properties["eo:cloud_cover"])
    return catalog, items


@app.cell
def _(items, mo):
    rows = "\n".join(
        f"- `{it.id}` — {it.properties['eo:cloud_cover']:.2f}% clouds, "
        f"{it.properties['datetime'][:10]}"
        for it in items[:5]
    )
    mo.md(
        f"""
        ## STAC search

        Found **{len(items)}** Sentinel-2 L2A scenes. Top 5 by cloud cover:

        {rows}
        """
    )
    return


@app.cell
def _(BANDS, BBOX_LATLON, TARGET_CRS, TARGET_RES_M, items):
    from odc.stac import load
    import odc.geo.xr  # registers the .odc accessor on xarray objects

    s2 = load(
        [items[0]],
        bands=BANDS,
        bbox=BBOX_LATLON,
        crs=TARGET_CRS,
        resolution=TARGET_RES_M,
    ).squeeze("time")
    return load, s2


@app.cell
def _(mo, s2):
    mo.md(
        f"""
        ## Sentinel-2 chip

        Shape: `{dict(s2.sizes)}`
        Pixel size: {s2.odc.geobox.resolution.x:.0f} m
        CRS: `{s2.odc.geobox.crs}`
        Vars: `{list(s2.data_vars)}`
        """
    )
    return


@app.cell
def _(s2):
    import numpy as np

    def to_rgb(ds, percentile=98):
        rgb = np.stack([ds["B04"].values, ds["B03"].values, ds["B02"].values], axis=-1)
        lo, hi = np.percentile(rgb, [2, percentile])
        return np.clip((rgb - lo) / (hi - lo + 1e-9), 0, 1)

    rgb = to_rgb(s2)
    return np, rgb, to_rgb


@app.cell
def _(rgb):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(rgb)
    ax.set_title("Sentinel-2 RGB · Blantyre · dry season 2024")
    ax.set_xticks([])
    ax.set_yticks([])
    fig
    return ax, fig, plt


@app.cell
def _(BBOX_LATLON):
    import osmnx as ox

    roads_gdf = ox.features_from_bbox(
        bbox=BBOX_LATLON,
        tags={"highway": True},
    )
    facilities_gdf = ox.features_from_bbox(
        bbox=BBOX_LATLON,
        tags={"amenity": ["clinic", "hospital", "doctors"]},
    )
    return facilities_gdf, ox, roads_gdf


@app.cell
def _(facilities_gdf, mo, roads_gdf):
    facility_rows = (
        "\n".join(f"- {n}" for n in facilities_gdf.get("name", []).dropna().head(10))
        if "name" in facilities_gdf.columns
        else "(no `name` tags)"
    )
    geom_counts = dict(roads_gdf.geometry.geom_type.value_counts())
    mo.md(
        f"""
        ## OSM vector layers

        - **Road features**: {len(roads_gdf)} ({geom_counts})
        - **Healthcare facilities**: {len(facilities_gdf)}

        Facilities:

        {facility_rows}
        """
    )
    return


@app.cell
def _(TARGET_CRS, roads_gdf, s2):
    from rasterio.features import rasterize

    HIGHWAY_RANK = {
        "motorway": 6, "trunk": 5, "primary": 4, "secondary": 3,
        "tertiary": 2, "residential": 1, "unclassified": 1,
        "service": 1, "track": 1, "path": 1, "footway": 1,
    }

    def rank_of(h):
        if isinstance(h, str):
            return HIGHWAY_RANK.get(h, 1)
        if hasattr(h, "__iter__"):
            xs = list(h)
            return HIGHWAY_RANK.get(xs[0] if xs else "service", 1)
        return 1

    roads_proj = roads_gdf.to_crs(TARGET_CRS)
    lines = roads_proj[
        roads_proj.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ].copy()
    lines["rank"] = lines["highway"].apply(rank_of)

    road_class = rasterize(
        shapes=zip(lines.geometry, lines["rank"]),
        out_shape=(s2.sizes["y"], s2.sizes["x"]),
        transform=s2.odc.geobox.affine,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    return HIGHWAY_RANK, lines, rank_of, rasterize, road_class, roads_proj


@app.cell
def _(np, road_class):
    import matplotlib.pyplot as plt

    fig2, ax2 = plt.subplots(figsize=(7, 7))
    ax2.imshow(road_class, cmap="hot", interpolation="nearest")
    n_road = (road_class > 0).sum()
    pct = 100 * n_road / road_class.size
    ax2.set_title(
        f"Rasterized OSM highways (rank 0–6) · "
        f"{n_road} road px ({pct:.1f}% of grid)"
    )
    ax2.set_xticks([])
    ax2.set_yticks([])
    fig2
    return ax2, fig2, plt


@app.cell
def _(TARGET_CRS, facilities_gdf, road_class, s2):
    ds = s2.assign(road_class=(("y", "x"), road_class))
    ds["road_class"].attrs = {
        "long_name": "OSM highway rank, rasterized",
        "ranks": (
            "0=none, 1=local (residential/service/track/path/footway), "
            "2=tertiary, 3=secondary, 4=primary, 5=trunk, 6=motorway"
        ),
    }
    ds.attrs.update(
        {
            "purpose": "tirtha polyglot dataset smoke test",
            "crs": TARGET_CRS,
            "source_raster": "Microsoft Planetary Computer / Sentinel-2 L2A",
            "source_vector": "OpenStreetMap via OSMnx",
        }
    )

    facilities_proj = facilities_gdf.to_crs(TARGET_CRS)
    return ds, facilities_proj


@app.cell
def _(ds, mo):
    var_lines = "\n".join(
        f"- `{v}` `{dict(ds[v].sizes)}` {ds[v].dtype}"
        for v in ds.data_vars
    )
    mo.md(
        f"""
        ## The polyglot Dataset

        **Variables on the (y, x) grid:**

        {var_lines}

        **Attrs:** `{ds.attrs}`

        Sidecar `facilities_proj` (GeoDataFrame) joins on lat/lon —
        same CRS as the raster.
        """
    )
    return


@app.cell
def _(facilities_proj, plt, rgb, s2):
    fig3, axx = plt.subplots(figsize=(8, 8))
    gbox = s2.odc.geobox
    extent = (
        gbox.affine.c,
        gbox.affine.c + gbox.affine.a * gbox.width,
        gbox.affine.f + gbox.affine.e * gbox.height,
        gbox.affine.f,
    )
    axx.imshow(rgb, extent=extent, origin="upper")
    if len(facilities_proj):
        facilities_proj.geometry.centroid.plot(
            ax=axx, color="cyan", markersize=120,
            edgecolor="black", linewidth=1.5, zorder=3,
        )
    axx.set_title(
        f"Polyglot view · S2 RGB + {len(facilities_proj)} healthcare facilities"
    )
    axx.set_xticks([])
    axx.set_yticks([])
    fig3
    return axx, extent, fig3, gbox


@app.cell
def _(mo):
    mo.md(
        """
        ## Status

        - ✅ STAC search + Sentinel-2 chip via odc-stac
        - ✅ OSM roads + healthcare facilities via OSMnx
        - ✅ Vector → raster rasterization (`road_class`)
        - ✅ Polyglot xarray Dataset assembled
        - ⏸️ **Phase B: TerraMind inference** — pending ML deps install
          (`uv sync --extra ml`) and TerraMind-Small weight download

        If you can see a reasonable RGB image of Blantyre with road
        overlay and facility markers, the data substrate works.
        Next step: feed `ds[BANDS]` to TerraMind-Small and add
        `terramind_embeddings(y, x, embed)` as a new variable.
        """
    )
    return


if __name__ == "__main__":
    app.run()
