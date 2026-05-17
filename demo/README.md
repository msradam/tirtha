# Tirtha terminal demo

A short terminal recording showing the `tirtha` CLI running end-to-end on
Brownsville, Brooklyn — first for healthcare access, then for school access
using the same pipeline with one argument changed.

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
2. `tirtha accessibility --help` — the subcommand
3. `tirtha accessibility run --region "Brownsville, Brooklyn" --out ./demo-out`
4. `ls demo-out/` and `cat demo-out/summary.txt` — generated artifacts
5. Same pipeline run with `--preset schools` — flips the destination set
6. `diff` between the two summaries — same code, different humanitarian question

Total runtime in the demo: ~60 seconds wall-clock once data is cached.

First-time runs are slower (NASADEM tiles, OSM Overpass, building footprints
all fetched fresh). Subsequent runs of the same region complete in ~25 s on
an Apple Silicon MacBook.
