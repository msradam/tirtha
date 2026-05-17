# Methodology

> Working draft, design choices recorded here before code is written, so the implementation has something concrete to converge on.

## The problem

For each populated location in a target region, estimate the **travel time to the nearest health facility**, using only open data and open weights, in a form that's reproducible on a laptop.

This is a slight refinement of the classical problem from the [Malaria Atlas Project (MAP)](https://malariaatlas.org/project-resources/accessibility-to-healthcare/) and [WHO AccessMod](https://www.accessmod.org): both produce travel-time-to-care maps, but neither ships a fork-and-run pipeline that an analyst can point at a new country and re-run end-to-end with current data.

## The pipeline

```
                                                            ┌────────────────────────┐
                                                            │  healthsites.io  v3    │
                                                            │  facility coords       │
                                                            └──────────┬─────────────┘
                                                                       │
                                                                       ▼
   ┌────────────────────┐    ┌──────────────────────┐      ┌────────────────────────┐
   │ Sentinel-1 + S-2   │    │  TerraMind           │      │  MCP_Geometric         │
   │ DEM tiles via STAC ├───▶│  per-pixel embeddings├─────▶│  off-road least-cost   │
   └────────────────────┘    │  → friction raster   │      │  paths                 │
                             └──────────────────────┘      └───────────┬────────────┘
                                                                       │
   ┌────────────────────┐    ┌──────────────────────┐                  │
   │ OSM road network   │    │  OSMnx graph         │                  │
   │ for target country ├───▶│  on-road routing     ├──────────────────┤
   └────────────────────┘    │  (ported from 2019)  │                  │
                             └──────────────────────┘                  │
                                                                       ▼
                                                            ┌────────────────────────┐
                                                            │  Fusion at road-entry  │
                                                            │  points → travel-time  │
                                                            │  raster                │
                                                            └───────────┬────────────┘
                                                                        │
                          ┌─────────────────────────────────────────────┼────────────────────────┐
                          ▼                                             ▼                        ▼
              ┌────────────────────┐                       ┌────────────────────┐    ┌──────────────────┐
              │ kepler.gl GeoJSON  │                       │ MAE vs MAP 2020    │    │ MAE vs DHS v483a │
              │ visualization      │                       │ raster (Weiss '20) │    │ reported times   │
              └────────────────────┘                       └────────────────────┘    └──────────────────┘
```

## Design commitments

### 1. The TerraMind role is *off-road traversability*, not generic friction

The 2018/2020 MAP friction surfaces are hand-engineered: `(land cover class, slope) → speed`, via lookup tables. This works well where land cover classes are informative and poorly where they aren't, i.e., where the "off-road" landscape is heterogeneous (informal paths, dry riverbeds, footbridges, seasonal trails).

TerraMind's pretrained multimodal embeddings (Sentinel-1 SAR + Sentinel-2 optical + DEM) capture more signal than a categorical land-cover map. We use TerraMind specifically to **estimate off-road traversability**, not to replace the entire MAP friction surface.

On-road traversability is already a solved problem. OSM has road class, surface, and (often) speed metadata, and OSMnx exposes it as a graph. There's no value in re-learning what OSM already knows.

This split is the load-bearing methodological move. It's why the repo is built around **fusion** of a raster cost model with a vector road graph rather than around either alone.

### 2. Anisotropic (Tobler) cost, configurable

Walking up a slope ≠ walking down. AccessMod 3.0's signature contribution is treating slope-induced cost as directional: cells have eight directed edges to their neighbors, with per-direction speed from Tobler's hiking function.

MAP's 2020 raster bakes a single isotropic speed per pixel (averaging up/down). It's faster to compute and easier to publish as a raster, but it loses real information in mountainous regions.

The repo will support both modes via a flag:
- `--cost-mode isotropic`. MAP-style; faster; comparable directly to the MAP raster.
- `--cost-mode anisotropic`. AccessMod-style; honest in topography; this is the default once validated.

### 3. The on-road / off-road fusion

For each facility, compute travel time to a populated pixel as:

```
T(pixel → facility) = min(
    T_offroad(pixel → facility),                                 # MCP through friction raster
    T_offroad(pixel → nearest_road_entry) + T_onroad(entry → facility)  # walk to road, then route
)
```

The fusion point is the **road-entry**: any pixel adjacent to a road segment. The off-road MCP terminates either at facilities or at road-entry pixels (whichever is reached first). The on-road graph routes from road-entry to facility-nearest-road-entry.

This matches how AccessMod actually works internally; the difference is we're using TerraMind for the off-road raster instead of a hand-engineered cost surface.

### 4. Fine-tuning supervision: DHS, not synthetic

A zero-shot use of TerraMind (via its Thinking-in-Modalities trick to generate auxiliary LULC and feed a rule-based cost function) is the v0. The v1 is a supervised fine-tune.

Supervision source: **DHS `v483a` / IPUMS-DHS `HEALTHFACTIM`**, self-reported travel time to nearest health facility, paired with georeferenced cluster locations. ~150 surveys across 56 countries, 2000–2017.

We fine-tune a small regression head on top of frozen TerraMind embeddings: for each DHS cluster, the head predicts reported travel time. The friction raster is then derived by inversion (per-pixel cost such that summed-cost shortest paths reproduce the trained travel times). This is noisy supervision, self-reported times have well-known biases, but it's *real*, and it grounds the model in observed human experience rather than in a re-derivation of MAP's own rules.

### 5. Open, open, open

| Component | Source | License |
|---|---|---|
| Foundation model | IBM/ESA TerraMind | Apache 2.0 |
| Facility data | healthsites.io v3 | Open (OSM-linked) |
| Imagery | Sentinel-1, Sentinel-2 | Free, ESA Copernicus |
| Elevation | Copernicus DEM / SRTM | Free |
| Road network | OpenStreetMap via OSMnx | ODbL |
| Ground truth | DHS Program | Free with registration |
| Benchmark raster | MAP 2020 Weiss et al. | CC-BY |
| Routing core | scikit-image MCP_Geometric | BSD |
| On-road graph | OSMnx + iGraph | MIT / GPL |

No paid APIs. No proprietary tiles. No gated weights. The whole thing is reproducible from a fresh checkout.

## Scope of v1

**One country, one ADM1 region.** Candidates:

- **Malawi (MWI)**, recent DHS (2015–16, 2024), good OSM coverage in Southern Region, small enough to be tractable. There's a 2025 *Communications Medicine* paper on Blantyre catchment areas we can compare against.
- **Burkina Faso (BFA)**, multiple DHS rounds, very different terrain profile (Sahel), well-studied accessibility literature.

Default pick: **Malawi Southern Region** unless something compelling argues for BFA.

## What v1 explicitly does *not* include

- Global coverage.
- Multimodal routing (cars, transit), walking only, matching MAP's walking layer.
- Web UI / hosted API / Django anything.
- Real-time updates.
- Training TerraMind from scratch, only fine-tuning a head.
- Service-level reliability, this is a research artifact, not a production system.

## Evaluation

Two metrics, reported with caveats:

1. **MAE vs MAP 2020 raster** (per-pixel, in minutes), measures agreement with the published benchmark. Expect tight agreement on roads, more divergence off-road (which is where we *expect* to differ, that's the point).
2. **MAE vs DHS reported travel times** at cluster locations, measures agreement with human experience. The 2022 PMC study comparing modeled vs perceived accessibility in sub-Saharan Africa suggests *no* model does well here, which makes the absolute number less important than the comparison: does fusion beat pure-friction on this metric?

A difference map (ours minus MAP) is the most useful single visualization, it shows where the methods disagree and why.

## Open questions to resolve before v1

- [ ] Confirm TerraMind-Small fine-tunes acceptably on a single GPU / Colab session.
- [ ] Verify healthsites.io v3 coverage for Malawi (facility count, completeness).
- [ ] Pick exact DHS round + variable harmonization approach.
- [ ] Decide isotropic vs anisotropic default for v1.
- [ ] Decide whether to publish the fine-tuned head weights (HF? in-repo? both?).

## Related work

Tirtha sits in a literature with both healthcare-specific neighbors and
broader satellite-imagery-to-graph neighbors. The full bibliography is at
[`docs/references.md`](references.md). Key relationships:

- **Friction-surface accessibility**: Weiss et al. (2018, 2020) established
  the canonical methodology with hand-engineered rules over land cover.
  Wu et al. (2025, *Nature Communications*) extended to 30m global at
  six infrastructure categories, still rule-based. Tirtha replaces the
  rule-based component with a foundation-model-derived friction surface.
- **On/off-road fusion**: Ray & Ebener (2008) introduced this in
  AccessMod. Tirtha extends their methodology by substituting an
  FM-derived off-road surface for the rule-based one.
- **Satellite-imagery-to-graph for navigation**: OVerSeeC (Rana et al.,
  2026, RSS-ROAR) is the closest concurrent published work. They use
  SAM + Gemma-2-27B + Qwen2.5-Coder-14B on satellite imagery to produce
  off-road robot navigation costmaps. Different domain (ground robots),
  different compute envelope (GPU-cluster), different output (raster
  costmap, not a unified pixel+road graph). Tirtha's open-source +
  laptop-tier + EO-native FM positioning does not overlap.
- **Earlier graph-from-imagery work**: URA* (Pal et al. 2023), Tile2Net
  (VIDA-NYU 2023), and CRESI (Van Etten 2018) each have pieces of the
  pattern (CNN-based traversability, sidewalk graphs, road graphs from
  satellite) but predate the foundation-model era and do not fuse pixel
  and road networks as a single sparse adjacency.
- **Foundation models for Earth observation**: TerraMind (Jakubik et al.
  2025) is the open-weight multimodal generative FM that Tirtha uses.
  Prithvi-EO-2.0 (Szwarcman et al. 2024) is an alternative open-weight
  candidate not currently exercised in Tirtha; cross-FM validation is
  on the roadmap.
- **Conformal calibration**: Vovk et al. (2005) established conformal
  prediction; Romano et al. (2019) introduced the conformalized quantile
  regression (CQR) variant used in Tirtha's calibration. Angelopoulos
  & Bates (2023) is a useful tutorial reference.

## What Tirtha invents

Four design choices are not in any cited prior work. They are documented
explicitly so reviewers can see the boundary between applied and novel
contributions:

1. **FM-as-frozen-friction-extractor.** Using TerraMind as a frozen
   feature extractor whose embeddings are mapped to per-pixel friction
   via an in-chip logistic regression probe trained against rasterized
   OSM road labels.
2. **Linear friction blending** between rule-based off-road Tobler and
   walking-on-road speeds: `friction = (1 - P) * Tobler + P * road_walk`.
3. **Unified pixel-plus-road sparse adjacency** as a loadable artifact.
   AccessMod has the fusion idea conceptually; Tirtha exposes it as a
   `scipy.sparse.csr_matrix` plus per-node attributes.
4. **Conformal calibration of MCP outputs.** Conformal prediction is
   well-studied for regression; applying it to accessibility maps with
   marginal coverage guarantees over the travel-time raster is, to our
   knowledge, novel.

---

*This document is a design commitment, not a finished plan. It will be edited as the implementation forces clarifications.*
