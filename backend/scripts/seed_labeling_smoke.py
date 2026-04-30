"""
Seed minimal data for labeling smoke test.

Inserts:
  - 1 content_source (RSS)
  - 6 articles across 2 topics
  - 1 cluster_run
  - 2 article_cluster rows (is_current=true)
  - 6 article_cluster_member rows

Safe to re-run (ON CONFLICT DO NOTHING on unique columns).

Usage:
    cd backend
    uv run python scripts/seed_labeling_smoke.py
"""

import asyncio
import uuid

from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterAlgorithm,
    ClusterRun,
    ContentSource,
    SourceStatus,
    SourceType,
)
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

SOURCE_ID = uuid.UUID("00000000-0001-0000-0000-000000000000")
RUN_ID = uuid.UUID("00000000-0002-0000-0000-000000000000")
CLUSTER_1_ID = uuid.UUID("00000000-0003-0000-0000-000000000000")
CLUSTER_2_ID = uuid.UUID("00000000-0004-0000-0000-000000000000")

ARTICLES = [
    {
        "id": uuid.UUID("00000000-0010-0000-0000-000000000000"),
        "cluster_id": CLUSTER_1_ID,
        "relevance_score": 0.95,
        "title": "Harga Beras Premium Naik 20 Persen di Pasar Induk",
        "url": "https://seed.local/beras-naik-1",
        "first_paragraph": (
            "Harga beras premium di Pasar Induk Cipinang naik hingga 20 persen "
            "dalam sebulan terakhir akibat gangguan pasokan dari sentra produksi "
            "di Jawa Tengah dan cuaca ekstrem yang mempengaruhi panen."
        ),
    },
    {
        "id": uuid.UUID("00000000-0011-0000-0000-000000000000"),
        "cluster_id": CLUSTER_1_ID,
        "relevance_score": 0.88,
        "title": "Bulog Gelontorkan 50 Ribu Ton Beras Operasi Pasar",
        "url": "https://seed.local/beras-naik-2",
        "first_paragraph": (
            "Perum Bulog menyiapkan 50 ribu ton beras untuk operasi pasar "
            "guna menekan lonjakan harga yang terjadi di berbagai kota besar "
            "termasuk Jakarta, Surabaya, dan Medan."
        ),
    },
    {
        "id": uuid.UUID("00000000-0012-0000-0000-000000000000"),
        "cluster_id": CLUSTER_1_ID,
        "relevance_score": 0.81,
        "title": "Pedagang Warteg Keluhkan Kenaikan Harga Bahan Pokok",
        "url": "https://seed.local/beras-naik-3",
        "first_paragraph": (
            "Para pedagang warung makan di Jakarta mengaku kesulitan "
            "menghadapi kenaikan harga beras dan bahan pokok lainnya. "
            "Banyak yang terpaksa menaikkan harga jual atau mengurangi porsi."
        ),
    },
    {
        "id": uuid.UUID("00000000-0020-0000-0000-000000000000"),
        "cluster_id": CLUSTER_2_ID,
        "relevance_score": 0.92,
        "title": "Rupiah Melemah ke Level 16.400 per Dolar AS",
        "url": "https://seed.local/rupiah-1",
        "first_paragraph": (
            "Nilai tukar rupiah melemah ke level 16.400 per dolar AS pada "
            "perdagangan Rabu pagi, tertekan sentimen global akibat ekspektasi "
            "kebijakan suku bunga The Fed yang lebih hawkish dari perkiraan."
        ),
    },
    {
        "id": uuid.UUID("00000000-0021-0000-0000-000000000000"),
        "cluster_id": CLUSTER_2_ID,
        "relevance_score": 0.85,
        "title": "BI Intervensi Pasar untuk Jaga Stabilitas Rupiah",
        "url": "https://seed.local/rupiah-2",
        "first_paragraph": (
            "Bank Indonesia melakukan intervensi di pasar valuta asing dan "
            "pasar surat berharga negara untuk menjaga stabilitas nilai tukar "
            "rupiah yang sedang mengalami tekanan dari sentimen eksternal."
        ),
    },
    {
        "id": uuid.UUID("00000000-0022-0000-0000-000000000000"),
        "cluster_id": CLUSTER_2_ID,
        "relevance_score": 0.78,
        "title": "Eksportir Diimbau Repatriasi Devisa Hasil Ekspor",
        "url": "https://seed.local/rupiah-3",
        "first_paragraph": (
            "Pemerintah mengimbau para eksportir untuk segera merepatriasi "
            "devisa hasil ekspor guna membantu memperkuat pasokan dolar di "
            "dalam negeri di tengah tekanan pelemahan rupiah."
        ),
    },
]


async def seed() -> None:
    async with get_session() as session:
        # content_source
        await session.execute(
            pg_insert(ContentSource)
            .values(
                id=SOURCE_ID,
                name="[SEED] Detik Finance",
                url="https://seed.local/rss",
                source_type=SourceType.rss,
                status=SourceStatus.active,
            )
            .on_conflict_do_nothing(index_elements=["url"])
        )

        # articles
        for a in ARTICLES:
            await session.execute(
                pg_insert(Article)
                .values(
                    id=a["id"],
                    source_id=SOURCE_ID,
                    title=a["title"],
                    url=a["url"],
                    first_paragraph=a["first_paragraph"],
                )
                .on_conflict_do_nothing(index_elements=["url"])
            )

        # cluster_run
        await session.execute(
            pg_insert(ClusterRun)
            .values(
                id=RUN_ID,
                algorithm=ClusterAlgorithm.hdbscan,
                algorithm_version="0.1-seed",
                params={"min_cluster_size": 3},
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

        # article_cluster
        for cluster_id, label_placeholder, count in [
            (CLUSTER_1_ID, None, 3),
            (CLUSTER_2_ID, None, 3),
        ]:
            await session.execute(
                pg_insert(ArticleCluster)
                .values(
                    id=cluster_id,
                    run_id=RUN_ID,
                    label=label_placeholder,
                    member_count=count,
                    is_current=True,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

        # article_cluster_member
        for a in ARTICLES:
            await session.execute(
                text(
                    "INSERT INTO article_cluster_member (cluster_id, article_id, relevance_score) "
                    "VALUES (:cluster_id, :article_id, :relevance_score) "
                    "ON CONFLICT (cluster_id, article_id) DO NOTHING"
                ).bindparams(
                    cluster_id=a["cluster_id"],
                    article_id=a["id"],
                    relevance_score=a["relevance_score"],
                )
            )

        await session.commit()

    print("seed complete: 1 source, 6 articles, 1 run, 2 clusters, 6 members")
    print(f"  cluster 1 (pangan): {CLUSTER_1_ID}")
    print(f"  cluster 2 (rupiah): {CLUSTER_2_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
