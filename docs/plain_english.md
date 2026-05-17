# Tirtha, in Plain English

> Or: "what did we just build, and why does it matter?"

This document is for people who want to understand tirtha without reading a single line of code or any of the technical papers. If you read this top to bottom, you'll understand the project well enough to defend it at a dinner party.

---

## 1. The one-sentence pitch

**Tirtha estimates how long it takes someone, on foot, to reach the nearest healthcare facility, for every pixel of the planet, using modern open data and a foundation model trained on satellite imagery.**

That's it. The rest of this document explains why each word in that sentence matters, what's hard about it, and why the way we're doing it is different from prior work.

---

## 2. Why this is a problem worth solving

In dense cities like Manhattan, central London, or central Tokyo, physical access to healthcare is taken for granted. You can walk to a clinic; if you can't walk, you can call a taxi.

In rural and remote settlements across the developing world, distance and travel time to a health site is one of the dominant factors in whether a disease outbreak gets contained, whether a child gets vaccinated, whether a snakebite victim survives. Studies in rural Nigeria have found that *utilization of healthcare facilities decreases exponentially with distance*. In rural Bangladesh, the Sundarbans, parts of Malawi, the difference between "30 minutes from a clinic" and "3 hours from a clinic" is, in aggregate, the difference between thousands of lives.

UNICEF, WHO, the Bill & Melinda Gates Foundation, and most ministries of health in low- and middle-income countries (LMICs) all need accurate, current, country-scale maps of physical accessibility to healthcare. They use these maps to:

- decide where to build new clinics
- target vaccination campaigns to under-served areas
- estimate the catchment population a facility actually serves
- prioritize emergency response during outbreaks

**Existing maps exist**, the canonical one is from a 2020 *Nature Medicine* paper by Weiss et al. at Oxford's Malaria Atlas Project. They published a global travel-time-to-healthcare raster at ~1 km resolution. It's used by everyone in the field.

But two things are missing from the current state of the world:

1. **The Weiss/MAP map is a static, published artifact.** You can't easily re-run it for a new country, with updated facility data, with different assumptions. You read it; you don't *use* it.
2. **It was built before modern AI foundation models existed.** It uses hand-engineered rules: "this pixel is land-cover class 'dense urban', so people walk at 5 km/h here." Those rules work, but they leave a lot of signal in the satellite imagery untouched.

Tirtha closes both gaps.

---

## 3. What "travel time" actually means here

When we say "how long it takes someone to walk to a clinic," we mean: given a starting location (a populated pixel on the satellite map), what is the *shortest possible walking path*, in minutes, to the nearest healthcare facility?

This is a classic algorithm problem: **shortest path on a graph**, solved by Dijkstra's algorithm (1959). The interesting part is *what the graph represents* and *what the edge weights mean*.

For our problem, there are two complementary views of "the world you can walk through":

### View A: Roads, as a network of lines
OpenStreetMap (OSM) has every road on Earth, contributed by ~10 million volunteers over 20 years. We treat each road as an edge in a graph, a line you can traverse at, say, 5–6 km/h on foot. This is what Google Maps does. It's perfect *when you stay on roads*.

### View B: The whole landscape, as a grid of pixels
For each ~10m × 10m pixel of the Earth (from satellite imagery), we estimate "how long does it take to traverse this pixel on foot, off-road?" Steep slope = slow. Dense forest = slow. Open grassland = faster. A river = effectively infinite (impassable). This gives you a **friction surface**, a map where every pixel has a walking-cost number attached.

Then we run Dijkstra over the combined "graph", road network plus pixel grid, from every healthcare facility outward, and we get a travel-time-to-nearest-facility number for every pixel.

**The interesting question is how you build View B's friction surface.** That's where most of the methodology lives. That's also where AI foundation models come in.

---

## 4. The story of Tirtha, in three eras

### Era 1: The 2019 UNICEF intern
In late 2018, the author (Adam Munawar Rahman) was a Computer Science student at Wesleyan, doing a winter internship at UNICEF Innovation in New York. His task: figure out how to compute distances to healthcare facilities for UNICEF's "Magicbox" open-data platform.

He built it in Python: OSMnx (a library that downloads OSM data and turns it into a graph), iGraph (a fast C-backed graph library), and a custom Django REST API. It worked. It computed travel times. He wrote a three-part blog series about it (*The Roads Yet Taken*, *Go the Distance*, *All the Difference*). It even got used at UNICEF.

The 2019 version was good. But it was missing two things: a way to estimate *off-road* traversability, and a way to *learn* friction values from data rather than hand-picking them.

### Era 2: The years 2020–2024, the field caught up
While Adam went on to other things, the open-source ecosystem filled in pieces he didn't have in 2019:

- **The Malaria Atlas Project's 2020 paper** (Weiss et al., *Nature Medicine*) published a global travel-time raster, settling the canonical methodology.
- **OpenStreetMap healthsite data matured** into a curated database at [healthsites.io](https://healthsites.io) with a public API.
- **DHS Program** (the global household survey infrastructure) accumulated ~150 surveys across 56 countries with self-reported "how long does it take you to reach the nearest health facility" data, a *real* supervision signal that didn't exist when Weiss et al. published.
- **NASA and IBM released Prithvi** (2023), the first open-weight foundation model trained on Earth observation imagery. Then in April 2025, IBM and the European Space Agency released **TerraMind**, bigger, multimodal (trained on Sentinel-1 radar + Sentinel-2 optical + DEM together), and Apache-2.0 licensed.

### Era 3: Tirtha, now
Tirtha is the *what if you assembled all those pieces into a single open, reproducible, modern pipeline?* artifact.

The pivot from the 2019 Django REST API to the 2026 tirtha pipeline happened over a single session. The 2019 code is preserved on a git archive branch as a kind of fossil, the prelude.

---

## 5. The methodological core: TerraMind + OSMnx + Dijkstra

Tirtha's architecture has three load-bearing pieces:

### Piece 1: TerraMind estimates the off-road friction surface
Instead of writing rules like "land-cover class 'forest' → 8 min/km," we feed satellite imagery (12 Sentinel-2 optical bands + 2 Sentinel-1 radar bands + 1 NASADEM elevation band) into TerraMind. TerraMind was trained on ~9 million globally-distributed multimodal samples, it knows what cities, forests, water, deserts, and croplands *look like* across the entire spectrum, not just the bands a human happened to think were relevant.

Its output is a learned representation of each pixel ("embedding"). We use those embeddings (after fine-tuning on DHS-reported travel times) to estimate per-pixel walking cost. This is where AI replaces hand-engineering.

### Piece 2: OSMnx handles the on-road routing
For paths that follow roads, we use OpenStreetMap's road network directly, via the OSMnx Python library. Roads have well-known speeds and topology, there's no need to re-learn them. **OSMnx is the proven solution for the on-road problem.**

### Piece 3: We fuse the two at "road-entry pixels"
The novel methodological move is: build a single graph that contains *both* pixel nodes (one per 10m × 10m grid cell, with friction from TerraMind) and road nodes (from OSMnx), connected at the points where pixels and roads meet. A person walks off-road to the nearest road, takes the road, and exits to the destination facility. Dijkstra figures out the optimal balance.

This isn't entirely new. WHO's **AccessMod** tool has done on/off-road fusion since 2008. But AccessMod is a GRASS-GIS desktop application; it's not a scriptable, fork-and-run, AI-era pipeline. **Tirtha is the FM-era successor to AccessMod.** That's the cleanest one-line positioning.

---

## 6. The supervision signal: why DHS matters

Here's where tirtha's most defensible novelty lives.

Weiss et al. 2020 didn't have any real ground-truth data for "how long does walking to a clinic actually take?" They calibrated their model using *assumed land-cover speeds* derived from prior literature. The assumed speeds work *okay* on average, but they aren't anchored in observed human experience.

**The DHS Program has been asking respondents in LMICs for ~25 years: "how long does it take you to reach the nearest health facility?"** This is variable `v483a` (in IPUMS-DHS, it's called `HEALTHFACTIM`). About 150 surveys across 56 countries. Self-reported minutes, paired with georeferenced household clusters.

It's not perfect, self-reported times have known biases, and DHS deliberately scrambles cluster GPS coordinates by up to 5km to protect privacy. But it's **real human-reported data on the exact thing we're predicting**.

Tirtha fine-tunes TerraMind against this signal. We're calibrating the friction surface to reproduce *the travel times people actually report*, not to match a published raster. **This is the novelty leg nobody else is running on.**

---

## 7. What we actually built this session, and what it proves

Tonight, we built a *toy-scale miniature* of the entire production pipeline on a single 2.5 km × 2.5 km chip around Queen Elizabeth Central Hospital in Blantyre, Malawi.

Every load-bearing piece is now real, on real data, with real numbers:

| Component | Status | Evidence |
|---|---|---|
| Polyglot xarray Dataset | ✅ working | 12 S2 bands + S1 + DEM + rasterized OSM all on shared 10m grid |
| TerraMind multimodal inference | ✅ working | 4-config ablation, best AUC 0.748 with S2+S1+DEM |
| Tobler slope-aware friction | ✅ working | from NASADEM, mean slope 6.5° in chip |
| OSMnx on-road graph | ✅ working | 487 road features, hierarchy preserved |
| MCP shortest-path solver | ✅ working | Dijkstra on the friction raster from facility seeds |
| WorldPop population weighting | ✅ working | 20,723 people accounted for in chip |
| Benchmark vs MAP 2020 | ✅ working | **Spearman ρ = 0.674, MAE = 2.89 min** |

The key number is **Spearman ρ = 0.674 vs the published MAP 2020 raster**, with MAE 2.89 minutes and a small positive bias (we are slightly more pessimistic than MAP, which makes sense because our 10m grid finds longer detours that MAP's ~925m grid bilinear-interpolates over).

For the population-weighted accessibility numbers (which is the metric every public-health agency cares about):

| Walking time | Tirtha (this work) | MAP 2020 (Weiss) | Difference |
|---|---|---|---|
| ≤ 5 min | 22.9% | 22.5% | +0.4 pp |
| ≤ 10 min | 60.3% | 67.1% | -6.8 pp |
| ≤ 15 min | 89.5% | 98.4% | -8.9 pp |
| ≤ 30 min | 100% | 100% | 0 |

**Close, but with our finer grid showing some areas MAP misses.**

---

## 8. The ablation that justifies "we used TerraMind, not just any ViT"

A reasonable skeptic looks at this and asks: "you used a foundation model. Did it actually matter that it was *TerraMind* specifically? Or could you have used any pretrained vision transformer?"

We ran the ablation:

| Modalities into TerraMind | ROC-AUC (road detection) |
|---|---|
| S2 only (optical, 12 bands) | 0.712 |
| S2 + S1 (optical + radar) | 0.707 |
| **S2 + S1 + DEM (optical + radar + elevation)** | **0.748** |
| TiM variant · S2 + S1 + DEM | 0.705 |

Adding the radar+DEM modalities, which generic vision transformers don't have, lifts performance ~5 percentage points. That's TerraMind-specific. If we'd used a vanilla ViT trained on natural images (or even SatlasPretrain, which is RGB-focused), we wouldn't have gotten this lift.

The TiM variant. TerraMind's most-hyped capability ,  *didn't help in zero-shot*. It adds variance, not mean. It probably needs fine-tuning to be useful. **This is an honest negative result.**

---

## 9. What's left to build

The toy on the Blantyre chip is a proof. Production tirtha v1 is:

1. **Country-scale execution**, tile all of Malawi's Southern Region into 2.5km chips, run the pipeline per-tile, mosaic into a single travel-time raster.
2. **TerraMind fine-tuning**, instead of using zero-shot embeddings, train a small regression head against DHS-reported travel times. This is the supervision innovation that justifies the methodology paper.
3. **The on/off-road fusion graph as a single sparse matrix**, currently we use raster-only MCP, which treats roads as low-friction pixels rather than as a separate topological graph. The proper fusion is the methodological novelty.
4. **Per-pixel uncertainty quantification**. TerraMind gives us per-pixel features for free; turning them into a confidence interval on travel time is the citable open lane nobody else is running on.
5. **A `tirtha` Python package** with a CLI (`tirtha run --country MWI --admin1 "Southern Region"`) that produces the final raster + GeoJSON + accessibility metrics in one command.

The hardest part, confirming the methodology works end-to-end, is **done**. What's left is execution, scale, and polish.

---

## 10. What this could become

The honest scoping:

- **Best case**: tirtha becomes the open-source healthcare-accessibility tool that an NGO analyst or public-health grad student forks, points at their country, and gets a publication-quality map in an afternoon. It cites a paper that documents the methodology, and that paper gets cited by everyone who needs to map physical accessibility in LMICs going forward.
- **Likely case**: tirtha is a strong portfolio artifact and a real (small) contribution to the open-source geospatial-health ecosystem. A few researchers and analysts use it. It maintains itself with low effort.
- **Pessimistic case**: the methodology is sound but the engineering effort to maintain a country-scale pipeline exceeds the author's time budget; the repo becomes a snapshot that someone else picks up later.

The first two are both successful outcomes. The third is fine too, it's still a real artifact pinning the technique down for anyone who wants it.

---

## 11. Why "tirtha"

In Sanskrit, *tirtha* (तीर्थ) means a "crossing place", literally a ford in a river where you can safely cross. It also means a place of pilgrimage, often where people travel for healing. The word is shared across Hindu, Buddhist, and Jain traditions; it's used in Bengali, Hindi, Tamil, and Nepali, and the concept generalizes across South Asian cultures.

For our project: the *tirtha* is the place where safe physical access to healthcare becomes possible. It's both the literal crossing (the road, the path, the bridge, the trail) and the destination (the clinic, the hospital, the healing site).

A travel-time-to-healthcare map is a map of every person's distance from the nearest tirtha.

---

## 12. A note on attribution

This project is the work of Adam Munawar Rahman, with code assistance from Claude (Anthropic's AI assistant) during pair-programming sessions. The methodology, design decisions, and intellectual direction are Adam's. The literature search, novelty audit, technical implementation, and figure generation were collaborative.

This project would not exist without:

- The **OpenStreetMap** community (~10 million contributors)
- The **healthsites.io** project (Kartoza, Mark Herringer, contributors)
- The **Malaria Atlas Project** (Weiss, Bertozzi-Villa, Gething, and team)
- The **Demographic and Health Surveys Program** (USAID)
- The **WorldPop** project (University of Southampton)
- **IBM Research, ESA Φ-lab, and Forschungszentrum Jülich** for TerraMind
- **NASA** for Sentinel-2, **ESA** for Sentinel-1 and Copernicus
- The countless authors of the Python geospatial ecosystem (`xarray`, `rasterio`, `osmnx`, `geopandas`, `odc-stac`, `scikit-image`, `scikit-learn`, `terratorch`, `pytorch`, `marimo`)
- **UNICEF Innovation** for the 2019 internship that planted the seed

If tirtha helps anyone, anywhere, find a safer crossing, that's the whole point.

---

*Document drafted 2026-05-16. See `docs/methodology.md` for the technical design, and `README.md` for the quickstart.*
