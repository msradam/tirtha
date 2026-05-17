# References

Every methodological choice in Tirtha that has prior published grounding,
keyed by where the choice appears in the codebase. Format: short key,
inline summary, full citation. BibTeX-compatible for later use in a paper.

## Cost surfaces and friction

### Tobler1993
Tobler, W. (1993). "Three presentations on geographical analysis and
modeling." National Center for Geographic Information and Analysis Technical
Report 93-1. UC Santa Barbara.
Source of the hiking function `v = 6 * exp(-3.5 * |tan(slope) + 0.05|)` (km/h).
Used in `src/tirtha/friction.py:tobler_friction`.

### Goodchild1977
Goodchild, M. F. (1977). "An evaluation of lattice solutions to the problem
of corridor location." Environment and Planning A, 9(7), 727-738.
Foundational work on 8-connected pixel graphs for least-cost-path analysis.
Background for `src/tirtha/route.py:multi_source_mcp` and
`src/tirtha/graph.py:build_graph`.

### Sethian1999
Sethian, J. A. (1999). "Fast marching methods." SIAM Review, 41(2), 199-235.
Reference for the alternative to Dijkstra on rasters; we use Dijkstra via
scikit-image MCP_Geometric, but Sethian's method is the standard cross-check.

### Knoblauch1996
Knoblauch, R. L., Pietrucha, M. T., & Nitzburg, M. (1996). "Field studies of
pedestrian walking speed and start-up time." Transportation Research Record,
1538(1), 27-38.
Empirical pedestrian speeds. Justifies the 5.5 km/h baseline walking speed
we apply on residential roads in `src/tirtha/friction.py:WALK_KMH_BY_HIGHWAY_RANK`.

### Bohannon1997
Bohannon, R. W. (1997). "Comfortable and maximum walking speed of adults aged
20-79 years: reference values and determinants." Age and Ageing, 26(1), 15-19.
Population reference for adult walking speeds. Comfortable speed across all
age groups: 1.26 to 1.46 m/s, which is 4.5 to 5.3 km/h. Supports our
5.0-6.0 km/h range across highway classes.

## Routing algorithms

### Dijkstra1959
Dijkstra, E. W. (1959). "A note on two problems in connexion with graphs."
Numerische Mathematik, 1(1), 269-271.
The shortest-path algorithm used throughout Tirtha. Multi-source variant in
`src/tirtha/route.py:multi_source_mcp`, also used on the unified
sparse graph from `tirtha.graph` via `scipy.sparse.csgraph.dijkstra`.

### vanderWalt2014
van der Walt, S., Schönberger, J. L., Nunez-Iglesias, J., Boulogne, F.,
Warner, J. D., Yager, N., Gouillart, E., Yu, T., and the scikit-image
contributors (2014). "scikit-image: image processing in Python." PeerJ, 2:e453.
The MCP_Geometric implementation in scikit-image that Tirtha uses for
raster shortest paths.

### Bertolazzi2014
Bertolazzi, E., & Frego, M. (2014). "Semianalytical minimum-time solution for
the optimal control of a vehicle subject to limited acceleration."
Optimal Control Applications and Methods.
Reference for why MCP_Geometric multiplies by the Euclidean distance
between adjacent pixels (not just edge weight), to avoid path-length bias.

## Foundation models

### Jakubik2025
Jakubik, J., et al. (2025). "TerraMind: Large-scale generative multimodality
for Earth observation." arXiv:2504.11171.
The pretrained model used in `src/tirtha/embed.py`. Multimodal generative
foundation model trained on Sentinel-1 + Sentinel-2 + NASADEM + auxiliary
modalities. Apache 2.0 weights on HuggingFace at
ibm-esa-geospatial/TerraMind-1.0-{tiny,small,base,large}.

### Szwarcman2024
Szwarcman, D., et al. (2024). "Prithvi-EO-2.0: A versatile multi-temporal
foundation model for Earth observation applications." arXiv:2412.02732.
Sister foundation model from IBM and NASA. Tirtha does not currently use
Prithvi but it is a candidate for cross-FM validation.

## Conformal prediction and uncertainty

### Vovk2005
Vovk, V., Gammerman, A., & Shafer, G. (2005). "Algorithmic Learning in a
Random World." Springer.
Foundational treatment of conformal prediction. The marginal coverage
guarantee invoked by `src/tirtha/uncertainty.py` and the
`notebooks/02_bench_vs_map.py` validation.

### Romano2019
Romano, Y., Patterson, E., & Candès, E. (2019). "Conformalized Quantile
Regression." Advances in Neural Information Processing Systems 32 (NeurIPS).
The split-conformal CQR variant used in our calibration. Lets us calibrate
quantile-style prediction intervals with finite-sample marginal coverage
guarantees.

### Angelopoulos2023
Angelopoulos, A. N., & Bates, S. (2023). "Conformal Prediction: A Gentle
Introduction." Foundations and Trends in Machine Learning, 16(4), 494-591.
Tutorial introduction to split-conformal prediction. Useful pedagogical
reference for the methodology paper.

## Accessibility metrics

### Hansen1959
Hansen, W. G. (1959). "How accessibility shapes land use." Journal of the
American Institute of Planners, 25(2), 73-76.
Foundational paper on gravity-based accessibility. The intellectual lineage
of "percent of population within N minutes" measures, even though tirtha
uses cumulative-opportunity rather than gravity weighting.

### PenchanskyThomas1981
Penchansky, R., & Thomas, J. W. (1981). "The concept of access: definition
and relationship to consumer satisfaction." Medical Care, 19(2), 127-140.
The five dimensions of access (availability, accessibility, accommodation,
affordability, acceptability). Tirtha measures only "accessibility" (the
physical/temporal dimension); we are explicit in `docs/methodology.md` that
quality, insurance, and trust gaps are not in scope.

### Weiss2020
Weiss, D. J., Nelson, A., Vargas-Ruiz, C. A., Gligorić, K., Bavadekar, S.,
Gabrilovich, E., Bertozzi-Villa, A., Rozier, J., Gibson, H. S., Shekel, T.,
Kamath, C., Lieber, A., Schulman, K., Shao, Y., Qarkaxhija, V., Nandi, A. K.,
Keddie, S. H., Rumisha, S., Amratia, P., Arambepola, R., Chestnutt, E. G.,
Millar, J. J., Symons, T. L., Cameron, E., Battle, K. E., Bhatt, S., &
Gething, P. W. (2020). "Global maps of travel time to healthcare facilities."
Nature Medicine, 26, 1835-1838.
The canonical benchmark Tirtha is calibrated against. Source of the 30-60-120
minute reporting bins used in `src/tirtha/metrics.py:DEFAULT_THRESHOLDS_MIN`.

### Weiss2018
Weiss, D. J., et al. (2018). "A global map of travel time to cities to assess
inequalities in accessibility in 2015." Nature, 553, 333-336.
Earlier MAP friction-surface paper that established the rule-based methodology
Tirtha replaces in its FM-aware variant.

### Wu2025
Wu, B., Chen, B., An, S., Nelson, A., Dai, L., Lin, F., & Gong, P. (2025).
"Measuring global human accessibility to essential daily necessities and
services." Nature Communications, 16:10709.
The closest published peer at country scale. Rule-based friction at 30m
globally, no foundation model, no calibrated uncertainty, no published code.
The four-way head-to-head in `docs/figures/17_wu_headtohead.png` compares
against a re-implementation of this paper's methodology.

### RayEbener2008
Ray, N., & Ebener, S. (2008). "AccessMod 3.0: computing geographic coverage
and accessibility to health care services using anisotropic movement of
patients." International Journal of Health Geographics, 7:63.
The on/off-road fusion methodology Tirtha extends. AccessMod uses rule-based
friction; Tirtha substitutes a foundation-model-derived friction surface.
We cite Ray & Ebener as the methodological lineage we extend.

## Data sources

### Tatem2017
Tatem, A. J. (2017). "WorldPop, open data for spatial demography."
Scientific Data, 4, 170004.
Population weighting in `src/tirtha/metrics.py:population_weighted_accessibility`.
WorldPop UN-adjusted constrained 100m gridded population estimates are the
default population layer.

### Boeing2017
Boeing, G. (2017). "OSMnx: New methods for acquiring, constructing, analyzing,
and visualizing complex street networks." Computers, Environment and Urban
Systems, 65, 126-139.
The OSM-to-NetworkX pipeline used in `src/tirtha/data.py:load_osm_roads`,
`load_osm_facilities`, and `load_osm_buildings`.

### DHS
ICF International. The Demographic and Health Surveys Program. www.dhsprogram.com.
The `v483a` variable (also `HEALTHFACTIM` in IPUMS-DHS) is the survey question
"how long does it take you to get to the nearest health facility?" The
calibration target Tirtha plans to use in v0.2 once registration completes.

### Planetary Computer
Microsoft. (2024). Planetary Computer STAC API.
planetarycomputer.microsoft.com.
Data source for Sentinel-1 RTC, Sentinel-2 L2A, and NASADEM tiles loaded via
`src/tirtha/data.py:load_dem`, `load_sentinel2_rgb` and the multimodal chip
fetch in `src/tirtha/embed.py:fetch_multimodal_chip`.

## Adjacent prior art

These are works Tirtha is aware of but does not directly use. Documented
here so reviewers can see we've surveyed the space.

### Rana2026
Rana, M., Quattrociocchi, S., Lee, J., Ellis, J., Adkins, R., Uccello, A.,
Warnell, G., & Biswas, J. (2026). "OVerSeeC: Open-Vocabulary Cost Map
Generation for Off-road Robot Navigation." arXiv:2602.18606.
RSS-ROAR 2025 Best Paper Runner-up. The most directly concurrent published
work: satellite imagery + SAM + LLMs to produce off-road navigation cost
maps. Different domain (ground robots, not humanitarian accessibility),
different compute envelope (27B + 14B LLMs on GPU clusters, not laptop),
different output (raster costmap, not unified pixel+road graph), no
OSM fusion, no calibrated uncertainty.

### Mi2023
URA*-style work. Pal, A., et al. (2023). "Uncertainty-aware Robot Aerial
Pathfinding for Autonomous Inspection." arXiv:2309.08814.
Aerial imagery to traversability with ensemble CNN + uncertainty-aware A*.
Pre-foundation-model era, no OSM fusion. Has the pattern; precedes the FM.

### Mahabadi2023
The Tile2Net pipeline. Mahabadi, M., et al. (2023). "Tile2Net: Aerial
imagery to topologically interconnected pedestrian network." VIDA-NYU.
github.com/VIDA-NYU/tile2net. Aerial imagery to vector pedestrian graphs.
Different output (vector sidewalk network, not unified cost graph), no FM,
no fusion with vehicle road network.

### vanEtten2018
Van Etten, A., et al. (2018). "City-scale road extraction from satellite
imagery." github.com/avanetten/cresi. Satellite imagery to routable road
graph as NetworkX. Road-only, no off-road, no FM, no friction surface.
The road extraction half of what Tirtha does end-to-end.

## What Tirtha invents

These design choices have no specific prior-art citation. They are documented
here so the reader can see exactly which pieces are ours.

1. **FM-as-frozen-friction-extractor.** Using a pretrained Earth-observation
   foundation model (TerraMind) as a frozen feature extractor whose
   embeddings are projected onto a per-pixel friction estimate via an
   in-chip logistic regression probe against rasterized OSM road labels.
   Implementation in `src/tirtha/embed.py:estimate_p_road_from_chip`. To
   our knowledge, this specific approach is not in any published prior
   work as of May 2026.

2. **Linear friction blending.** Combining the rule-based off-road Tobler
   friction with road-walking speeds via a convex combination weighted by
   FM-predicted P(road): `friction = (1 - P) * Tobler + P * road_walk`.
   Implementation in `src/tirtha/friction.py:fm_blended_friction`. Linear
   blending is the simplest defensible choice; we don't claim it's
   optimal.

3. **Unified pixel-plus-road sparse adjacency.** A single
   `scipy.sparse.csr_matrix` whose rows are both raster pixels and OSMnx
   road-graph nodes, joined at zero-cost edges where coincident.
   Implementation in `src/tirtha/graph.py:build_graph`. AccessMod (Ray &
   Ebener 2008) has the fusion idea conceptually; we expose it as a
   loadable artifact you can run any graph algorithm on.

4. **Conformal calibration of MCP outputs.** Applying split-conformal CQR
   (Romano et al. 2019) to ensemble-derived travel time estimates so the
   final per-pixel intervals have a marginal coverage guarantee. Conformal
   prediction is well-studied for regression; applying it end-to-end to
   accessibility maps is, to our knowledge, novel.
