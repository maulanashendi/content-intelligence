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


@cli.command("gsc-link")
def gsc_link():
    """Map gsc_page rows to internal articles and populate article_gsc_metric."""
    from core.db import get_session
    from ingest.gsc import link_articles

    async def _run():
        async with get_session() as session:
            return await link_articles(session)

    count = asyncio.run(_run())
    click.echo(f"gsc-link complete: {count} article_gsc_metric rows upserted")


if __name__ == "__main__":
    cli()
