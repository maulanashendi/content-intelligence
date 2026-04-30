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
    from labeling.pipeline import run as run_pipeline

    result = asyncio.run(run_pipeline())
    click.echo(f"labeling complete: {result}")


if __name__ == "__main__":
    cli()
