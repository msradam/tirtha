# Tirtha

[![tests](https://github.com/msradam/tirtha/actions/workflows/test.yml/badge.svg)](https://github.com/msradam/tirtha/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

## What this is

Tirtha builds a graph from satellite imagery, joins it with the OpenStreetMap road network, and computes how far every populated pixel is from the nearest essential service (clinic, school, water point, shelter). The output is an accessibility map plus a unified pixel-and-road graph artifact you can run any graph algorithm on.

Concretely:

1. Pull Sentinel-1 (radar), Sentinel-2 (optical), and NASADEM (elevation) tiles for the region of interest, plus the OSM road network and the OSM-tagged destination facilities.
2. Feed the satellite imagery to IBM/ESA's TerraMind foundation model to estimate per-pixel walkability (the "friction surface").
3. Treat the friction raster as a graph: each pixel is a node, adjacent pixels are connected, edge weights are walking time. Stitch the OSM road graph onto the same node set.
4. Run shortest-path (Dijkstra) from every destination facility outward. The resulting raster has a walking-time number per pixel.
5. Weight by population (WorldPop) and report standard accessibility metrics (percent of population within 30, 60, 120 minutes), plus calibrated per-pixel uncertainty bounds.

Built for humanitarian accessibility work. Ships with a healthcare preset because that is where the standard benchmark ([Weiss et al. 2020 MAP](https://malariaatlas.org/project-resources/accessibility-to-healthcare/)) and the standard supervision signal (DHS HEALTHFACTIM) exist. The pipeline itself does not know about healthcare; the destination set is a configuration choice.

## Install

```bash
git clone https://github.com/msradam/tirtha.git
cd tirtha
uv sync                # core
uv sync --extra ml     # add torch + terratorch for `--friction fm` (TerraMind)
uv sync --extra dev    # add pytest + ruff
```

## Run

```bash
uv run tirtha accessibility run --region "Sierra Leone" --resolution 100 --out ./sl
```

Writes to `./sl/`:

- `travel_time.tif`: walking-time raster in minutes
- `friction.tif`: input friction surface in min/m
- `facilities.geojson`: destinations actually used
- `metrics.json`: population-weighted accessibility numbers
- `summary.txt`: human-readable summary
- `figures/headline.png`: four-panel summary figure

About 4 minutes wall clock for a country at 100m, 30 seconds for a 2 km chip at 10m, on a MacBook.

`--preset schools|water|shelter` swaps the destination set. `--bbox W,S,E,N` overrides geocoding for places Nominatim does not have as a polygon.

## CLI

```
tirtha
├── version
├── cache-info
├── accessibility
│   └── run                 walking-time raster + metrics + figure
└── graph
    ├── build               unified pixel + road graph (.npz)
    └── inspect             one-line graph summary
```

## The graph artifact

`tirtha graph build` produces a `scipy.sparse.csr_matrix` of the unified pixel-plus-OSM-road graph plus per-node attributes (coordinates, type, friction). Load and run any algorithm:

```python
from tirtha.graph import load_graph
import scipy.sparse.csgraph as csg
g = load_graph("sl.graph.npz")
dist = csg.dijkstra(g.adj, indices=g.facility_node_ids)
```

## Validation

Per-pixel Spearman of 0.674 against the Weiss et al. 2020 MAP raster on the Blantyre chip, MAE 2.89 minutes. After split-conformal calibration the 95% CI on travel time has empirical coverage 94.9% (ECE 0.003). At country scale, Tirtha and MAP disagree by 1.71 million people on "more than 3 hours walking from healthcare in Sierra Leone." Full numbers, figures, and methodology in [`docs/methodology.md`](docs/methodology.md).

```bash
uv run pytest          # 29 tests, under 2 seconds, no network or GPU
```

[`notebooks/02_bench_vs_map.py`](notebooks/02_bench_vs_map.py) takes any `tirtha accessibility run` output and produces a head-to-head against the published MAP 2020 raster (Spearman, MAE, Weiss-bin accessibility, three-panel figure).

## Showcase

Pre-computed results for Sierra Leone (national), Blantyre, Cox's Bazar, and Brownsville live under [`docs/cases/`](docs/cases/). The [`notebooks/03_showcase.py`](notebooks/03_showcase.py) renders them as a static site:

```bash
uv run marimo export html-wasm notebooks/03_showcase.py -o site
```

CI deploys this to GitHub Pages on every push to master.

## See also

- [`docs/methodology.md`](docs/methodology.md): design choices, the on/off-road fusion, calibration, validation numbers
- [`docs/plain_english.md`](docs/plain_english.md): the project explained without jargon
- [`CHANGELOG.md`](CHANGELOG.md): development arc
- [`demo/`](demo/): vhs terminal recording, reproducible with `brew install vhs && vhs demo/tirtha.tape`
- [`archive/django-api`](https://github.com/msradam/tirtha/tree/archive/django-api): the 2019 UNICEF Magicbox intern code this transforms

## License

Apache 2.0.
