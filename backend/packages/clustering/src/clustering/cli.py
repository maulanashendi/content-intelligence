import asyncio
import logging

import click

logging.basicConfig(level="INFO", format="%(levelname)s %(name)s %(message)s")


@click.group()
def cli():
    pass


@cli.command()
def run():
    from clustering.pipeline import run as run_pipeline

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    cli()
