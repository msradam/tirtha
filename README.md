# tirtha

[![tests](https://github.com/msradam/tirtha/actions/workflows/test.yml/badge.svg)](https://github.com/msradam/tirtha/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

Walking-time-to-nearest-anything maps for any region of the world. Uses IBM/ESA's TerraMind foundation model for off-road friction, OSMnx for the road graph, and multi-source Dijkstra for the routing. Built for humanitarian accessibility work; ships with a healthcare preset.

*tirtha* (तीर्थ): Sanskrit for "crossing place" or place of pilgrimage. The map is every person's distance from the nearest one.

## Install

```bash
git clone https://github.com/msradam/tirtha.git
cd tirtha
uv sync                # core
uv sync --extra ml     # add torch + terratorch for `--friction fm`
uv sync --extra dev    # add pytest + ruff
```

## Run

```bash
uv run tirtha accessibility run --region "Sierra Leone" --resolution 100 --out ./sl
```

That fetches Sentinel imagery + NASADEM + OSM, builds a friction surface, runs MCP from every healthcare facility, and writes `travel_time.tif`, `friction.tif`, `facilities.geojson`, `metrics.json`, `summary.txt`, and a four-panel figure. About 4 minutes wall clock on a MacBook for a country at 100m, 30 seconds for a 2 km chip at 10m.

`--preset schools|water|shelter` swaps the destination set. `--bbox W,S,E,N` overrides geocoding for regions Nominatim doesn't have as a polygon.

## CLI

```
tirtha
├── version
├── cache-info
├── accessibility
│   └── run                 → travel-time raster + metrics + figure
└── graph
    ├── build               → unified pixel + road graph (.npz)
    └── inspect             → one-line graph summary
```

`tirtha graph build` produces a `scipy.sparse.csr_matrix` of the unified pixel-plus-OSM-road graph plus per-node attributes. Load with `tirtha.graph.load_graph` and run any algorithm:

```python
from tirtha.graph import load_graph
import scipy.sparse.csgraph as csg
g = load_graph("sl.graph.npz")
dist = csg.dijkstra(g.adj, indices=g.facility_node_ids)
```

## What it produces

Per-pixel Spearman of 0.674 vs the Weiss et al. 2020 MAP raster on the Blantyre chip, MAE 2.89 min. After split-conformal calibration the 95% CI on travel time has empirical coverage 94.9% (ECE 0.003). At country scale, tirtha and MAP disagree by 1.71 million people on "more than 3 hours walking from healthcare in Sierra Leone." Full numbers and figures in [`docs/methodology.md`](docs/methodology.md).

## Showcase

Pre-computed results for [Sierra Leone, Blantyre, Cox's Bazar, and Brownsville](docs/cases/) live under `docs/cases/`. The [showcase notebook](notebooks/03_showcase.py) renders them as a static site:

```bash
uv run marimo export html-wasm notebooks/03_showcase.py -o site
```

CI deploys this to GitHub Pages on every push to master.

## Validation

```bash
uv run pytest          # 29 tests, under 2 seconds, no network or GPU
```

[`notebooks/02_bench_vs_map.py`](notebooks/02_bench_vs_map.py) takes any `tirtha accessibility run` output and produces a head-to-head against the published MAP 2020 raster (Spearman, MAE, Weiss-bin accessibility, three-panel figure).

## See also

- [`docs/methodology.md`](docs/methodology.md): design choices, the on/off-road fusion, calibration, validation numbers
- [`docs/plain_english.md`](docs/plain_english.md): the project explained without jargon
- [`CHANGELOG.md`](CHANGELOG.md): development arc from v0.1 to v0.1.0
- [`demo/`](demo/): vhs terminal recording, reproducible with `brew install vhs && vhs demo/tirtha.tape`
- [`archive/django-api`](https://github.com/msradam/tirtha/tree/archive/django-api): the 2019 UNICEF Magicbox intern code this transforms

## License

Apache 2.0.
