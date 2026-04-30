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
    from clustering.pipeline import run as run_pipeline

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    cli()
