"""The polyglot graph artifact.

A first-class graph object that exposes "the image is a graph" as a real
loadable artifact, not an implicit routing internal. The fusion methodology
(on-road graph stitched to off-road raster) follows Ray & Ebener (2008) on
AccessMod; the contribution here is exposing it as a single loadable
``scipy.sparse.csr_matrix`` plus per-node attributes, so downstream code
can run any graph algorithm without rebuilding the geometry.

Two paradigms unified at ``(x, y)`` coordinates:

  - **Pixel nodes**: one per friction-raster cell, attribute = friction.
    Adjacency = 8-connected, weight = avg(friction) * pixel_distance.
  - **Road nodes**: OSMnx graph intersections, attribute = highway class.
    Adjacency = OSM segment geometries, weight = length / walking_speed.
  - **Join edges**: each road node connects to its containing pixel at
    zero cost (so off-road walking can ascend to the road network and
    use vector-precise routing once on a road).

The result is a single ``scipy.sparse.csr_matrix`` describing the merged
graph, plus a node-features array recording type and coordinates. Save
with ``save_graph(g, path)``, load with ``load_graph(path)``; downstream
code can run any graph algorithm (Dijkstra, betweenness centrality,
community detection) without having to reconstruct the geometry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.sparse as sp

# Node-type constants, kept as small ints for compact node-features arrays.
NODE_PIXEL: int = 0
NODE_ROAD: int = 1
NODE_FACILITY: int = 2  # destination seed marker (a pixel that also has a destination)


@dataclass
class TirthaGraph:
    """A unified pixel + OSM-road graph for a single region.

    Attributes:
        adj: sparse CSR adjacency matrix; ``adj[i, j]`` = edge weight in minutes.
        node_xy: float32 array, shape ``(N, 2)``, columns = (x, y) in ``crs``.
        node_type: uint8 array, shape ``(N,)``; values in {NODE_PIXEL, NODE_ROAD, NODE_FACILITY}.
        node_friction: float32, shape ``(N,)``; pixel friction (min/m) or
            walking-time-per-meter equivalent for road nodes. NaN where N/A.
        crs: CRS string (e.g. ``"EPSG:32618"``).
        affine: rasterio/odc-geo Affine for the source raster, as a 6-tuple
            ``(a, b, c, d, e, f)``.
        raster_shape: ``(H, W)`` of the source friction raster.
        pixel_size_m: pixel side length in meters.
        region: human-readable region name.
        facility_node_ids: ndarray of node indices that are facility seeds.
    """

    adj: sp.csr_matrix
    node_xy: np.ndarray
    node_type: np.ndarray
    node_friction: np.ndarray
    crs: str
    affine: tuple[float, float, float, float, float, float]
    raster_shape: tuple[int, int]
    pixel_size_m: float
    region: str
    facility_node_ids: np.ndarray

    @property
    def n_nodes(self) -> int:
        return int(self.node_xy.shape[0])

    @property
    def n_pixel_nodes(self) -> int:
        return int((self.node_type == NODE_PIXEL).sum() + (self.node_type == NODE_FACILITY).sum())

    @property
    def n_road_nodes(self) -> int:
        return int((self.node_type == NODE_ROAD).sum())

    def summary(self) -> str:
        H, W = self.raster_shape
        return (
            f"TirthaGraph[{self.region}] · {H}×{W}px @ {self.pixel_size_m:.0f}m · "
            f"{self.n_nodes:,} nodes ({self.n_pixel_nodes:,} pixel + {self.n_road_nodes:,} road) · "
            f"{self.adj.nnz:,} edges · {len(self.facility_node_ids)} facility seeds · {self.crs}"
        )


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------


def _pixel_grid_edges(
    friction: np.ndarray, pixel_size_m: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized 8-connected pixel-pixel edges.

    Edge weight = ``(friction[a] + friction[b]) / 2 * dist``  (units: minutes).
    """
    H, W = friction.shape
    diag = pixel_size_m * np.sqrt(2.0)
    neighbours = [
        (-1, -1, diag), (-1, 0, pixel_size_m), (-1, 1, diag),
        (0, -1, pixel_size_m),                    (0, 1, pixel_size_m),
        (1, -1, diag), (1, 0, pixel_size_m), (1, 1, diag),
    ]
    rows_list, cols_list, data_list = [], [], []
    for dy, dx, dist in neighbours:
        ys = max(0, -dy)
        ye = H - max(0, dy)
        xs = max(0, -dx)
        xe = W - max(0, dx)
        ya, yb = ys + dy, ye + dy
        xa, xb = xs + dx, xe + dx
        src = (np.arange(ys, ye)[:, None] * W + np.arange(xs, xe)[None, :]).ravel()
        dst = (np.arange(ya, yb)[:, None] * W + np.arange(xa, xb)[None, :]).ravel()
        f_src = friction[ys:ye, xs:xe].ravel()
        f_dst = friction[ya:yb, xa:xb].ravel()
        w = (f_src + f_dst) * 0.5 * dist
        rows_list.append(src)
        cols_list.append(dst)
        data_list.append(w)
    return (
        np.concatenate(rows_list).astype(np.int64),
        np.concatenate(cols_list).astype(np.int64),
        np.concatenate(data_list).astype(np.float64),
    )


def _xy_to_rowcol(x: float, y: float, affine) -> tuple[int, int]:
    col = int((x - affine.c) / affine.a)
    row = int((y - affine.f) / affine.e)
    return row, col


def build_graph(
    friction: np.ndarray,
    affine,
    crs: str,
    pixel_size_m: float,
    region: str,
    road_graph=None,
    facility_geoms=None,
    walking_kmh_on_road: float = 5.5,
) -> TirthaGraph:
    """Build a unified pixel + road graph for a region.

    Args:
        friction: 2D friction surface (min/m), shape ``(H, W)``.
        affine: rasterio/odc-geo Affine transform for ``friction``.
        crs: CRS string.
        pixel_size_m: pixel side in meters.
        region: human-readable region name (for the artifact metadata).
        road_graph: optional ``networkx.MultiDiGraph`` from OSMnx (already
            projected to ``crs``). If provided, road nodes/edges are added
            and joined to their containing pixels.
        facility_geoms: optional iterable of shapely geometries representing
            destination facilities. The pixels containing them are marked
            ``NODE_FACILITY``.
        walking_kmh_on_road: walking speed used to convert OSM edge lengths
            (in meters) into edge weights (in minutes).

    Returns:
        ``TirthaGraph`` instance.
    """
    H, W = friction.shape
    N_pix = H * W

    # 1. Pixel-pixel edges
    rows_pp, cols_pp, data_pp = _pixel_grid_edges(friction, pixel_size_m)

    # 2. Road-road edges (from OSMnx graph, if provided)
    rows_rr = np.empty(0, dtype=np.int64)
    cols_rr = np.empty(0, dtype=np.int64)
    data_rr = np.empty(0, dtype=np.float64)
    road_node_xy: list[tuple[float, float]] = []
    road_node_id_map: dict = {}  # OSM node id → tirtha node index
    rows_join = np.empty(0, dtype=np.int64)
    cols_join = np.empty(0, dtype=np.int64)
    data_join = np.empty(0, dtype=np.float64)

    if road_graph is not None:
        # Build the node-id map first
        osm_nodes = list(road_graph.nodes(data=True))
        for i, (nid, ndata) in enumerate(osm_nodes):
            road_node_id_map[nid] = i
            road_node_xy.append((float(ndata.get("x", 0.0)), float(ndata.get("y", 0.0))))

        # Road-road edges
        rr_rows, rr_cols, rr_data = [], [], []
        for u, v, edata in road_graph.edges(data=True):
            if u not in road_node_id_map or v not in road_node_id_map:
                continue
            length_m = float(edata.get("length", 1.0))
            travel_min = (length_m / 1000.0) / walking_kmh_on_road * 60.0
            iu = N_pix + road_node_id_map[u]
            iv = N_pix + road_node_id_map[v]
            rr_rows.extend([iu, iv])
            rr_cols.extend([iv, iu])
            rr_data.extend([travel_min, travel_min])
        if rr_rows:
            rows_rr = np.array(rr_rows, dtype=np.int64)
            cols_rr = np.array(rr_cols, dtype=np.int64)
            data_rr = np.array(rr_data, dtype=np.float64)

        # Pixel ↔ road join edges (zero-cost at coincident locations)
        j_rows, j_cols = [], []
        for i, (x, y) in enumerate(road_node_xy):
            row, col = _xy_to_rowcol(x, y, affine)
            if 0 <= row < H and 0 <= col < W:
                pix_idx = row * W + col
                rn_idx = N_pix + i
                j_rows.extend([pix_idx, rn_idx])
                j_cols.extend([rn_idx, pix_idx])
        if j_rows:
            rows_join = np.array(j_rows, dtype=np.int64)
            cols_join = np.array(j_cols, dtype=np.int64)
            data_join = np.zeros(len(j_rows), dtype=np.float64)

    R = len(road_node_xy)
    N_total = N_pix + R

    # 3. Assemble sparse adjacency
    all_rows = np.concatenate([rows_pp, rows_rr, rows_join])
    all_cols = np.concatenate([cols_pp, cols_rr, cols_join])
    all_data = np.concatenate([data_pp, data_rr, data_join])
    adj = sp.csr_matrix((all_data, (all_rows, all_cols)), shape=(N_total, N_total))

    # 4. Node attributes
    # Pixel-node coords: take center of each pixel
    ys = np.arange(H)
    xs = np.arange(W)
    pixel_y_centers = affine.f + (ys + 0.5) * affine.e
    pixel_x_centers = affine.c + (xs + 0.5) * affine.a
    xx, yy = np.meshgrid(pixel_x_centers, pixel_y_centers)
    node_xy = np.zeros((N_total, 2), dtype=np.float32)
    node_xy[:N_pix, 0] = xx.ravel()
    node_xy[:N_pix, 1] = yy.ravel()
    if R:
        node_xy[N_pix:] = np.asarray(road_node_xy, dtype=np.float32)

    node_type = np.zeros(N_total, dtype=np.uint8)
    node_type[:N_pix] = NODE_PIXEL
    node_type[N_pix:] = NODE_ROAD

    node_friction = np.full(N_total, np.nan, dtype=np.float32)
    node_friction[:N_pix] = friction.ravel().astype(np.float32)
    # Road nodes get the walking-on-road friction as a reference value
    if R:
        node_friction[N_pix:] = 60.0 / (walking_kmh_on_road * 1000.0)

    # 5. Facility seeds
    facility_node_ids: list[int] = []
    if facility_geoms is not None:
        for geom in facility_geoms:
            c = geom.centroid
            row, col = _xy_to_rowcol(c.x, c.y, affine)
            if 0 <= row < H and 0 <= col < W:
                node_idx = row * W + col
                facility_node_ids.append(node_idx)
                node_type[node_idx] = NODE_FACILITY

    a, b, c0, d, e, f = affine.a, affine.b, affine.c, affine.d, affine.e, affine.f
    return TirthaGraph(
        adj=adj,
        node_xy=node_xy,
        node_type=node_type,
        node_friction=node_friction,
        crs=crs,
        affine=(a, b, c0, d, e, f),
        raster_shape=(H, W),
        pixel_size_m=float(pixel_size_m),
        region=region,
        facility_node_ids=np.asarray(facility_node_ids, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_graph(g: TirthaGraph, path: str | Path) -> None:
    """Save a TirthaGraph to a single ``.npz`` archive.

    The output bundles:
      - ``adj`` (sparse CSR): adjacency matrix, flattened internally
      - ``node_xy``, ``node_type``, ``node_friction``: per-node attributes
      - ``facility_node_ids``: destination-seed indices
      - ``meta.json`` (string): region, CRS, affine, pixel size, shape
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "region": g.region,
        "crs": g.crs,
        "affine": list(g.affine),
        "raster_shape": list(g.raster_shape),
        "pixel_size_m": g.pixel_size_m,
        "schema_version": 1,
    }
    np.savez_compressed(
        path,
        adj_data=g.adj.data,
        adj_indices=g.adj.indices,
        adj_indptr=g.adj.indptr,
        adj_shape=np.array(g.adj.shape, dtype=np.int64),
        node_xy=g.node_xy,
        node_type=g.node_type,
        node_friction=g.node_friction,
        facility_node_ids=g.facility_node_ids,
        meta_json=np.array(json.dumps(meta), dtype=object),
    )


def load_graph(path: str | Path) -> TirthaGraph:
    """Load a TirthaGraph saved by ``save_graph``."""
    path = Path(path)
    z = np.load(path, allow_pickle=True)
    meta = json.loads(str(z["meta_json"]))
    adj = sp.csr_matrix(
        (z["adj_data"], z["adj_indices"], z["adj_indptr"]),
        shape=tuple(z["adj_shape"].tolist()),
    )
    return TirthaGraph(
        adj=adj,
        node_xy=z["node_xy"],
        node_type=z["node_type"],
        node_friction=z["node_friction"],
        crs=meta["crs"],
        affine=tuple(meta["affine"]),
        raster_shape=tuple(meta["raster_shape"]),
        pixel_size_m=float(meta["pixel_size_m"]),
        region=meta["region"],
        facility_node_ids=z["facility_node_ids"],
    )


# ---------------------------------------------------------------------------
# NetworkX export (optional convenience)
# ---------------------------------------------------------------------------


def to_networkx(g: TirthaGraph):
    """Export to a ``networkx.DiGraph``. Useful for centrality / community
    analyses; not recommended for >1M-node graphs (slow + memory-heavy).
    """
    import networkx as nx

    G = nx.DiGraph()
    for i in range(g.n_nodes):
        G.add_node(
            int(i),
            x=float(g.node_xy[i, 0]),
            y=float(g.node_xy[i, 1]),
            type=int(g.node_type[i]),
            friction=float(g.node_friction[i]) if np.isfinite(g.node_friction[i]) else None,
        )
    coo = g.adj.tocoo()
    for r, c, w in zip(coo.row, coo.col, coo.data):
        G.add_edge(int(r), int(c), weight=float(w))
    return G
