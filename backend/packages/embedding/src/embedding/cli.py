import asyncio
import logging
import sys

import click
from core.config import settings


@click.command()
def run() -> None:
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stdout,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    count = asyncio.run(_run())
    click.echo(f"Embedded {count} articles")


async def _run() -> int:
    from embedding.pipeline import run as embed

    return await embed()


if __name__ == "__main__":
    run()
