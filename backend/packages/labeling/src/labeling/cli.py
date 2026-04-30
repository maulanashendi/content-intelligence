import asyncio
import logging

import click
from core.config import settings
from core.logging import configure_logging

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Labeling commands."""


@cli.command()
def run():
    from labeling.pipeline import run as run_pipeline

    result = asyncio.run(run_pipeline())
    logger.info("labeling cli complete", extra=result)


if __name__ == "__main__":
    cli()
