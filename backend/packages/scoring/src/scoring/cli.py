import asyncio

import click

from scoring.pipeline import run


@click.group()
def main() -> None:
    pass


@main.command("run")
def run_command() -> None:
    cluster_count = asyncio.run(run())
    click.echo(f"scored {cluster_count} current clusters")


if __name__ == "__main__":
    main()
