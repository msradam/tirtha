"""Friction-surface construction.

Tobler's hiking function (Tobler 1993) for slope-aware walking cost, plus
hybrid friction that applies walking-on-roads speeds where OSM road pixels
exist. Walking-only convention throughout for comparability with Weiss
et al. (2020) MAP. Walking speeds on roads (5.0 to 6.0 km/h by highway
class) are within the empirical range reported by Knoblauch et al. (1996)
and Bohannon (1997) for comfortable adult pedestrian speeds.

The Tobler equation:
    v_kmh = 6 * exp(-3.5 * |tan(slope_rad) + 0.05|)
    friction_min_per_m = 60 / (v_kmh * 1000)

The FM-blended variant (``fm_blended_friction``) is linear interpolation
between off-road Tobler and on-road walking speeds, weighted by a
foundation-model-predicted P(road). The blending operation is ordinary
lerp; the unusual piece is using an FM-derived road probability as the
weight. We have not found a direct citation for this specific weighting
source. See ``docs/methodology.md`` for the rationale and
``docs/references.md`` for the full bibliography.
"""
from __future__ import annotations

import numpy as np

# Walking speeds on OSM highway classes (km/h). Paved infrastructure is
# slightly faster than off-road Tobler at flat slope; we take min(tobler, road)
# so off-road can be faster than road in some pathological cases (downhill).
WALK_KMH_BY_HIGHWAY_RANK: dict[int, float] = {
    1: 5.0,  # local: residential / service / track / path / footway / pedestrian
    2: 5.5,  # tertiary
    3: 5.5,  # secondary
    4: 6.0,  # primary
    5: 6.0,  # trunk
    6: 6.0,  # motorway
}

# OSM highway tag to integer rank used for rasterization and friction lookup.
HIGHWAY_RANK: dict[str, int] = {
    "motorway": 6,
    "trunk": 5,
    "primary": 4,
    "secondary": 3,
    "tertiary": 2,
    "residential": 1,
    "unclassified": 1,
    "service": 1,
    "track": 1,
    "path": 1,
    "footway": 1,
    "pedestrian": 1,
    "cycleway": 1,
    "steps": 1,
}


def tobler_friction(slope_rad: np.ndarray, *, max_friction_min_per_m: float = 5.0) -> np.ndarray:
    """Compute Tobler off-road friction (min per meter) from slope in radians.

    Args:
        slope_rad: 2D array of slope values in radians.
        max_friction_min_per_m: Cap on friction for extreme slopes. Without
            the cap, impassable terrain produces effectively-infinite cost
            that dominates MCP outputs. Default 5 min/m is about 0.2 km/h.

    Returns:
        2D float32 array of friction values in minutes per meter.
    """
    slope_rad = np.where(np.isfinite(slope_rad), slope_rad, 0.0)
    v_kmh = 6.0 * np.exp(-3.5 * np.abs(np.tan(slope_rad) + 0.05))
    friction = 60.0 / (v_kmh * 1000.0)
    return np.clip(friction, 0.01, max_friction_min_per_m).astype(np.float32)


def hybrid_friction(
    tobler_min_per_m: np.ndarray,
    road_class_rank: np.ndarray,
    *,
    speeds_by_rank: dict[int, float] | None = None,
) -> np.ndarray:
    """Combine off-road Tobler with on-road walking speeds.

    For pixels where ``road_class_rank > 0``, override Tobler with the walking
    speed for that highway rank, but only if it is faster. Downhill off-road
    can still beat an uphill road under Tobler.

    Args:
        tobler_min_per_m: Tobler off-road friction.
        road_class_rank: rasterized OSM highway rank, 0 where no road.
        speeds_by_rank: optional override of the default walking speeds.

    Returns:
        Hybrid friction surface, same shape and dtype.
    """
    speeds = speeds_by_rank or WALK_KMH_BY_HIGHWAY_RANK
    friction = tobler_min_per_m.copy()
    for rank, speed_kmh in speeds.items():
        road_friction = 60.0 / (speed_kmh * 1000.0)
        on_road = road_class_rank == rank
        friction[on_road] = np.minimum(friction[on_road], road_friction)
    return friction


def fm_blended_friction(
    tobler_min_per_m: np.ndarray,
    p_road: np.ndarray,
    *,
    road_walk_kmh: float = 5.5,
) -> np.ndarray:
    """Foundation-model-blended friction.

    Convex combination of off-road Tobler and walking-on-road speeds,
    weighted by FM-predicted P(road). Used when a TerraMind probe has
    produced a per-pixel probability that each pixel is "road-like"
    (dense walkable infrastructure). Bridges rule-based off-road friction
    with learned road detection.
    """
    p = np.clip(p_road, 0.0, 1.0)
    road_friction = 60.0 / (road_walk_kmh * 1000.0)
    return ((1.0 - p) * tobler_min_per_m + p * road_friction).astype(np.float32)


def rank_of_highway_tag(tag) -> int:
    """Map an OSM ``highway`` tag (string or iterable of strings) to its rank.

    Falls back to 1 (local) for unrecognized tags or empty values.
    """
    if isinstance(tag, str):
        return HIGHWAY_RANK.get(tag, 1)
    if hasattr(tag, "__iter__"):
        items = list(tag)
        return HIGHWAY_RANK.get(items[0] if items else "service", 1)
    return 1
