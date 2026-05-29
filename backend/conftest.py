"""Pytest bootstrap: route every test through a dedicated test database.

The dev DB and the test DB used to be the same Postgres database, so any
test fixture that truncated `article` or `content_source` would wipe the
editor's seeded data. This module creates (or reuses) a separate database
named after `TEST_DATABASE_URL` (or `<dev_db>_test` when the env var is
unset), runs Alembic migrations against it, and re-binds `core.db` and
`settings.database_url` for the rest of the test session. The api and
ingest package conftests pick up the rebinding transparently.
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse, urlunparse

import pytest
from core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _resolve_test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    parsed = urlparse(settings.database_url)
    db = parsed.path.lstrip("/")
    if not db:
        raise RuntimeError("DATABASE_URL has no database name; set TEST_DATABASE_URL explicitly.")
    return urlunparse(parsed._replace(path=f"/{db}_test"))


def _admin_database_url() -> str:
    parsed = urlparse(settings.database_url)
    return urlunparse(parsed._replace(path="/postgres"))


TEST_DATABASE_URL = _resolve_test_database_url()


async def _ensure_test_database_exists() -> None:
    test_db_name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    admin_engine = create_async_engine(_admin_database_url(), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            existing = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": test_db_name},
            )
            if existing.scalar() is None:
                await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        await admin_engine.dispose()


def _run_migrations_on_test_db() -> None:
    from alembic.config import Config

    from alembic import command

    repo_root = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(repo_root, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    cfg.set_main_option("script_location", os.path.join(repo_root, "alembic"))
    # alembic/env.py prefers $DATABASE_URL over the cfg url; pin it to the test DB
    # for the upgrade so a set DATABASE_URL can never redirect migrations onto the dev DB.
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    try:
        command.upgrade(cfg, "head")
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev


_TRACKED_TABLES = (
    "article",
    "article_cluster",
    "article_embedding",
    "cluster_insight",
    "content_source",
    "trend_signal",
)


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end(_isolate_test_database: None) -> None:
    """Fail if any test leaked committed rows into the test DB after the session ends."""
    yield

    async def _count_rows() -> list[str]:
        engine = create_async_engine(TEST_DATABASE_URL)
        try:
            async with engine.connect() as conn:
                leaks = []
                for table in _TRACKED_TABLES:
                    count = (await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar()
                    if count:
                        leaks.append(f"{table}={count}")
                return leaks
        finally:
            await engine.dispose()

    leaks = asyncio.run(_count_rows())
    assert not leaks, (
        "Test DB leaked committed rows after session — check fixture cleanup: "
        + ", ".join(leaks)
    )


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    if settings.database_url == TEST_DATABASE_URL:
        raise RuntimeError(
            "TEST_DATABASE_URL must differ from DATABASE_URL — running tests "
            "against the dev DB would destroy seeded data. Set TEST_DATABASE_URL "
            "or rename the dev database."
        )

    asyncio.run(_ensure_test_database_exists())
    _run_migrations_on_test_db()

    import core.db as _core_db

    settings.database_url = TEST_DATABASE_URL
    _core_db._engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    _core_db._session_factory = async_sessionmaker(_core_db._engine, expire_on_commit=False)
