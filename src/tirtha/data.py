"""Data loaders — all public infrastructure, no paid APIs, no registration walls.

Sentinel-1/2 + NASADEM via Microsoft Planetary Computer STAC.
OSM roads, healthcare amenities, buildings via OSMnx.
WorldPop UN-adjusted population from data.worldpop.org.
MAP 2020 walking-only travel-time raster from data.malariaatlas.org.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

# ---------------------------------------------------------------------------
# Sentinel-2 / Sentinel-1 / NASADEM via Microsoft Planetary Computer
# ---------------------------------------------------------------------------


def _pc_catalog():
    """Lazy import + return signed STAC client for Microsoft Planetary Computer."""
    import planetary_computer
    import pystac_client

    return pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )


def load_dem(
    bbox: tuple[float, float, float, float],
    crs: str,
    resolution_m: int,
):
    """Load NASADEM elevation at target resolution for a bbox (W, S, E, N).

    Returns an ``xarray.DataArray`` of elevation in meters.
    """
    import odc.geo.xr  # noqa: F401 — registers .odc accessor
    from odc.stac import load

    catalog = _pc_catalog()
    items = list(catalog.search(collections=["nasadem"], bbox=bbox).items())
    if not items:
        raise RuntimeError(f"No NASADEM tiles for bbox {bbox}")
    ds = load(items, bands=["elevation"], bbox=bbox, crs=crs, resolution=resolution_m).squeeze(
        "time", drop=True
    )
    return ds["elevation"]


def load_sentinel2_rgb(
    bbox: tuple[float, float, float, float],
    crs: str,
    resolution_m: int,
    date_range: str = "2024-04-01/2024-10-15",
    max_cloud_pct: int = 15,
):
    """Load lowest-cloud Sentinel-2 L2A RGB chip via Planetary Computer.

    Returns the xarray Dataset with B02/B03/B04 bands.
    """
    import odc.geo.xr  # noqa: F401
    from odc.stac import load

    catalog = _pc_catalog()
    items = sorted(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=date_range,
            query={"eo:cloud_cover": {"lt": max_cloud_pct}},
        ).items(),
        key=lambda i: i.properties["eo:cloud_cover"],
    )
    if not items:
        raise RuntimeError(f"No Sentinel-2 scenes for bbox {bbox} (cloud<{max_cloud_pct}%)")
    return load([items[0]], bands=["B02", "B03", "B04"], bbox=bbox, crs=crs, resolution=resolution_m).squeeze(
        "time"
    )


# ---------------------------------------------------------------------------
# OpenStreetMap via OSMnx
# ---------------------------------------------------------------------------


def load_osm_roads(bbox: tuple[float, float, float, float], crs: str):
    """Fetch all OSM highway features within bbox; project to ``crs``.

    Returns a GeoDataFrame of LineString geometries with a ``highway`` column.
    """
    import osmnx as ox

    gdf = ox.features_from_bbox(bbox=bbox, tags={"highway": True}).to_crs(crs)
    return gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]


def load_osm_facilities(
    bbox: tuple[float, float, float, float],
    crs: str,
    tags: dict | None = None,
):
    """Fetch OSM healthcare facilities (or other tagged amenity set) within bbox.

    Default tags match the healthcare preset; pass an explicit ``tags`` dict
    to use this loader for schools, water points, shelters, etc.
    """
    import osmnx as ox

    if tags is None:
        tags = {
            "amenity": ["clinic", "hospital", "doctors", "urgent_care", "pharmacy"],
            "healthcare": True,
        }
    return ox.features_from_bbox(bbox=bbox, tags=tags).to_crs(crs)


def load_osm_buildings(bbox: tuple[float, float, float, float], crs: str):
    """Fetch OSM building footprints — usable as a population proxy."""
    import osmnx as ox

    return ox.features_from_bbox(bbox=bbox, tags={"building": True}).to_crs(crs)


def geocode_region(region: str):
    """Geocode a free-text region name to a boundary GeoDataFrame.

    Examples: "Sierra Leone", "Brooklyn, NYC", "Brownsville, Brooklyn".
    """
    import osmnx as ox

    return ox.geocode_to_gdf(region)


# ---------------------------------------------------------------------------
# WorldPop
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorldPopSource:
    """A WorldPop dataset slug. ``maxar_v1`` is constrained, LMIC-focused; for
    HIC countries the right product is different (BSGM, ACS-tract, HRSL).
    """

    iso3: str
    year: int = 2020
    product: str = "maxar_v1"  # "maxar_v1" (LMIC constrained) or "BSGM"

    @property
    def url(self) -> str:
        return (
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/"
            f"{self.year}/{self.product}/{self.iso3.upper()}/"
            f"{self.iso3.lower()}_ppp_{self.year}_UNadj_constrained.tif"
        )


def download_worldpop(source: WorldPopSource, cache_dir: str | os.PathLike) -> str:
    """Download a WorldPop UN-adjusted population raster to ``cache_dir``.

    Returns the local path. Raises if the WorldPop server returns non-200 (the
    HIC vs LMIC product mismatch is a common reason — see ``WorldPopSource``).
    """
    cache_dir = os.fspath(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{source.iso3.lower()}_pop_{source.year}.tif")
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return path
    r = requests.get(source.url, timeout=600, stream=True)
    r.raise_for_status()  # important — we silently wrote 0-byte files before
    with open(path, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    if os.path.getsize(path) < 1024:
        os.remove(path)
        raise RuntimeError(
            f"WorldPop download returned suspiciously small file for {source.iso3}; "
            f"check that the product path ({source.product}) exists for that country."
        )
    return path


# ---------------------------------------------------------------------------
# MAP 2020 walking-only travel-time raster (Weiss et al., Nature Medicine)
# ---------------------------------------------------------------------------


MAP_2020_WALKING_URL = (
    "https://data.malariaatlas.org/geoserver/ows"
    "?service=CSW&version=2.0.1&request=DirectDownload"
    "&ResourceId=Explorer:2020_walking_only_travel_time_to_healthcare"
)


def download_map_2020_walking(cache_dir: str | os.PathLike) -> str:
    """Download the global Weiss et al. 2020 walking-only travel-time raster.

    ~460 MB GeoTIFF inside a zip. Cached after first download.
    """
    import zipfile

    cache_dir = os.fspath(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    tif_path = os.path.join(cache_dir, "2020_walking_only_travel_time_to_healthcare.geotiff")
    zip_path = os.path.join(cache_dir, "map_walking_2020.zip")

    if os.path.exists(tif_path) and os.path.getsize(tif_path) > 1_000_000:
        return tif_path

    if not (os.path.exists(zip_path) and os.path.getsize(zip_path) > 100_000_000):
        r = requests.get(MAP_2020_WALKING_URL, timeout=600, stream=True)
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(cache_dir)
    return tif_path
