# friction

> Open, reproducible travel-time-to-healthcare mapping — pairing IBM/ESA's **TerraMind** foundation model with classical road-graph routing to estimate physical access to health facilities, benchmarked against the Malaria Atlas Project's 2020 raster.

**Status:** 🚧 In active rebuild. See [methodology sketch](docs/methodology.md) for the design; see the [archive branch](https://github.com/msradam/geospatial-routing-api/tree/archive/django-api) for the 2019 implementation this work transforms.

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
- **One CLI** — `uv run friction run --country MWI --admin1 "Southern Region"`.

## Quickstart

*Coming soon — pipeline under construction.*

## Repo structure

```
friction/
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
