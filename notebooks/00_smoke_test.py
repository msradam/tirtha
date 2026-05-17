"""Smoke test notebook — confirms the friction package imports and marimo runs.

Run with:  uv run marimo edit notebooks/00_smoke_test.py
"""

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import friction
    return friction, mo


@app.cell
def _(friction, mo):
    mo.md(
        f"""
        # friction · smoke test

        Package version: **{friction.__version__}**

        If you can see this, the environment is wired up correctly.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Next

        - `notebooks/01_malawi_end_to_end.py` — the hero notebook (TBD)
        - See `docs/methodology.md` for the design
        """
    )
    return


if __name__ == "__main__":
    app.run()
