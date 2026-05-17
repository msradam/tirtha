# 🛤️ tirtha: TerraMind-supervised friction surfaces for humanitarian accessibility mapping

Submission to the [TerraMind Blue-Sky Challenge](https://huggingface.co/spaces/ibm-esa-geospatial/challenge).

Adam Munawar Rahman. IBM (personal project, not affiliated with IBM work). NYU Tandon MS CompEng.
Code: [github.com/msradam/tirtha](https://github.com/msradam/tirtha).
Contact: msrahmanadam@gmail.com.

## TL;DR

Tirtha uses TerraMind-Small as a frozen multimodal feature extractor (Sentinel-2 + Sentinel-1 RTC + NASADEM) to estimate per-pixel walking friction, blends it with classical OSM road-graph routing, runs multi-source shortest paths from healthcare facilities, and reports calibrated per-pixel travel-time bounds via split-conformal prediction. Validated against MAP 2020 (Weiss et al., *Nature Medicine*) at Spearman ρ = 0.674 with MAE 2.89 min in Blantyre, and at country scale on Sierra Leone (13M pixels, 100m). No fine-tune. TerraMind is used here as the friction-surface backbone for a graph algorithm, not as a downstream task head.

## Why this is beyond just another fine-tune

The TerraMind paper and existing PANGAEA-style demos use it as a feature backbone for classification or segmentation fine-tunes (LULC, water bodies, change detection). Tirtha uses TerraMind embeddings as the cost layer of a shortest-path graph. Specifically:

1. Fetch a 224x224 multimodal chip (12 S2L2A bands, 2 S1 RTC bands in dB, NASADEM, all v1-normalized).
2. Run `terramind_v1_small` to get (14, 14, 384) patch embeddings. Frozen weights, no fine-tune.
3. Train an in-chip logistic-regression probe against the rasterized OSM road network for supervision. Distillation from OSM rather than from labels.
4. Upsample patch P(road) to per-pixel, blend with Tobler's hiking function over slope: `friction = (1 - P) * Tobler + P * road_walk`.
5. Run multi-source Dijkstra on the friction raster from every OSM-tagged healthcare facility, producing a walking-time-to-nearest-care raster.
6. Calibrate the uncertainty: bootstrap the probe B=200x, ensemble K=40 friction surfaces, propagate through MCP, then apply split-conformal CQR using MAP 2020 as proxy reference.

The result is a per-pixel walking-time raster with calibrated confidence intervals, the first such artifact for healthcare accessibility that I am aware of.

## Headline results

Per-pixel agreement with the Weiss et al. 2020 MAP raster (Blantyre, Malawi, 2.58 km chip):

| Metric | Value |
|---|---|
| Spearman ρ | 0.674 |
| Pearson r | 0.667 |
| MAE | 2.89 min |
| Bias (tirtha minus MAP) | +0.44 min |

Four-way head-to-head at the policy-relevant 10-min walking threshold:

| Method | % of population within 10 min |
|---|---|
| Tirtha (TerraMind-blended) | 68.4% |
| MAP 2020 (Weiss) | 67.1% |
| Tirtha (rules-only baseline) | 60.3% |
| Wu et al. 2025 (Nat Comms, rule-based) | 58.3% |

Tirtha-FM matches MAP within 1.3 percentage points. Wu's rule-based method is off by 8.8. The TerraMind embedding identifies walkable infrastructure (paths through "tree cover" patches, paved surfaces under canopy, informal walkways) that ESA WorldCover lookup tables miss. 62% of pixels disagree by at least 1 minute between Tirtha-FM and Wu, overwhelmingly with Tirtha-FM faster.

Calibrated uncertainty (the unique deliverable):

| Nominal coverage | Naive ensemble | Split-conformal CQR |
|---|---|---|
| 50% | 1.6% | 49.7% |
| 75% | 2.3% | 74.4% |
| 95% | 3.2% | 94.9% |

Expected Calibration Error: 0.484 → 0.003 (177x improvement). The honest 95% CI half-width is plus or minus 6 min. MAP 2020 has no uncertainty layer. AccessMod has none. Wu et al. 2025 has none. Tirtha does.

National scale, Sierra Leone (4 minutes wall-clock on a MacBook):

| Walking time | Tirtha-NAT | MAP 2020 |
|---|---|---|
| ≤ 30 min | 41.5% | 69.7% |
| ≤ 60 min | 50.1% | 90.0% |
| ≤ 180 min | 74.4% | 99.8% |

Tirtha estimates 25.6% of Sierra Leone's population (1.71 million people) is more than 3 hours walking from any healthcare facility. MAP 2020 estimates 0.2%. The discrepancy concentrates in the mountainous east and rural inland districts. The truth is between the two; either estimate is the kind of finding that prompts a Ministry of Health investigation.

Transfer to a region where rule-based lookup categorically fails, Kutupalong Rohingya refugee camp, Bangladesh:

MAP 2020 reports mean 152 min walking to nearest healthcare across Kutupalong, max 193 min. Tirtha using current OSM data (17 health amenities tagged inside the camp) reports mean 25 min. MAP's static facility database, frozen in 2020, does not include the camp's internal clinics. ESA WorldCover does not have an "informal settlement" class, so Wu's rule-based method has wild outliers (max 294 min) where camp pixels are assigned "tree cover" speeds. This is the case for a foundation-model-aware, live, fork-and-run pipeline.

## What ships

The repo is a Python package and CLI. `pip install tirtha` lets anyone do this on a laptop:

```bash
tirtha accessibility run \
  --bbox "-13.45,7.50,-11.00,10.00" --region "Sierra Leone Southern" \
  --friction fm --resolution 100 --out ./out
```

That fetches the data (Planetary Computer, OSM, WorldPop), runs TerraMind inference, builds the friction surface, computes MCP from facility seeds, writes a GeoTIFF, GeoJSON, JSON metrics, and a headline figure. The pipeline runs end-to-end in about 30 seconds for a 2 km chip or 4 minutes for a country at 100 m, on Apple Silicon CPU. No GPU required.

There is also a graph artifact: `tirtha graph build` produces a unified pixel + OSM-road sparse adjacency (`scipy.sparse.csr_matrix`) saved as a `.npz`. Load it in three lines and run any graph algorithm (Dijkstra, betweenness, community detection) without rebuilding the geometry. The thesis "image is both a raster and a graph" exposed as a first-class loadable object.

29 unit tests, GitHub Actions CI, vhs demo tape, Apache-2.0 license, Python 3.12+, uv-managed.

## What I would value your read on

Three questions for the team:

1. Is using TerraMind as the cost layer of a shortest-path graph a Blue-Sky-style application, versus the segmentation or detection demos that have won previous rounds?
2. Does the calibrated-uncertainty contribution land? Split-conformal CQR against MAP 2020 as proxy reference, or is there a more defensible calibration target you would recommend?
3. The DHS supervision loop (calibrating against household-reported travel times from the DHS Program) is the natural next step but blocked on weeks of registration paperwork. Is there an IBM or ESA partner you would suggest who has already done that registration and might be open to a co-authored validation?

Figures referenced: figure 17 (four-way Wu head-to-head), figure 19 (conformal calibration), figure 20 (Cox's Bazar transfer), figure 21 (Sierra Leone national). All in the repo at `docs/figures/`. Methodology details in `docs/methodology.md`. Non-technical writeup in `docs/plain_english.md`.
