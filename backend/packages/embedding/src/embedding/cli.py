import asyncio

import click
from core.config import settings
from core.logging import configure_logging


@click.command()
def run() -> None:
    configure_logging(settings.log_level)
    count = asyncio.run(_run())
    click.echo(f"Embedded {count} articles")


async def _run() -> int:
    from embedding.pipeline import run as embed

    return await embed()


if __name__ == "__main__":
    run()
