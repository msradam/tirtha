"""friction CLI — placeholder until the pipeline is wired up."""

import typer

app = typer.Typer(help="Travel-time-to-healthcare mapping pipeline.")


@app.command()
def run(
    country: str = typer.Option(..., "--country", help="ISO-3 country code (e.g. MWI)."),
    admin1: str | None = typer.Option(None, "--admin1", help="ADM1 region name."),
    out: str = typer.Option("./output", "--out", help="Output directory."),
) -> None:
    """Run the end-to-end friction pipeline for a target region."""
    typer.echo(f"[stub] would run pipeline for {country} / {admin1 or 'whole country'} → {out}")


@app.command()
def version() -> None:
    """Print friction version."""
    from friction import __version__
    typer.echo(__version__)


if __name__ == "__main__":
    app()
