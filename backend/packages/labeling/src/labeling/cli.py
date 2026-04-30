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
    from labeling.pipeline import run as run_pipeline

    result = asyncio.run(run_pipeline())
    click.echo(f"labeling complete: {result}")


if __name__ == "__main__":
    cli()
