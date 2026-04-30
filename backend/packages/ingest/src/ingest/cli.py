import asyncio
import logging
import sys

import click
from core.config import settings

logging.basicConfig(
    level=settings.log_level,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@click.group()
def cli():
    pass


@cli.command()
def run():
    from ingest.pipeline import run as run_pipeline

    totals = asyncio.run(run_pipeline())
    click.echo(f"ingest complete: {totals}")


if __name__ == "__main__":
    cli()
