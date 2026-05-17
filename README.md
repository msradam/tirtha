# tirtha

[![tests](https://github.com/msradam/tirtha/actions/workflows/test.yml/badge.svg)](https://github.com/msradam/tirtha/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

Open humanitarian accessibility mapping. Walking-time-to-nearest-essential-service for any populated region of the world, using IBM/ESA's TerraMind foundation model for friction estimation and OSMnx for road-graph routing. Healthcare is the flagship demo; the pipeline is application-general.

*tirtha* (तीर्थ) is Sanskrit for crossing place, a ford in a river where you can safely cross, also a place of pilgrimage where people travel for healing. This project maps every person's distance from the nearest tirtha.

## Status

v0.1.0. Pipeline works end-to-end. Validated on Blantyre (Malawi), Cox's Bazar (Bangladesh), Sierra Leone (national, 13M pixels at 100m), and Kew Gardens / Brownsville (NYC). 29 unit tests pass in under 2 seconds. CI green. Not yet on PyPI; see the audit in `docs/` for the shipping plan.

Methodology details: [`docs/methodology.md`](docs/methodology.md).
Project explained without jargon: [`docs/plain_english.md`](docs/plain_english.md).
2019 origin code preserved on branch [`archive/django-api`](https://github.com/msradam/tirtha/tree/archive/django-api).

## Quickstart

```bash
git clone https://github.com/msradam/tirtha.git
cd tirtha
uv sync                                # core deps
uv sync --extra ml                     # add torch + terratorch for --friction fm
uv sync --extra dev                    # add pytest + ruff

# Named region (anything Nominatim has as a polygon):
uv run tirtha accessibility run --region "Sierra Leone" --preset schools --resolution 100 --out ./sl

# Explicit bbox (for neighborhoods Nominatim treats as a point, informal settlements, custom AOIs):
uv run tirtha accessibility run \
    --bbox "-73.835,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --resolution 10 \
    --out ./kew-health

# Same pipeline, different humanitarian application:
uv run tirtha accessibility run \
    --bbox "-73.835,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --preset schools \
    --out ./kew-schools

# TerraMind-blended friction (downloads ~80 MB on first run):
uv run tirtha accessibility run \
    --bbox "-73.840,40.700,-73.810,40.725" \
    --region "Kew Gardens, Queens" \
    --resolution 10 \
    --friction fm \
    --out ./kew-fm
```

Outputs in `--out`:

- `travel_time.tif`: walking-time-to-nearest-destination raster in minutes
- `friction.tif`: input friction surface in min/m
- `facilities.geojson`: OSM destinations used
- `metrics.json`: population-weighted accessibility numbers
- `summary.txt`: human-readable summary
- `figures/headline.png`: four-panel summary figure

## CLI surface

```
tirtha
├── version              tirtha version
├── cache-info           show cache contents and total size
├── accessibility
│   └── run              the pipeline. travel-time raster + metrics + figure
└── graph
    ├── build            build the unified pixel + road graph for a region
    └── inspect          one-line summary of a saved graph artifact
```

## The graph artifact

The "image is a graph" thesis exposed as a loadable object. Build a unified pixel-plus-OSM-road graph for a region and run any graph algorithm on it:

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
# g.adj is scipy.sparse.csr_matrix
# g.node_xy, g.node_type, g.facility_node_ids are numpy arrays
distances_from_facilities = csg.dijkstra(g.adj, indices=g.facility_node_ids)
```

Or convert to NetworkX, igraph, graph-tool for centrality or community analysis.

## Validation results

Per-pixel comparison against the Weiss et al. 2020 walking-only Malaria Atlas Project raster.

### Four-way head-to-head (Blantyre 2.58 km chip)

| Walking time | Wu 2025 rule-based | Tirtha v2 (Tobler+roads) | Tirtha-FM (TerraMind blend) | MAP 2020 (Weiss) |
|---|---|---|---|---|
| ≤ 5 min | 22.2% | 22.9% | **27.8%** | 22.5% |
| ≤ 10 min | 58.3% | 60.3% | **68.4%** | 67.1% |
| ≤ 15 min | 85.2% | 89.5% | **94.3%** | 98.4% |
| ≤ 30 min | 100% | 100% | 100% | 100% |

At the 10-min walking threshold, Tirtha-FM matches MAP within 1.3 percentage points. Wu 2025's rule-based method is off by 8.8. The TerraMind multimodal embedding identifies walkable infrastructure (paths through tree-cover patches, paved surfaces under canopy, informal walkways) that Wu's WorldCover lookup categorizes as slow. 41,018 of 66,564 pixels (62%) disagree by at least 1 minute between Tirtha-FM and Wu.

Spearman ρ matrix. All three methods agree internally at ρ > 0.98. All differ from MAP at ρ ≈ 0.66, driven by MAP's 925m resolution versus our 10m.

|  | Wu | T-v2 | T-FM | MAP |
|---|---|---|---|---|
| Wu | 1.000 | 0.992 | 0.981 | 0.678 |
| T-v2 | | 1.000 | 0.991 | 0.674 |
| T-FM | | | 1.000 | 0.662 |
| MAP | | | | 1.000 |

### Calibrated per-pixel uncertainty

Wu 2025 and MAP 2020 have no uncertainty layer. Tirtha does, and split-conformal quantile regression makes the intervals honest.

| Nominal coverage | Naive ensemble | Split-conformal CQR |
|---|---|---|
| 50% | 1.6% | 49.7% |
| 75% | 2.3% | 74.4% |
| 95% | 3.2% | **94.9%** |

Expected Calibration Error: 0.484 → 0.003 (177x improvement). The honest 95% CI half-width is ±6 min on the Blantyre chip.

### TerraMind multimodal ablation

Zero-shot road-presence linear probe, 5-fold CV ROC-AUC.

| Modalities | ROC-AUC |
|---|---|
| S2 optical only | 0.712 ± 0.089 |
| S2 + S1 radar | 0.707 ± 0.080 |
| **S2 + S1 + DEM** | **0.748 ± 0.087** |
| TiM · S2 + S1 + DEM | 0.705 ± 0.165 |

DEM adds 5 points over optical-only. This is the multimodal value of TerraMind that generic ViTs don't have.

### National-scale Sierra Leone

13M pixels at 100m, 6.77M people via WorldPop UN-adjusted 2020, 571 OSM-tagged healthcare facilities. Multi-source MCP from all facility seeds in 4 seconds wall clock.

| Threshold | Tirtha-NAT | MAP 2020 |
|---|---|---|
| ≤ 15 min | 32.5% | 54.9% |
| ≤ 30 min | 41.5% | 69.7% |
| ≤ 60 min | 50.1% | 90.0% |
| ≤ 120 min | 63.1% | 98.7% |
| ≤ 180 min | 74.4% | 99.8% |

Tirtha-NAT estimates 25.6% of Sierra Leone's population (1.71 million people) is more than 3 hours walking from any healthcare facility. MAP 2020 estimates 0.2%. The discrepancy concentrates in the mountainous east and rural inland districts.

Caveats. 571 OSM facilities likely undercounts what MAP used; Sierra Leone Ministry of Health and Sanitation lists about 1,200 facilities, so some Tirtha "unreachable" areas may have unmapped clinics. Conversely, MAP's 925m resolution smooths over real isolation in narrow valleys. The truth is between the two estimates.

### Cox's Bazar refugee camp transfer

The closest competitor (Wu et al. 2025) has wild rule-based outliers where ESA WorldCover misclassifies camp infrastructure. MAP's static 2020 facility database missed the camp's internal clinics entirely.

| Method | Mean walking time | Max | Issue |
|---|---|---|---|
| Tirtha v2 | 22.5 min | 61.7 min | uses live OSM facilities |
| Wu 2025 rule-based | 26.3 min | 294.1 min | WorldCover misclassification, tail outliers |
| MAP 2020 (Weiss) | 152.1 min | 192.8 min | stale facility database, misses camp clinics |

This is the argument for a live, fork-and-run pipeline over a published static raster. See `docs/figures/20_coxs_bazar_headtohead.png` for the full breakdown.

### NYC urban application (Brownsville)

| Walking time | % built area · healthcare | % built area · schools |
|---|---|---|
| ≤ 5 min | 34.7% | 79.4% |
| ≤ 10 min | 71.6% | 99.6% |
| ≤ 15 min | 90.1% | 100% |
| ≤ 30 min | 100% | 100% |

Schools are about 2x as accessible as healthcare in Brownsville (mean 4.6 min vs 8.5 min). NYC has aggressively-distributed school infrastructure; healthcare consolidated into fewer larger facilities, producing 25-minute walking maxima in central Brooklyn for actual clinic access.

Walking-only is artificially pessimistic for NYC because the subway is real travel. The *spatial pattern* matches documented disparities. Brownsville's healthcare gaps are quality of care, insurance, continuity, and trust, not primarily distance. Tirtha shows the structural baseline.

## Benchmarking against MAP 2020

Validation is a research operation, not a CLI primitive. The marimo notebook at [`notebooks/02_bench_vs_map.py`](notebooks/02_bench_vs_map.py) takes any directory produced by `tirtha accessibility run`, downloads and clips the MAP 2020 walking-only raster, and reports head-to-head Spearman ρ, MAE, and Weiss-bin accessibility, plus a three-panel comparison figure.

```bash
uv run tirtha accessibility run --region "Blantyre, Malawi" --out ./blantyre
uv run marimo edit notebooks/02_bench_vs_map.py    # edit TIRTHA_OUT_DIR, re-run
```

## Tests

```bash
uv sync --extra dev
uv run pytest
# 29 tests, under 2 seconds, no network, no GPU, no foundation-model inference
```

Covers the Tobler hiking function math, hybrid friction overrides, MCP routing on synthetic rasters, accessibility metrics, raster-comparison math, and the graph build/save/load round-trip.

## Demo

A short terminal recording of the CLI in action is in [`demo/`](demo/). See `demo/README.md` to reproduce with [vhs](https://github.com/charmbracelet/vhs).

## Repo layout

```
src/tirtha/
├── __init__.py     public API; exposes run_accessibility
├── pipeline.py     end-to-end run_accessibility() orchestration
├── data.py         Planetary Computer STAC + OSMnx + WorldPop + MAP raster loaders
├── friction.py     Tobler, hybrid friction, FM-blended friction
├── route.py        multi-source MCP via scikit-image
├── metrics.py      pop-weighted accessibility, Spearman + MAE comparison
├── embed.py        TerraMind inference wrappers, in-chip probe (requires --extra ml)
├── graph.py        TirthaGraph + save/load, scipy.sparse adjacency
├── viz.py          4-panel headline figure
├── io.py           GeoTIFF / GeoJSON / JSON / TXT writers
└── cli.py          Typer CLI

tests/              29 unit tests
notebooks/          marimo notebooks (smoke test, MAP benchmark)
demo/               vhs tape for terminal recording
docs/               methodology, plain-english, figures
```

## Origin

The 2019 version of this was a Django service built during a UNICEF Magicbox engineering internship. OSMnx pulled road networks, iGraph computed routed distances, and the API answered queries. That implementation is preserved on the [`archive/django-api`](https://github.com/msradam/tirtha/tree/archive/django-api) branch at tag `v1-unicef-2019-archive`. The 2026 work modernizes the pipeline and retires the REST API scaffolding (which existed in 2019 mostly to demonstrate "hireability").

Three blog posts on [adamr.io](https://adamr.io) document the 2019 work: *The Roads Yet Taken*, *Go the Distance*, and *All the Difference*. A "Part IV" methodology writeup is `docs/methodology.md`.

## License

Apache 2.0. See `LICENSE`.
