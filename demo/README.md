# Tirtha terminal demo

A short terminal recording showing the `tirtha` CLI running end-to-end on
**Kew Gardens, Queens** — the author's home neighborhood. First for healthcare
access, then for schools (same pipeline, one argument changed), then the graph
artifact (pixels + roads as a single loadable object).

## Producing the GIF

Install [vhs](https://github.com/charmbracelet/vhs) (Charm's terminal-recording
tool):

```bash
brew install vhs
```

Then from the repo root:

```bash
vhs demo/tirtha.tape
```

This produces `demo/tirtha.gif` (or `.mp4` if you change `Output` in the tape).

## What the demo shows

1. `tirtha --help` — the CLI surface
2. `tirtha accessibility run --bbox ... --region "Kew Gardens, Queens"`
3. `ls demo-out/kew-health/` and `cat summary.txt` — generated artifacts
4. Same pipeline run with `--preset schools` — flips the destination set
5. `diff` between the two summaries — same code, different humanitarian question
6. `tirtha graph build` — produce a unified pixel + road graph artifact
7. `tirtha graph inspect` — one-line summary of the saved graph

Why Kew Gardens? Nominatim doesn't have it as an OSM polygon, so we pass `--bbox`
explicitly. Many neighborhoods, informal settlements, and custom AOIs work this
way — and the option is documented up-front in the demo.

Total runtime in the demo: ~2 minutes wall-clock once data is cached. First-time
runs are slower (NASADEM tiles, OSM Overpass, building footprints fetched fresh).
Subsequent runs of the same chip complete in ~20 s on an Apple Silicon MacBook.
