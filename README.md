# tirtha

> Open, reproducible travel-time-to-healthcare mapping — pairing IBM/ESA's **TerraMind** foundation model with classical road-graph routing to estimate physical access to health facilities, benchmarked against the Malaria Atlas Project's 2020 raster.

**The name** — *tirtha* (तीर्थ) is Sanskrit for "crossing place" — a ford in a river where you can safely cross, also a place of pilgrimage where people travel for healing. This project maps every person's distance from the nearest tirtha.

**Status:** 🚧 v0 toy proof-of-concept working end-to-end on a 2.5 km × 2.5 km chip in Blantyre, Malawi. Country-scale v1 is the next milestone. See [`docs/methodology.md`](docs/methodology.md) for technical design, [`docs/plain_english.md`](docs/plain_english.md) for the project explained without jargon, and the [archive branch](https://github.com/msradam/geospatial-routing-api/tree/archive/django-api) for the 2019 implementation this transforms.

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

Tirtha additionally provides **per-pixel uncertainty bounds** (figure 14, B=200 bootstrap × K=40 friction ensemble). Wu 2025 and MAP 2020 have none.

**Calibration caveat (honest)** — figure 18 documents that tirtha's current CIs are *severely under-calibrated* against MAP 2020 as a proxy reference: ECE = 0.485, empirical 95% coverage = 3%. The bootstrap-over-196-patches methodology produces over-confident intervals. Path to calibrated UQ: TerraMind fine-tune with DHS supervision (adds epistemic variation) + deep ensembles or conformal calibration against held-out DHS clusters. This is the principled post-hoc fix. Until then: tirtha provides *uncertainty bounds*, not *calibrated uncertainty bounds*. The distinction matters for the methodology paper.

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

See [`docs/figures/`](docs/figures/) for all 18 headline visualizations — including figure 17 (Tirtha vs Wu vs MAP four-way head-to-head) and figure 18 (calibration limitation, honestly documented).

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
