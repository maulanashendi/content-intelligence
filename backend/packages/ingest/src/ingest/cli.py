import asyncio

import click
from core.config import settings
from core.logging import configure_logging

configure_logging(settings.log_level)


@click.group()
def cli():
    pass


@cli.command()
def run():
    from ingest.pipeline import run as run_pipeline

    totals = asyncio.run(run_pipeline())
    click.echo(f"ingest complete: {totals}")


@cli.command()
def seed():
    from ingest.seed import seed_sources

    inserted = asyncio.run(seed_sources())
    click.echo(f"seeded {inserted} new sources")


if __name__ == "__main__":
    cli()
