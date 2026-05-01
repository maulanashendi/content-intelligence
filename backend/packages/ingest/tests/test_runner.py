import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from core.db import get_session
from core.models import ContentSource, SourceType
from ingest.rss import BlockedError
from ingest.runner import _fetch_one_source, _is_blocked, _mark_blocked, _run_once


@pytest.fixture(autouse=True)
def reset_blocked_state() -> None:
    import ingest.runner as _runner
    _runner._blocked_until.clear()
    yield
    _runner._blocked_until.clear()


# ---------------------------------------------------------------------------
# _is_blocked / _mark_blocked — pure in-memory logic
# ---------------------------------------------------------------------------


def test_is_blocked_false_for_unknown_source() -> None:
    assert _is_blocked(uuid.uuid4()) is False


def test_mark_blocked_prevents_immediate_refetch() -> None:
    sid = uuid.uuid4()
    _mark_blocked(sid, "test-source")
    assert _is_blocked(sid) is True


def test_is_blocked_true_within_block_window() -> None:
    import ingest.runner as _runner

    sid = uuid.uuid4()
    _runner._blocked_until[sid] = datetime.now(UTC) + timedelta(hours=1)
    assert _is_blocked(sid) is True


def test_is_blocked_false_after_expiry() -> None:
    import ingest.runner as _runner

    sid = uuid.uuid4()
    _runner._blocked_until[sid] = datetime.now(UTC) - timedelta(seconds=1)
    assert _is_blocked(sid) is False
    assert sid not in _runner._blocked_until


# ---------------------------------------------------------------------------
# _run_once — with mocked DB + fetch_and_store_source
# ---------------------------------------------------------------------------


def _make_session_ctx(sources: list):
    mock_result = MagicMock()
    mock_result.scalars.return_value = sources
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _ctx():
        yield mock_session

    return _ctx


@pytest.mark.asyncio
async def test_run_once_skips_blocked_sources() -> None:
    import ingest.runner as _runner

    sid = uuid.uuid4()
    _runner._blocked_until[sid] = datetime.now(UTC) + timedelta(hours=1)

    source = MagicMock(id=sid, url="https://blocked.example.com/feed", name="Blocked")
    ctx = _make_session_ctx([source])

    with patch("ingest.runner.get_session", ctx), \
         patch("ingest.runner.fetch_and_store_source") as mock_fetch:
        await _run_once()

    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_run_once_calls_fetch_for_active_sources() -> None:
    sid = uuid.uuid4()
    source = MagicMock(id=sid, url="https://active.example.com/feed", name="Active")
    ctx = _make_session_ctx([source])
    calls: list[uuid.UUID] = []

    async def _capture(client, source_id, *_args):
        calls.append(source_id)
        return 3

    with patch("ingest.runner.get_session", ctx), \
         patch("ingest.runner.fetch_and_store_source", _capture):
        await _run_once()

    assert calls == [sid]


@pytest.mark.asyncio
async def test_run_once_marks_source_blocked_on_blocked_error() -> None:
    import ingest.runner as _runner

    sid = uuid.uuid4()
    source = MagicMock(id=sid, url="https://blocked.example.com/feed", name="WillBlock")
    ctx = _make_session_ctx([source])

    async def _raise_blocked(*_args, **_kwargs):
        raise BlockedError("provider blocked us")

    with patch("ingest.runner.get_session", ctx), \
         patch("ingest.runner.fetch_and_store_source", _raise_blocked):
        await _run_once()

    assert _is_blocked(sid)


@pytest.mark.asyncio
async def test_run_once_continues_on_generic_exception() -> None:
    sid1, sid2 = uuid.uuid4(), uuid.uuid4()
    sources = [
        MagicMock(id=sid1, url="https://fail.example.com/feed", name="Fail"),
        MagicMock(id=sid2, url="https://ok.example.com/feed", name="Ok"),
    ]
    ctx = _make_session_ctx(sources)
    calls: list[uuid.UUID] = []

    async def _selective(client, source_id, *_args):
        if source_id == sid1:
            raise RuntimeError("unexpected error")
        calls.append(source_id)
        return 1

    with patch("ingest.runner.get_session", ctx), \
         patch("ingest.runner.fetch_and_store_source", _selective):
        await _run_once()

    assert calls == [sid2]


# ---------------------------------------------------------------------------
# _fetch_one_source — guard conditions with real DB (NullPool via conftest)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def disabled_source() -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Disabled",
        url="https://disabled.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=False,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source


@pytest.mark.asyncio
async def test_fetch_one_source_skips_disabled_source(disabled_source: ContentSource) -> None:
    with patch("ingest.runner.fetch_and_store_source") as mock_fetch:
        await _fetch_one_source(disabled_source.id)
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_one_source_skips_nonexistent_source() -> None:
    with patch("ingest.runner.fetch_and_store_source") as mock_fetch:
        await _fetch_one_source(uuid.uuid4())
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_one_source_skips_currently_blocked_source(
    rss_source: ContentSource,
) -> None:
    _mark_blocked(rss_source.id, rss_source.name)

    with patch("ingest.runner.fetch_and_store_source") as mock_fetch:
        await _fetch_one_source(rss_source.id)

    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_one_source_marks_blocked_on_429(rss_source: ContentSource) -> None:
    import ingest.runner as _runner

    async def _raise_blocked(*_args, **_kwargs):
        raise BlockedError("429")

    with patch("ingest.runner.fetch_and_store_source", _raise_blocked):
        await _fetch_one_source(rss_source.id)

    assert _is_blocked(rss_source.id)

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)
    assert source is not None
    from core.models import SourceStatus

    assert source.status == SourceStatus.blocked


@pytest.mark.asyncio
async def test_fetch_one_source_sets_error_status_on_generic_failure(
    rss_source: ContentSource,
) -> None:
    async def _raise_generic(*_args, **_kwargs):
        raise RuntimeError("upstream RST")

    with patch("ingest.runner.fetch_and_store_source", _raise_generic):
        await _fetch_one_source(rss_source.id)

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)
    assert source is not None
    from core.models import SourceStatus

    assert source.status == SourceStatus.error


@pytest.mark.asyncio
async def test_fetch_one_source_calls_fetch_for_enabled_source(
    rss_source: ContentSource,
) -> None:
    fetched: list[uuid.UUID] = []

    async def _capture(client, source_id, source_url, source_name):
        fetched.append(source_id)
        return 1

    with patch("ingest.runner.fetch_and_store_source", _capture):
        await _fetch_one_source(rss_source.id)

    assert fetched == [rss_source.id]


# ---------------------------------------------------------------------------
# Bounded immediate queue: overflow drops oldest, never raises
# ---------------------------------------------------------------------------


def test_enqueue_immediate_overflow_drops_oldest() -> None:
    import ingest.runner as _runner

    _runner._immediate.clear()

    for i in range(_runner.IMMEDIATE_QUEUE_MAX + 5):
        _runner._enqueue_immediate(f"payload-{i}")

    assert len(_runner._immediate) == _runner.IMMEDIATE_QUEUE_MAX
    assert _runner._immediate[-1] == f"payload-{_runner.IMMEDIATE_QUEUE_MAX + 4}"
    assert _runner._immediate[0] == f"payload-{5}"


def test_enqueue_immediate_does_not_raise_on_full_queue() -> None:
    import ingest.runner as _runner

    _runner._immediate.clear()

    for i in range(_runner.IMMEDIATE_QUEUE_MAX * 2):
        _runner._enqueue_immediate(str(i))

    _runner._immediate.clear()


# ---------------------------------------------------------------------------
# run_loop graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_loop_exits_when_shutdown_event_set() -> None:
    import ingest.runner as _runner

    async def _noop_run_once() -> None:
        return None

    async def _noop_listener() -> None:
        await _runner._shutdown.wait()

    with patch("ingest.runner._run_once", _noop_run_once), \
         patch("ingest.runner._listen_for_new_sources", _noop_listener), \
         patch("ingest.runner._install_signal_handlers", lambda _e: None):
        async def _stop_soon():
            await asyncio.sleep(0.05)
            _runner._shutdown.set()

        await asyncio.gather(_runner.run_loop(), _stop_soon())


# ---------------------------------------------------------------------------
# invalid notify payload — does not crash the inner loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listener_retries_on_connection_failure() -> None:
    import ingest.runner as _runner

    _runner._shutdown = asyncio.Event()
    attempts: list[int] = []

    async def _failing_connect(*_args, **_kwargs):
        attempts.append(1)
        raise ConnectionError("simulated db down")

    original_backoff = _runner.RECONNECT_BACKOFF_BASE
    _runner.RECONNECT_BACKOFF_BASE = 0.05

    try:
        with patch("ingest.runner.asyncpg.connect", _failing_connect):
            task = asyncio.create_task(_runner._listen_for_new_sources())
            await asyncio.sleep(0.3)
            _runner._shutdown.set()
            await asyncio.wait_for(task, timeout=2.0)
    finally:
        _runner.RECONNECT_BACKOFF_BASE = original_backoff

    assert len(attempts) >= 2


def test_install_signal_handlers_no_loop_does_not_raise() -> None:
    import ingest.runner as _runner

    event = asyncio.Event()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_install(event))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        pytest.fail(f"signal handler install raised: {exc}")


async def _async_install(event: asyncio.Event) -> None:
    import ingest.runner as _runner

    _runner._install_signal_handlers(event)


@pytest.mark.asyncio
async def test_run_loop_handles_invalid_uuid_payload() -> None:
    import ingest.runner as _runner

    fetch_calls: list = []

    async def _capture_fetch(source_id):
        fetch_calls.append(source_id)

    async def _noop_run_once() -> None:
        _runner._immediate.append("not-a-uuid")

    async def _noop_listener() -> None:
        await _runner._shutdown.wait()

    with patch("ingest.runner._run_once", _noop_run_once), \
         patch("ingest.runner._listen_for_new_sources", _noop_listener), \
         patch("ingest.runner._install_signal_handlers", lambda _e: None), \
         patch("ingest.runner._fetch_one_source", _capture_fetch):
        async def _stop_soon():
            await asyncio.sleep(0.2)
            _runner._shutdown.set()

        await asyncio.gather(_runner.run_loop(), _stop_soon())

    assert fetch_calls == []
