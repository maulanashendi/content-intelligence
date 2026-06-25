import logging
import time
import uuid
from datetime import UTC, datetime

import pytest
from core.config import settings
from core.db import get_session
from core.models import Article, ClusterInsight, ContentSource
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

GSC_FORBIDDEN_KEY_TOKENS = ("gsc", "impressions", "clicks", "position", "ctr")

ARTICLES_PER_CLUSTER = 6
NUM_CLUSTERS = 3


def _assert_no_gsc_keys(payload: object, where: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = key.lower()
            for forbidden in GSC_FORBIDDEN_KEY_TOKENS:
                assert forbidden not in lowered, f"GSC-flavored key '{key}' leaked at {where}"
            _assert_no_gsc_keys(value, where)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_gsc_keys(item, where)


@pytest.mark.asyncio
async def test_e2e_pipeline_and_api(
    rss_source: ContentSource,
    fake_embedder: object,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 18 samples vs default umap_target_dimensions=30 — UMAP needs n_samples > n_components.
    # Drop to 5 for the test only; clustering shape isn't sensitive at this scale.
    monkeypatch.setattr(settings, "umap_target_dimensions", 5)

    source_id = rss_source.id

    async def fake_ingest_rss(_client: object) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        async with get_session() as session:
            for cluster_idx in range(NUM_CLUSTERS):
                for member_idx in range(ARTICLES_PER_CLUSTER):
                    session.add(
                        Article(
                            id=uuid.uuid4(),
                            source_id=source_id,
                            title=f"{cluster_idx}|article {cluster_idx}-{member_idx}",
                            url=f"https://fake.example.com/{cluster_idx}/{member_idx}/{uuid.uuid4()}",
                            published_at=now,
                        )
                    )
            await session.commit()
        return NUM_CLUSTERS * ARTICLES_PER_CLUSTER

    async def fake_ingest_sitemap(_client: object) -> int:
        return 0

    async def fake_ingest_trends(_client: object) -> int:
        return 0

    monkeypatch.setattr("ingest.pipeline.ingest_rss", fake_ingest_rss)
    monkeypatch.setattr("ingest.pipeline.ingest_sitemap", fake_ingest_sitemap)
    monkeypatch.setattr("ingest.pipeline.ingest_trends", fake_ingest_trends)
    # get_embedder is lazily imported inside embedding.pipeline._encode_local (SP3),
    # so patch it at its source module, not on embedding.pipeline.
    monkeypatch.setattr("embedding.embedder.get_embedder", lambda: fake_embedder)

    async def fake_gsc_run(_session, _settings) -> None:
        return None

    import types
    fake_gsc_mod = types.ModuleType("gsc")
    fake_gsc_mod.run = fake_gsc_run  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "ingest.gsc", fake_gsc_mod)

    label_counter = {"n": 0}

    async def fake_label(_reps) -> dict[str, object]:
        label_counter["n"] += 1
        n = label_counter["n"]
        return {
            "label": f"Topic {n}",
            "what_happened": f"Apa terjadi {n}",
            "parties_involved": [f"Pihak {n}"],
            "editorial_angle": f"Sudut {n}",
            "summary": [f"Klaim {n}"],
        }

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake_label)

    from pipeline.cli import _run_daily

    caplog.set_level(logging.INFO)
    await _run_daily()

    finished = [r for r in caplog.records if r.getMessage() == "pipeline finished"]
    assert finished, "expected a 'pipeline finished' log record"
    elapsed = getattr(finished[-1], "total_elapsed_s", None)
    assert isinstance(elapsed, float), f"expected float total_elapsed_s, got {elapsed!r}"

    async with get_session() as session:
        insight_rows = list(
            (await session.execute(select(ClusterInsight))).scalars()
        )
    assert insight_rows, "scoring did not upsert any cluster_insight rows"
    assert all(
        row.trend_velocity is not None
        and isinstance(row.competitor_count, int)
        and isinstance(row.tempo_covered, bool)
        and isinstance(row.underperformed, bool)
        for row in insight_rows
    ), "cluster_insight rows missing expected raw-signal fields"

    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/api/v1/health", "/api/v1/clusters/morning", "/api/v1/clusters/deferred"):
            t0 = time.perf_counter()
            resp = await client.get(path)
            took = time.perf_counter() - t0
            assert resp.status_code == 200, f"{path} → {resp.status_code}: {resp.text}"
            assert took < 0.5, f"{path} took {took:.3f}s"
            _assert_no_gsc_keys(resp.json(), path)

        morning_resp = (await client.get("/api/v1/clusters/morning")).json()
        morning = morning_resp["clusters"]
        assert morning, "expected ≥1 cluster in /clusters/morning"
        cluster_id = morning[0]["id"]

        t0 = time.perf_counter()
        resp = await client.get(f"/api/v1/clusters/{cluster_id}")
        took = time.perf_counter() - t0
        assert resp.status_code == 200
        assert took < 0.5, f"/clusters/{{id}} took {took:.3f}s"
        _assert_no_gsc_keys(resp.json(), f"/clusters/{cluster_id}")
