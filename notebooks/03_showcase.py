"""tirtha showcase. Reactive marimo notebook for the 10-country gallery.

Reads pre-computed case outputs from docs/cases/ and lets the user pick a
country to inspect. WASM-compatible: only reads static JSON and PNG via
relative URLs, no rasterio or torch in the browser.

Export to a static site:

    uv run marimo export html-wasm notebooks/03_showcase.py -o site/

Deploy via GitHub Pages: serve the produced ``site/`` directory and the
``docs/cases/`` directory as siblings.
"""
from __future__ import annotations

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    mo.md(
        """
        # tirtha: country accessibility gallery

        Pre-computed walking-time-to-nearest-healthcare maps for ten LMIC countries.
        Each case ran end-to-end on a laptop in 4 to 10 minutes wall clock at 100m
        resolution. The whole pipeline (data fetch, friction surface, multi-source
        MCP from facility seeds, accessibility metrics) is one `tirtha accessibility
        run` invocation per country.

        See [docs/methodology.md](https://github.com/msradam/tirtha/blob/master/docs/methodology.md)
        for design details, [docs/plain_english.md](https://github.com/msradam/tirtha/blob/master/docs/plain_english.md)
        for the project without jargon, and the [GitHub repo](https://github.com/msradam/tirtha)
        for the code.
        """
    )
    return (mo,)


@app.cell
def _():
    """Load the gallery index.

    Tries several path conventions so the same notebook works in three contexts:
      1. ``marimo edit notebooks/03_showcase.py`` from repo root: docs/cases/.
      2. ``marimo run notebooks/03_showcase.py`` from repo root: docs/cases/.
      3. WASM bundle at ``site/index.html`` with cases at ``site/cases/``:
         the GHA workflow copies docs/cases to site/cases.
    """
    import json
    from pathlib import Path

    candidate_index_paths = [
        "docs/cases/index.json",       # local from repo root
        "../docs/cases/index.json",    # local from notebooks/
        "cases/index.json",            # WASM relative
        "./cases/index.json",          # WASM relative explicit
    ]

    index = None
    cases_base = None
    last_err = None
    for path_str in candidate_index_paths:
        try:
            p = Path(path_str)
            if p.exists():
                index = json.loads(p.read_text())
                cases_base = str(p.parent)
                break
        except Exception as exc:
            last_err = exc

    if index is None:
        # WASM (pyodide): fall back to HTTP via urllib.
        import urllib.request

        for url in ("./cases/index.json", "cases/index.json", "../docs/cases/index.json"):
            try:
                with urllib.request.urlopen(url) as r:
                    index = json.loads(r.read().decode())
                cases_base = url.rsplit("/", 1)[0]
                break
            except Exception as exc:
                last_err = exc

    if index is None:
        index = {"cases": [], "error": f"could not locate index.json: {last_err}"}
        cases_base = "cases"
    return cases_base, index, json


@app.cell
def _(index, mo):
    cases = index.get("cases", [])
    if not cases:
        mo.md(
            f"""
            ## No cases yet

            Run `uv run python scripts/build_country_cases.py` to populate
            `docs/cases/`. Error (if any): `{index.get('error', '')}`.
            """
        ).callout(kind="warn")
        country_options = []
    else:
        country_options = [(c["iso3"], f"{c['region']} ({c['iso3']})") for c in cases]
    return cases, country_options


@app.cell
def _(country_options, mo):
    selector = mo.ui.dropdown(
        options={label: iso for iso, label in country_options},
        value=country_options[0][1] if country_options else None,
        label="Pick a country",
    )
    selector
    return (selector,)


@app.cell
def _(cases, selector):
    selected_iso = selector.value
    case = next((c for c in cases if c["iso3"] == selected_iso), None)
    return case, selected_iso


@app.cell
def _(cases_base, case, mo, selected_iso):
    if case is None:
        mo.md("Select a country to view its case.")
        return
    fig_url = f"{cases_base}/{selected_iso.lower()}/figures/headline.png"
    mo.md(
        f"""
        ## {case['region']}

        *{case['blurb']}*

        - **ISO3**: `{case['iso3']}`
        - **Resolution**: {case['resolution_m']} m
        - **OSM destinations**: {case['n_destinations']}
        - **Pipeline wall clock**: {case['elapsed_s']:.0f} seconds
        - **CRS**: `{case['crs']}`

        ![headline figure]({fig_url})
        """
    )
    return (fig_url,)


@app.cell
def _(case, mo):
    """Accessibility table per Weiss thresholds."""
    if case is None:
        return
    acc = case["accessibility"]
    rows = "\n".join(
        f"| <= {t:3d} min | {acc['pct_within'][str(t)]:5.1f}% |"
        for t in acc["thresholds_min"]
    )
    mo.md(
        f"""
        ### Accessibility (built-area weighted)

        | Walking time | Share |
        |---|---|
        {rows}

        Total built pixels (population proxy): {int(acc['total_population']):,}.
        """
    )
    return acc, rows


@app.cell
def _(mo):
    mo.md(
        """
        ---

        ## How to run your own country

        ```bash
        uv run tirtha accessibility run --region "Your Country" --resolution 100 --out ./out
        ```

        Or with a custom bbox for any region Nominatim does not have as a polygon:

        ```bash
        uv run tirtha accessibility run \\
          --bbox "W,S,E,N" \\
          --region "Pretty Name" \\
          --resolution 30 \\
          --out ./out
        ```

        Add `--friction fm` to use the TerraMind-derived friction surface
        (downloads ~80 MB of model weights on first run).

        See [the GitHub repo](https://github.com/msradam/tirtha) for installation,
        the CLI surface, and the unit tests.
        """
    )
    return


if __name__ == "__main__":
    app.run()
