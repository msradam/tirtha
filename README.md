# tirtha

[![tests](https://github.com/msradam/geospatial-routing-api/actions/workflows/test.yml/badge.svg)](https://github.com/msradam/geospatial-routing-api/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

> Open, reproducible travel-time-to-healthcare mapping — pairing IBM/ESA's **TerraMind** foundation model with classical road-graph routing to estimate physical access to health facilities, benchmarked against the Malaria Atlas Project's 2020 raster.

**The name** — *tirtha* (तीर्थ) is Sanskrit for "crossing place" — a ford in a river where you can safely cross, also a place of pilgrimage where people travel for healing. This project maps every person's distance from the nearest tirtha.

**Status:** 🚧 v0.1 — pipeline working end-to-end, Typer CLI, demonstrated on Blantyre / Cox's Bazar / Sierra Leone (national-scale) / Brownsville Brooklyn. See [`docs/methodology.md`](docs/methodology.md) for technical design, [`docs/plain_english.md`](docs/plain_english.md) for the project explained without jargon, and the [archive branch](https://github.com/msradam/geospatial-routing-api/tree/archive/django-api) for the 2019 implementation this transforms.

## Quickstart

```bash
git clone https://github.com/msradam/geospatial-routing-api.git tirtha
cd tirtha
uv sync                       # installs deps; ~3 GB Python ML stack on first run

# Run on a named region (anything OSM/Nominatim has as a polygon):
uv run tirtha accessibility run --region "Sierra Leone" --preset schools --resolution 100 --out ./sl

# Or pass an explicit bbox — useful for neighborhoods / informal settlements
# that Nominatim doesn't have as a polygon. Kew Gardens, Queens (the author's
# home neighborhood) is the canonical demo case:
uv run tirtha accessibility run \
    --bbox "-73.835,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --resolution 10 \
    --out ./kew-health

# Same pipeline, schools instead of healthcare — one argument:
uv run tirtha accessibility run \
    --bbox "-73.835,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --preset schools \
    --out ./kew-schools
```

Outputs (in `--out`):

- `travel_time.tif` — walking-time-to-nearest-destination raster (minutes)
- `friction.tif` — input friction surface (min/m)
- `facilities.geojson` — OSM destinations actually used
- `metrics.json` — population-weighted accessibility numbers
- `summary.txt` — human-readable summary
- `figures/headline.png` — four-panel headline figure

### The graph artifact

The "image is a graph" thesis exposed as a real loadable object. Build a unified
pixel + OSM-road graph for a region and run any graph algorithm on it:

```bash
uv run tirtha graph build \
    --bbox "-73.835,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --resolution 30 \
    --out kew.graph.npz

uv run tirtha graph inspect kew.graph.npz
# TirthaGraph[Kew Gardens, Queens] · 95×72px @ 30m
#   10,202 nodes (6,840 pixel + 3,362 road) · 70,965 edges
#   62 facility seeds · EPSG:32618
```

Load it in your own Python:

```python
from tirtha.graph import load_graph
import scipy.sparse.csgraph as csg

g = load_graph("kew.graph.npz")
# g.adj is a scipy.sparse.csr_matrix; g.node_xy, g.node_type, g.facility_node_ids
distances_from_facilities = csg.dijkstra(g.adj, indices=g.facility_node_ids)
# or convert to NetworkX, igraph, graph-tool, ... for centrality / community / etc.
```

### CLI surface

```
tirtha
├── version              # tirtha version
├── cache-info           # show cache contents + total size
├── accessibility
│   └── run              # the pipeline → travel-time raster + metrics + figure
└── graph
    ├── build            # build the unified pixel + road graph for a region
    └── inspect          # one-line summary of a saved graph artifact
```

A short terminal recording of the demo is in [`demo/`](demo/) — see `demo/README.md` to reproduce with [vhs](https://github.com/charmbracelet/vhs).

### Benchmarking vs MAP 2020

Validation isn't a CLI primitive — it's a research operation. There's a marimo
notebook at [`notebooks/02_bench_vs_map.py`](notebooks/02_bench_vs_map.py) that
takes any directory produced by `tirtha accessibility run`, downloads + clips
the MAP 2020 walking-only raster, and reports head-to-head Spearman ρ, MAE,
and Weiss-bin accessibility numbers — plus a three-panel comparison figure.

```bash
uv run tirtha accessibility run --region "Blantyre, Malawi" --out ./blantyre
uv run marimo edit notebooks/02_bench_vs_map.py    # edit TIRTHA_OUT_DIR, re-run
```

The CLI makes accessibility maps; this notebook validates them against the
published reference. Different jobs, different shapes.

### Tests

```bash
uv sync --extra dev      # installs pytest, ruff
uv run pytest            # 29 tests; <2s
```

Covers the Tobler hiking function math, hybrid friction overrides, MCP routing
on synthetic rasters, accessibility metrics, raster-comparison math, and the
graph build/save/load round-trip. No network, no GPU, no foundation-model
inference — pure unit tests.

## Headline result (v0 toy, Blantyre chip) — three-way head-to-head

Population-weighted accessibility (WorldPop UN-adjusted, walking-only, Blantyre 2.58km chip):

| Walking time | **Wu 2025** (Nat Comms, rule-based) | Tirtha v2 (Tobler+roads) | **Tirtha-FM** (TerraMind blend) | MAP 2020 (Weiss) |
|---|---|---|---|---|
| ≤ 5 min | 22.2% | 22.9% | **27.8%** | 22.5% |
| ≤ 10 min | 58.3% | 60.3% | **68.4%** | 67.1% |
| ≤ 15 min | 85.2% | 89.5% | **94.3%** | 98.4% |
| ≤ 30 min | 100% | 100% | 100% | 100% |

At the 10-min bin, **Tirtha-FM agrees with MAP within 1.3 pp; Wu 2025's rule-based method is off by 8.8 pp**. The TerraMind multimodal embedding identifies walkable infrastructure (paths through tree-cover patches, paved surfaces under canopy, informal walkways) that Wu's WorldCover lookup categorizes as slow. **41,018 of 66,564 pixels (62%) disagree by ≥1 min between Tirtha-FM and Wu.**

Spearman ρ matrix (all three methods agree internally at ρ > 0.98; all differ from MAP at ρ ≈ 0.66 driven by MAP's 925m resolution vs our 10m):

|  | Wu | T-v2 | T-FM | MAP |
|---|---|---|---|---|
| Wu | 1.000 | 0.992 | 0.981 | 0.678 |
| T-v2 | | 1.000 | 0.991 | 0.674 |
| T-FM | | | 1.000 | **0.662** |
| MAP | | | | 1.000 |

Tirtha additionally provides **calibrated per-pixel uncertainty bounds** (figures 14, 19). Wu 2025 and MAP 2020 have none.

- The naive ensemble (B=200 bootstrap × K=40 friction samples) is severely over-confident — ECE 0.484 against MAP 2020, empirical 95% coverage = 3.2% (figure 18, honestly documented).
- **Split-conformal quantile regression** (figure 19) brings empirical 95% coverage to **94.9%** — within 0.1 pp of nominal. ECE drops 177× to 0.003. The honest 95% CI half-width is **±6 min**, not the wildly over-confident ±0.1 min of the naive ensemble. Conformal calibration is against MAP 2020 as proxy reference; DHS supervision in v1 will recalibrate against human-reported travel times.

TerraMind multimodal ablation (zero-shot road-presence linear probe, 5-fold CV ROC-AUC):

| Modalities | ROC-AUC |
|---|---|
| S2 optical only | 0.712 ± 0.089 |
| S2 + S1 radar | 0.707 ± 0.080 |
| **S2 + S1 + DEM** | **0.748 ± 0.087** |
| TiM · S2 + S1 + DEM | 0.705 ± 0.165 |

DEM adds 5 pts over optical-only — this is the multimodal value of TerraMind that generic ViTs don't have.

### Methodological extensions also working at toy scale

**Fusion graph (figure 13)**: Built the proper on/off-road fusion as a scipy sparse adjacency — pixel grid (Tobler-weighted) + OSMnx walk graph (per-edge length × walking speed), joined at road-entry pixels. 67,112 nodes, 531,837 edges, Dijkstra in 0.0s. At Blantyre's dense 10m road resolution it agrees with raster-only fusion at Spearman 0.98 (MAE 1.19 min) — confirming that for dense urban grids, raster-only is already a valid fusion. The graph-based fusion's value shows up at country scale and for sparse rural roads.

**Uncertainty quantification (figure 14)** — *the open lane no other healthcare-accessibility work currently provides*: B=200 bootstrap probes over the TerraMind S2+S1+DEM embeddings → P(road) ± σ per patch → K=40 perturbed friction surfaces → ensemble MCP → per-pixel mean, std, and 95% CI on travel time. Population-weighted mean 95% CI width: 0.22 min. MAP 2020 has no uncertainty layer; AccessMod has no uncertainty layer; tirtha does.

See [`docs/figures/`](docs/figures/) for all 22 headline visualizations — including figure 17 (Tirtha vs Wu vs MAP four-way head-to-head), figure 19 (split-conformal CQR brings empirical 95% coverage to 94.9%), figure 20 (Cox's Bazar transfer demonstration), figure 21 (Sierra Leone national-scale), and figure 22 (Brownsville, Brooklyn urban application).

### Urban application — Brownsville, Brooklyn (figure 22)

Same pipeline pointed at a dense NYC neighborhood. 3.4 × 4.4 km at 10m resolution. 17 healthcare facilities (5 pharmacies, 5 clinics, 3 doctors, 2 hospitals), 47 schools, 26,202 buildings, 70 subway features. MCP solves in 0.1 seconds.

| Walking time | % built area · healthcare | % built area · schools |
|---|---|---|
| ≤ 5 min | 34.7% | 79.4% |
| ≤ 10 min | 71.6% | 99.6% |
| ≤ 15 min | 90.1% | 100% |
| ≤ 30 min | 100% | 100% |

**Schools are ~2× as accessible as healthcare in Brownsville** (mean 4.6 min vs 8.5 min). NYC has aggressively-distributed school infrastructure; healthcare consolidated into fewer larger facilities, producing 25-minute walking maxima in central Brooklyn for actual clinic access.

Honest methodology note: walking-only is artificially pessimistic for NYC (the L, 3, and C trains serve this area). But the *spatial pattern* matches what's documented — Brownsville's healthcare disparities aren't primarily distance-based; they're quality of care, insurance, continuity, and trust. Tirtha shows the structural baseline.

### National-scale — Sierra Leone (figure 21)

First end-to-end run beyond a toy chip: all of Sierra Leone, ~13M pixels at 100m resolution, 571 OSM-tagged healthcare facilities, 6.77M people via WorldPop UN-adjusted 2020. Multi-source MCP from all facility seeds in **4 seconds**. Compared against MAP 2020 over the same extent:

| Threshold | Tirtha-NAT | MAP 2020 |
|---|---|---|
| ≤ 15 min | 32.5% | 54.9% |
| ≤ 30 min | 41.5% | 69.7% |
| ≤ 60 min | 50.1% | 90.0% |
| ≤ 120 min | 63.1% | 98.7% |
| ≤ 180 min | 74.4% | 99.8% |

**Headline: Tirtha-NAT estimates that 25.6% of Sierra Leone's population — 1.71 million people — is more than 3 hours walking from any healthcare facility. MAP 2020 estimates 0.2%.** The discrepancy concentrates in the mountainous east and rural inland districts.

Honest caveats (both directions): 571 OSM facilities likely under-counts what MAP used (Sierra Leone MoHS lists ~1,200 facilities) → some Tirtha "unreachable" areas may have unmapped clinics. Conversely, MAP's 925m resolution smooths over real isolation in narrow valleys. The truth is between the two estimates — but Tirtha's number is the kind of result that would prompt a Ministry of Health investigation.

### Transfer demonstration — Cox's Bazar refugee camp (figure 20)

The Wu 2025 deep-read identified "transfer to a region where rule-based lookup tables fail" as a required demonstration. We ran the same head-to-head at Kutupalong, Cox's Bazar, Bangladesh (Rohingya refugee camp area, 4.7×4.5 km chip):

| Method | Mean walking time | Max | Issue |
|---|---|---|---|
| Tirtha v2 | **22.5 min** | 61.7 min | uses live OSM facilities |
| Wu 2025 rule-based | 26.3 min | **294.1 min** | WorldCover misclassification → tail outliers |
| MAP 2020 (Weiss) | **152.1 min** | 192.8 min | **stale facility database — misses camp clinics entirely** |

**Three findings**:

1. **MAP 2020 reports the entire camp as 2+ hours from healthcare** because its static 2020-era facility database does not include the 17 health-related amenities currently tagged in OSM inside the camp. Both Tirtha and Wu — using live OSM data — report ~25 min. **This is the canonical argument for a live, fork-and-run accessibility tool over a published static raster.**

2. **Wu's rule-based method has wild tail outliers** (max 294 min) because ESA WorldCover doesn't have a refugee-camp / informal-settlement class. Camp pixels get assigned to tree/grass/cropland (3-5 km/h) when reality is dense human walking infrastructure. Tirtha v2's slope-only Tobler is more conservative and avoids the brittleness.

3. **Wu and Tirtha still agree at Spearman ρ = 0.992** (same as Blantyre) — methodology changes within rule-based + Tobler + roads don't move rank-ordering much; they move absolute travel times.

---

## What this is

A reproducible pipeline that:

1. Pulls health facilities for a target country from **[healthsites.io](https://healthsites.io)** (OSM-linked, openly licensed).
2. Pulls Sentinel-1/2 + DEM tiles via STAC for the region of interest.
3. Runs **[TerraMind](https://huggingface.co/ibm-esa-geospatial)** (IBM/ESA, Apache 2.0) to estimate per-pixel off-road traversability — the part of the problem where classical lookup tables (land cover × slope) are weakest.
4. Fuses the resulting friction raster with an **OSMnx** road graph at road-entry points, so on-road travel uses real routing and off-road travel uses learned friction.
5. Runs minimum-cost paths from every populated pixel to the nearest facility (`skimage.graph.MCP_Geometric`, with optional anisotropic Tobler correction).
6. Outputs a kepler.gl-ready GeoJSON travel-time map.
7. Reports MAE against the [Malaria Atlas Project 2020](https://malariaatlas.org/project-resources/accessibility-to-healthcare/) raster and against [DHS](https://dhsprogram.com) self-reported travel times (`v483a` / `HEALTHFACTIM`).

Everything is open data and open weights. No paid APIs. Runs on a laptop.

## Why this exists

I built the 2019 version of this as a UNICEF Magicbox engineering intern: a Django service that ingested OSM road networks via OSMnx, built road graphs in iGraph, and computed routed distances between populated points and health facilities. The story is in three parts on [adamr.io](https://adamr.io):

- 🛤️ *The Roads Yet Taken* — Part I
- 🌍 *Go the Distance* — Part II
- ✨ *All the Difference* — Part III

In the seven years since, the open-source ecosystem has filled in the pieces I didn't have: foundation models for Earth observation (TerraMind), a peer-reviewed benchmark (Weiss et al. 2020, *Nature Medicine*), live OSM-linked facility data (healthsites.io v3 API), and harmonized self-reported ground truth (DHS). This repo is what happens when you point all of that at the original problem.

A "Part IV" methodology writeup is in [docs/methodology.md](docs/methodology.md).

## The artifact

When complete, this repo ships:

- **One marimo notebook** — end-to-end pipeline for one country/region, runnable in Colab.
- **One map** — kepler.gl viz with three toggleable layers (MAP baseline, this pipeline, difference).
- **One number** — MAE vs MAP raster and MAE vs DHS reported times.
- **One CLI** — `uv run tirtha run --country MWI --admin1 "Southern Region"`.

## Quickstart

*Coming soon — pipeline under construction.*

## Repo structure

```
tirtha/
├── data/       # healthsites.io, STAC, DHS loaders
├── model/      # TerraMind wrapper, fine-tune head
├── routing/    # OSMnx road graph (ported from 2019)
├── fusion/     # off-road raster ↔ on-road graph stitching
└── eval/       # MAP raster + DHS benchmarks
notebooks/      # marimo .py notebooks
docs/           # methodology + results writeups
```

## The 2019 archive

The original Django/REST implementation lives on the [`archive/django-api`](https://github.com/msradam/geospatial-routing-api/tree/archive/django-api) branch, tagged [`v1-unicef-2019-archive`](https://github.com/msradam/geospatial-routing-api/releases/tag/v1-unicef-2019-archive). The 2026 work transforms its data-science pipeline (the part that actually mattered) and retires the REST API scaffolding (which was a job-search artifact).

Here's what it produced in 2019 — schools color-coded by distance to nearest health facility:

![2019 kepler.gl output](kepler_screenshot.png)

## License

TBD — leaning Apache 2.0 to match TerraMind.
