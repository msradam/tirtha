"""TerraMind foundation-model embeddings.

Wraps IBM/ESA's TerraMind (Jakubik et al. 2025; arXiv:2504.11171) via
terratorch for per-pixel friction estimation. Multimodal input (Sentinel-2
L2A optical, Sentinel-1 RTC SAR, NASADEM elevation) produces (14, 14, D)
patch embeddings over 224x224 chips. A linear probe trained in-place
against the rasterized OSM road network turns those embeddings into
per-pixel P(road), which we blend with Tobler off-road friction in
``tirtha.friction.fm_blended_friction``.

The frozen-feature-extractor pattern is standard for transfer learning,
and pretrained vision features for traversability have been used in
robotics (Frey et al. 2023, Rana et al. 2026 OVerSeeC). We have not
found a citation for the specific application to humanitarian
accessibility friction. See ``docs/methodology.md`` for rationale and
``docs/references.md`` for the TerraMind paper citation.

This is the "FM-supervised friction" path described in docs/methodology.md.
Requires the ``[ml]`` extra (torch + terratorch + huggingface_hub).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# TerraMind v1 pretraining stats (sourced from
# terratorch.models.backbones.terramind.model.terramind_register)
# ---------------------------------------------------------------------------

# Sentinel-2 L2A: 12 bands in TerraMind order.
#   B01 (coastal), B02 (blue), B03 (green), B04 (red),
#   B05 / B06 / B07 (red-edge 1-3), B08 (NIR), B8A (NIR narrow),
#   B09 (water vapor), B11 / B12 (SWIR 1-2).
S2L2A_BAND_ORDER: tuple[str, ...] = (
    "B01", "B02", "B03", "B04", "B05", "B06", "B07",
    "B08", "B8A", "B09", "B11", "B12",
)
S2L2A_MEAN = np.array(
    [1390.458, 1503.317, 1718.197, 1853.91, 2199.1, 2779.975,
     2987.011, 3083.234, 3132.22, 3162.988, 2424.884, 1857.648],
    dtype=np.float32,
).reshape(12, 1, 1)
S2L2A_STD = np.array(
    [2106.761, 2141.107, 2038.973, 2134.138, 2085.321, 1889.926,
     1820.257, 1871.918, 1753.829, 1797.379, 1434.261, 1334.311],
    dtype=np.float32,
).reshape(12, 1, 1)

# Sentinel-1 GRD/RTC: 2 bands (VV, VH) in dB after 10*log10 of linear power.
S1_MEAN = np.array([-12.599, -20.293], dtype=np.float32).reshape(2, 1, 1)
S1_STD = np.array([5.195, 5.890], dtype=np.float32).reshape(2, 1, 1)

# NASADEM: 1 band (meters).
DEM_MEAN = np.float32(435.726)
DEM_STD = np.float32(560.326)

# TerraMind input geometry: fixed at 224x224 pixels, 16x16 patches, 14x14 patch grid.
TERRAMIND_INPUT_PX: int = 224
TERRAMIND_PATCH_PX: int = 16
TERRAMIND_PATCH_GRID: int = TERRAMIND_INPUT_PX // TERRAMIND_PATCH_PX  # 14


# ---------------------------------------------------------------------------
# Optional-import guard
# ---------------------------------------------------------------------------


def _require_ml_extras() -> None:
    """Raise a helpful error if the [ml] extra is not installed."""
    try:
        import terratorch  # noqa: F401
        import torch  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "TerraMind support requires the [ml] extra. Install with:\n"
            "    uv sync --extra ml\n"
            "(or pip install 'tirtha[ml]'). Underlying error: " + str(e)
        ) from e


# ---------------------------------------------------------------------------
# Multimodal chip fetch + normalization
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MultimodalChip:
    """A center-cropped 224×224 multimodal input ready for TerraMind."""

    s2: np.ndarray  # (12, 224, 224), float32, v1-normalized
    s1: np.ndarray  # (2, 224, 224),  float32, v1-normalized
    dem: np.ndarray  # (1, 224, 224), float32, v1-normalized
    y0: int  # top-left row of the 224x224 crop within the full chip
    x0: int  # top-left col


def fetch_multimodal_chip(
    bbox: tuple[float, float, float, float],
    crs: str,
    resolution_m: int = 10,
    date_range_s2: str = "2024-04-01/2024-10-15",
    date_range_s1: str = "2024-04-01/2024-10-15",
    max_cloud_pct: int = 15,
) -> MultimodalChip:
    """Fetch and normalize a TerraMind-ready 224×224 multimodal chip.

    Pulls the lowest-cloud Sentinel-2 L2A scene (12 bands) and the closest
    Sentinel-1 RTC scene over the bbox, plus NASADEM. Crops to the center
    224×224 in pixel space; raises if the bbox at the given resolution doesn't
    reach 224×224 (TerraMind requires the fixed input size).
    """
    import odc.geo.xr  # noqa: F401
    import planetary_computer
    import pystac_client
    from odc.stac import load

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    # --- Sentinel-2 L2A (12 bands) ----------------------------------------
    s2_items = sorted(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=date_range_s2,
            query={"eo:cloud_cover": {"lt": max_cloud_pct}},
        ).items(),
        key=lambda i: i.properties["eo:cloud_cover"],
    )
    if not s2_items:
        raise RuntimeError(f"No Sentinel-2 scenes for {bbox} (cloud<{max_cloud_pct}%).")
    s2_ds = load(
        [s2_items[0]],
        bands=list(S2L2A_BAND_ORDER),
        bbox=bbox,
        crs=crs,
        resolution=resolution_m,
    ).squeeze("time")

    s2_full = np.stack(
        [s2_ds[b].values for b in S2L2A_BAND_ORDER], axis=0
    ).astype(np.float32)
    H, W = s2_full.shape[-2:]
    if H < TERRAMIND_INPUT_PX or W < TERRAMIND_INPUT_PX:
        raise ValueError(
            f"Multimodal chip is {H}×{W}px at {resolution_m}m; TerraMind requires "
            f"≥ {TERRAMIND_INPUT_PX}×{TERRAMIND_INPUT_PX}. Expand --bbox or lower "
            f"--resolution to fit the input."
        )

    # --- Sentinel-1 RTC (VV, VH; dB) --------------------------------------
    s1_items = sorted(
        catalog.search(
            collections=["sentinel-1-rtc"],
            bbox=bbox,
            datetime=date_range_s1,
        ).items(),
        key=lambda i: i.properties["datetime"],
    )
    if not s1_items:
        raise RuntimeError(f"No Sentinel-1 RTC scenes for {bbox}.")
    s1_ds = load(
        [s1_items[0]],
        bands=["vv", "vh"],
        bbox=bbox,
        crs=crs,
        resolution=resolution_m,
    ).squeeze("time")
    s1_lin = np.stack([s1_ds["vv"].values, s1_ds["vh"].values], axis=0).astype(np.float32)
    s1_db = 10.0 * np.log10(np.clip(s1_lin, 1e-6, None))

    # --- NASADEM ----------------------------------------------------------
    dem_items = list(catalog.search(collections=["nasadem"], bbox=bbox).items())
    if not dem_items:
        raise RuntimeError(f"No NASADEM tiles for {bbox}.")
    dem_ds = load(dem_items, bands=["elevation"], bbox=bbox, crs=crs, resolution=resolution_m).squeeze(
        "time", drop=True
    )
    dem = np.where(np.isfinite(dem_ds["elevation"].values), dem_ds["elevation"].values, 0.0).astype(
        np.float32
    )

    # --- Center-crop everything to 224×224 ---------------------------------
    y0 = (H - TERRAMIND_INPUT_PX) // 2
    x0 = (W - TERRAMIND_INPUT_PX) // 2
    s2_crop = s2_full[:, y0 : y0 + TERRAMIND_INPUT_PX, x0 : x0 + TERRAMIND_INPUT_PX]
    s1_crop = s1_db[:, y0 : y0 + TERRAMIND_INPUT_PX, x0 : x0 + TERRAMIND_INPUT_PX]
    dem_crop = dem[y0 : y0 + TERRAMIND_INPUT_PX, x0 : x0 + TERRAMIND_INPUT_PX][None, ...]

    # --- Normalize with v1 pretraining stats ------------------------------
    s2_norm = (s2_crop - S2L2A_MEAN) / S2L2A_STD
    s1_norm = (s1_crop - S1_MEAN) / S1_STD
    dem_norm = (dem_crop - DEM_MEAN) / DEM_STD

    return MultimodalChip(s2=s2_norm, s1=s1_norm, dem=dem_norm, y0=y0, x0=x0)


# ---------------------------------------------------------------------------
# TerraMind model build + inference
# ---------------------------------------------------------------------------


def load_terramind(
    variant: str = "terramind_v1_small",
    modalities: Iterable[str] = ("S2L2A", "S1GRD", "DEM"),
):
    """Build a pretrained TerraMind backbone via terratorch's BACKBONE_REGISTRY.

    First call downloads weights from HuggingFace (~80 MB for ``small``).
    """
    _require_ml_extras()
    import torch
    from terratorch import BACKBONE_REGISTRY

    model = BACKBONE_REGISTRY.build(
        variant,
        pretrained=True,
        modalities=list(modalities),
    ).eval()
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )
    return model.to(device), device


def run_terramind_inference(model, device, chip: MultimodalChip) -> np.ndarray:
    """Run TerraMind on the multimodal chip; return (14, 14, D) patch grid."""
    _require_ml_extras()
    import torch

    inputs = {
        "S2L2A": torch.from_numpy(chip.s2).unsqueeze(0).to(device),
        "S1GRD": torch.from_numpy(chip.s1).unsqueeze(0).to(device),
        "DEM": torch.from_numpy(chip.dem).unsqueeze(0).to(device),
    }
    with torch.no_grad():
        out = model(inputs)
    last = out[-1].squeeze(0).cpu().numpy()  # (196, D)
    D = last.shape[-1]
    return last.reshape(TERRAMIND_PATCH_GRID, TERRAMIND_PATCH_GRID, D)


# ---------------------------------------------------------------------------
# Probe: embeddings → P(road)
# ---------------------------------------------------------------------------


def train_road_probe_in_chip(
    emb_patches: np.ndarray,
    road_class_224: np.ndarray,
    *,
    min_road_fraction: float = 0.05,
) -> np.ndarray:
    """Train an in-chip logistic regression probe and return per-patch P(road).

    The probe is trained on the same patches it then predicts on. This is
    a fast distillation from OSM rather than independent generalization,
    but it lets us use TerraMind's multimodal representation to identify
    walkable-infrastructure pixels that OSM tagging may underrepresent.

    Args:
        emb_patches: (14, 14, D) per-patch embeddings.
        road_class_224: (224, 224) rasterized OSM highway ranks.
        min_road_fraction: patch is labeled "has road" if ≥ this fraction of
            its 16×16 pixels are on a road.

    Returns:
        (14, 14) array of P(road) ∈ [0, 1] per patch.
    """
    from sklearn.linear_model import LogisticRegression

    if road_class_224.shape != (TERRAMIND_INPUT_PX, TERRAMIND_INPUT_PX):
        raise ValueError(
            f"road_class_224 must be {TERRAMIND_INPUT_PX}×{TERRAMIND_INPUT_PX}, "
            f"got {road_class_224.shape}"
        )

    patches = road_class_224.reshape(
        TERRAMIND_PATCH_GRID, TERRAMIND_PATCH_PX, TERRAMIND_PATCH_GRID, TERRAMIND_PATCH_PX
    ).transpose(0, 2, 1, 3)
    patch_road_frac = (patches > 0).mean(axis=(2, 3))  # (14, 14)
    y = (patch_road_frac.flatten() >= min_road_fraction).astype(int)
    X = emb_patches.reshape(-1, emb_patches.shape[-1])

    if y.sum() < 5 or y.sum() > len(y) - 5:
        # Degenerate label distribution. Fall back to label fraction directly.
        # (Almost-all-road or almost-no-road chips don't need a probe.)
        return patch_road_frac.astype(np.float32)

    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    clf.fit(X, y)
    p = clf.predict_proba(X)[:, 1]
    return p.reshape(TERRAMIND_PATCH_GRID, TERRAMIND_PATCH_GRID).astype(np.float32)


def upsample_patches_to_pixels(
    patches: np.ndarray, patch_px: int = TERRAMIND_PATCH_PX
) -> np.ndarray:
    """Upsample a (G, G) patch grid to (G * patch_px, G * patch_px) by repeat."""
    return np.repeat(np.repeat(patches, patch_px, axis=0), patch_px, axis=1)


def pad_to_full_raster(
    p_road_224: np.ndarray, full_shape: tuple[int, int], y0: int, x0: int, fill: float = 0.0
) -> np.ndarray:
    """Embed a (224, 224) probe map back into a larger raster, padded with ``fill``."""
    H, W = full_shape
    out = np.full((H, W), fill, dtype=np.float32)
    out[y0 : y0 + TERRAMIND_INPUT_PX, x0 : x0 + TERRAMIND_INPUT_PX] = p_road_224
    return out


def estimate_p_road_from_chip(
    bbox: tuple[float, float, float, float],
    crs: str,
    resolution_m: int,
    road_class_full: np.ndarray,
    full_shape: tuple[int, int],
    variant: str = "terramind_v1_small",
    *,
    verbose: bool = True,
) -> np.ndarray:
    """End-to-end TerraMind P(road) estimate for a chip.

    1. Fetch multimodal S2 + S1 + DEM chip, center-cropped to 224×224.
    2. Load TerraMind, run inference → (14, 14, D) embeddings.
    3. Train in-chip linear probe against the rasterized OSM road network
       restricted to the same 224×224 region.
    4. Upsample patch P(road) to (224, 224) and pad back to the full raster
       shape, using the OSM road raster as fallback outside the probe region.

    Returns:
        (H, W) float32 array of P(road) ∈ [0, 1] across the full raster.
    """
    if verbose:
        print("[fm] fetching multimodal chip (S2 + S1 + DEM)...")
    chip = fetch_multimodal_chip(bbox=bbox, crs=crs, resolution_m=resolution_m)

    if verbose:
        print(f"[fm] loading {variant} ...")
    model, device = load_terramind(variant=variant)

    if verbose:
        print("[fm] running inference ...")
    emb_patches = run_terramind_inference(model, device, chip)

    if verbose:
        print("[fm] training in-chip road probe ...")
    road_class_224 = road_class_full[
        chip.y0 : chip.y0 + TERRAMIND_INPUT_PX,
        chip.x0 : chip.x0 + TERRAMIND_INPUT_PX,
    ]
    p_patch = train_road_probe_in_chip(emb_patches, road_class_224)
    p_pixel_224 = upsample_patches_to_pixels(p_patch)

    # Fallback outside the 224×224 region: use OSM road mask directly.
    fallback = (road_class_full > 0).astype(np.float32)
    p_full = fallback.copy()
    p_full[
        chip.y0 : chip.y0 + TERRAMIND_INPUT_PX,
        chip.x0 : chip.x0 + TERRAMIND_INPUT_PX,
    ] = p_pixel_224
    return p_full
