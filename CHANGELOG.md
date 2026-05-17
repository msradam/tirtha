# Changelog

All notable changes to tirtha are documented here. The repo originally lived
as a 2019 UNICEF Magicbox intern project (a Django REST API for distance-to-
healthcare computations). That implementation is preserved on the
[`archive/django-api`](https://github.com/msradam/tirtha/tree/archive/django-api)
branch at tag `v1-unicef-2019-archive` and is no longer part of the active
codebase.

The development version numbers (v0.1 through v0.6) track in-session
iterations during the May 16-17, 2026 build. The first PyPI-shaped release
is v0.1.0, which bundles the contents of all six iterations.

## v0.1.0 (2026-05-17): first PyPI release

Consolidates the development iterations v0.1 through v0.6 into a single
released artifact. What ships:

- Python package `tirtha` (Apache 2.0, requires Python 3.12+)
- CLI: `tirtha accessibility run`, `tirtha graph build`, `tirtha graph inspect`,
  `tirtha cache-info`, `tirtha version`
- Pipeline: STAC + OSMnx + WorldPop + MAP raster loaders, Tobler friction,
  hybrid friction with road overrides, FM-blended friction via TerraMind-Small
  (optional `[ml]` extra), multi-source MCP from facility seeds, calibrated
  uncertainty via split-conformal CQR
- Graph artifact: unified pixel + OSM-road sparse adjacency, saved as `.npz`,
  loadable in three lines for any graph algorithm
- 10-country showcase pre-computed at 100m resolution: Sierra Leone, Malawi,
  Burkina Faso, Liberia, Rwanda, Madagascar, Nepal, Haiti, Ethiopia,
  Bangladesh. Browsable via the marimo WASM site (deployed on GitHub Pages)
- 29-test pytest suite; GitHub Actions CI for tests and lint
- vhs demo tape, plain-English explainer, methodology doc, 22 committed figures

Validation numbers (Blantyre 2.58 km chip):

- Per-pixel agreement vs MAP 2020: Spearman rho 0.674, MAE 2.89 min
- Population-weighted accessibility within 10 min: tirtha-FM 68.4%, MAP 67.1%
- Calibration: empirical 95% coverage 94.9% after split-conformal CQR
- TerraMind ablation: S2+S1+DEM ROC-AUC 0.748, S2 alone 0.712

## Development iterations

The sub-headings below document the order in which v0.1.0's contents were
built. Each is commit-tagged in the git history.

### v0.6 (development): bench-vs-MAP marimo notebook

- `notebooks/02_bench_vs_map.py`: reactive marimo notebook for benchmarking
  any `tirtha accessibility run` output against the Weiss et al. 2020 MAP
  walking-only raster. Loads `metrics.json`, downloads MAP 2020 (~460 MB,
  cached), clips and reprojects, computes Spearman rho, MAE, and Weiss-bin
  accessibility head-to-head, and produces a three-panel figure.
- Deliberate decision: benchmarking is a research operation, not a CLI
  primitive. `tirtha bench compare` would have implied it was a primary
  use case. The notebook keeps the CLI focused and the validation forkable.

## v0.5 (2026-05-17): CI, lint, and tests as shipping signal

- `.github/workflows/test.yml`: GitHub Actions runs pytest and ruff on
  every push and PR. Caches `uv.lock`. No ML extras in CI to keep runs fast.
- README badges (tests, python version, license).
- Auto-fixed 35 ruff lint issues across `src/tirtha/`.
- `[tool.pytest.ini_options]` in `pyproject.toml` for stable test discovery.

## v0.4 (2026-05-17): 29-test pytest suite

- `tests/test_friction.py`: 10 tests covering Tobler's hiking function
  (flat, steep, optimum, NaN slopes), hybrid friction overrides, FM-blend
  convex combination math, and highway-rank mapping.
- `tests/test_metrics.py`: 9 tests on population-weighted accessibility,
  Weiss-bin defaults, raster-comparison math, JSON serializability.
- `tests/test_route.py`: 6 tests on multi-source MCP, monotonicity with
  distance, two-seed nearest-source, low-friction corridor speedup.
- `tests/test_graph.py`: 4 tests on graph build, facility-seed marking, and
  save/load round-trip.
- Total runtime: 1.18 s. No network, no GPU, no TerraMind.
- Bugfix to `tirtha.metrics.compare_rasters`: now returns the same keys
  regardless of valid-pixel count (was inconsistent between code paths).

## v0.3 (2026-05-17): TerraMind wired through the CLI

- `tirtha accessibility run --friction fm` now actually invokes the
  foundation model. Fetches Sentinel-2, Sentinel-1 RTC, and NASADEM via
  Planetary Computer, normalizes with TerraMind v1 pretraining stats,
  runs `terramind_v1_small` (~80 MB downloaded from HuggingFace on first
  run), trains an in-chip logistic-regression probe against the rasterized
  OSM road network, and blends the per-pixel P(road) with Tobler off-road
  friction via `tirtha.friction.fm_blended_friction`.
- New module: `src/tirtha/embed.py` with `MultimodalChip`, `fetch_multimodal_chip`,
  `load_terramind`, `run_terramind_inference`, `train_road_probe_in_chip`,
  `estimate_p_road_from_chip`.
- Helpful error message when the `[ml]` extra is not installed.
- 224x224 fixed input size enforced. Raises a clear error with `--bbox`
  and `--resolution` hints if the chip is too small.

## v0.2 (2026-05-17): graph artifact and Kew Gardens demo

- `src/tirtha/graph.py`: `TirthaGraph` dataclass plus `build_graph`,
  `save_graph`, `load_graph`, and `to_networkx`. The "image is both a
  raster and a graph" thesis exposed as a first-class loadable object.
  Bundles a unified scipy.sparse CSR adjacency of pixel and OSM-road
  nodes joined at coincident locations, plus per-node coordinates,
  types, friction, and a JSON metadata sidecar, all in a single `.npz`.
- CLI: `tirtha graph build` and `tirtha graph inspect`.
- `--bbox` escape hatch on both `accessibility run` and `graph build`.
  Nominatim does not have every neighborhood as a polygon. `--bbox`
  lets users target informal settlements, refugee camps, and custom
  AOIs directly.
- Demo switched from Brownsville to Kew Gardens, Queens (the author's
  home neighborhood, intuit-checkable, and a real test of the `--bbox`
  flow since Nominatim treats it as a point not a polygon).
- Better error message when geocoding returns a non-polygon (was an
  unhelpful TypeError).

## v0.1 (2026-05-17): real package, Typer CLI, vhs demo tape

- Renamed `friction` to `tirtha` everywhere. PyPI name and CLI entry-point.
- New package layout (flat, 8 modules under `src/tirtha/`):
  - `__init__.py`: public API
  - `pipeline.py`: `run_accessibility()` orchestration
  - `data.py`: Planetary Computer STAC, OSMnx, WorldPop, and MAP raster
    loaders, with the `raise_for_status` fix that prevents the 0-byte
    WorldPop bug that bit us on the NYC 5-borough run.
  - `friction.py`: Tobler, hybrid, FM-blended
  - `route.py`: multi-source MCP
  - `metrics.py`: accessibility, raster comparison, AccessibilityResult dataclass
  - `viz.py`: 4-panel headline figure
  - `io.py`: GeoTIFF, GeoJSON, JSON, TXT writers
  - `cli.py`: Typer CLI
- Replaced empty `src/friction/{data,eval,fusion,model,routing}/` stub
  directories with the real modules above.
- CLI subcommands: `tirtha version`, `tirtha cache-info`,
  `tirtha accessibility run`.
- Four destination presets: `health`, `schools`, `water`, `shelter`.
- Demo tape (`demo/tirtha.tape`) showing the CLI end-to-end on
  Brownsville. Reproducible via `brew install vhs && vhs demo/tirtha.tape`.

## Pre-v0.1: methodology validation (May 16-17, 2026)

These are the figures and findings that motivated the v0.1 refactor. See
the git log for the full commit messages.

- v4.3 (commit `3e96bc8`): Cox's Bazar transfer demo. MAP 2020 reports
  mean 152 min walking to nearest healthcare in Kutupalong refugee camp.
  Tirtha using live OSM data reports 25 min. MAP's facility database was
  frozen in 2020 and missed the 17 health amenities tagged inside the camp.
- v4.2 (commit `7b9adb8`): split-conformal calibration of the uncertainty
  bounds. Empirical 95% coverage 3% to 94.9%. ECE 0.485 to 0.003.
- v4.1 (commit `fdb8d94`): documentation of the naive uncertainty
  miscalibration before the conformal fix.
- v4 (commit `5e357ab`): four-way head-to-head between tirtha-rules,
  tirtha-FM, Wu et al. 2025 rule-based, and MAP 2020. At the 10-min
  walking threshold, tirtha-FM agrees with MAP within 1.3 percentage
  points; Wu's rule-based is off by 8.8.
- v5 (commit `1fdbf55`): national-scale Sierra Leone run. ~13M pixels at
  100m, 6.77M population. Tirtha estimates 25.6% of the population is
  more than 3 hours walking from healthcare (1.71M people); MAP 2020
  estimates 0.2%.
- v6 (commit `dc7d4b3`): Brownsville, Brooklyn urban application. Same
  pipeline. Schools are about 2x as accessible as healthcare in the
  documented health-disparities neighborhood.

## Archive

- `archive/django-api` branch and `v1-unicef-2019-archive` tag preserve
  the 2019 UNICEF Magicbox intern implementation (Django REST + OSMnx +
  iGraph). Read-only reference.
