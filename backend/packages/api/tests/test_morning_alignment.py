"""Cross-check test: every number on the /morning page is aligned.

Seed ONE ClusterRun with a deterministic mixed set of leaf clusters covering
every DNA classification: on-DNA (desk OK + need OK), off-DNA (bad desk),
off-DNA (denied need), off-DNA (NULL fields). Expected counts are DERIVED
from the seed list in Python — no hand-typed magic numbers.

Surface-under-test:
  /api/v1/clusters/morning?dna=<bool>
  /api/v1/clusters/quadrant-summary?dna=<bool>
  /api/v1/clusters/quadrant/{quadrant}?dna=<bool>&limit=50
  /api/v1/clusters/bento?dna=<bool>&limit=50
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from core.config import settings
from core.models import ArticleCluster, ClusterInsight, ClusterRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)

# ---------------------------------------------------------------------------
# Seed definition — derive expected counts from this list, no magic numbers
# ---------------------------------------------------------------------------

@dataclass
class _SeedCluster:
    desk: str | None
    need: str | None
    quadrant: str
    tempo_covered: bool
    # demand_score kept distinct so ordering is deterministic
    demand_score: float


# fmt: off
_SEED = [
    # 3 Politik / Update me / opportunity / uncovered  →  DNA-pass
    _SeedCluster("Politik",          "Update me",  "opportunity", False, 0.91),
    _SeedCluster("Politik",          "Update me",  "opportunity", False, 0.90),
    _SeedCluster("Politik",          "Update me",  "opportunity", False, 0.89),
    # 2 Hukum / Educate me / winning / covered  →  DNA-pass
    _SeedCluster("Hukum",            "Educate me", "winning",     True,  0.80),
    _SeedCluster("Hukum",            "Educate me", "winning",     True,  0.79),
    # 1 Nasional / Update me / evergreen / covered  →  DNA-pass
    _SeedCluster("Nasional",         "Update me",  "evergreen",   True,  0.70),
    # 1 Ekonomi & Bisnis / Update me / ignore / covered  →  DNA-pass
    _SeedCluster("Ekonomi & Bisnis", "Update me",  "ignore",      True,  0.60),
    # 2 Selebriti / Update me / opportunity / uncovered  →  DNA-FAIL (off-desk)
    _SeedCluster("Selebriti",        "Update me",  "opportunity", False, 0.50),
    _SeedCluster("Selebriti",        "Update me",  "opportunity", False, 0.49),
    # 1 Politik / Divert me / opportunity / uncovered  →  DNA-FAIL (denied need)
    _SeedCluster("Politik",          "Divert me",  "opportunity", False, 0.40),
    # 1 NULL / NULL / opportunity / uncovered  →  DNA-FAIL (null)
    _SeedCluster(None,               None,         "opportunity", False, 0.30),
    # 2 too_early clusters: one DNA-pass, one DNA-FAIL (off-desk)
    _SeedCluster("Politik",          "Update me",  "too_early",   True,  0.20),
    _SeedCluster("Selebriti",        "Update me",  "too_early",   True,  0.19),
]
# fmt: on

_ALLOWED_DESKS = set(settings.morning_allowed_desks)
_DENIED_NEEDS = set(settings.morning_denied_user_needs)


def _passes_dna(c: _SeedCluster) -> bool:
    return (
        c.desk is not None
        and c.need is not None
        and c.desk in _ALLOWED_DESKS
        and c.need not in _DENIED_NEEDS
    )


_DNA_PASS = [c for c in _SEED if _passes_dna(c)]
_EXPECTED_DNA_TOTAL = len(_DNA_PASS)
_EXPECTED_ALL_TOTAL = len(_SEED)

# morning = uncovered AND (passes DNA when dna=true)
_MORNING_DNA_TRUE = [c for c in _DNA_PASS if not c.tempo_covered]
_MORNING_DNA_FALSE = [c for c in _SEED if not c.tempo_covered]

# Sanity: the fixture must include off-DNA clusters so dna=true totals are
# strictly smaller than dna=false totals.
assert _EXPECTED_DNA_TOTAL < _EXPECTED_ALL_TOTAL, "seed must include off-DNA clusters"
assert len(_MORNING_DNA_TRUE) < len(_MORNING_DNA_FALSE), "seed must have off-DNA uncovered clusters"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[str, list[uuid.UUID]]:
    """Seed the mixed cluster set; return id lists keyed by 'all' and 'dna'."""
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    objects: list = [run]

    all_ids: list[uuid.UUID] = []
    dna_ids: list[uuid.UUID] = []

    for sc in _SEED:
        cluster = ArticleCluster(
            id=uuid.uuid4(),
            run_id=run.id,
            label=f"Test {sc.desk} {sc.quadrant}",
            is_current=True,
            member_count=1,
        )
        insight = ClusterInsight(
            id=uuid.uuid4(),
            cluster_id=cluster.id,
            trend_velocity=0.5,
            competitor_count=2,
            trend_match_count=1,
            tempo_covered=sc.tempo_covered,
            editorial_quadrant=sc.quadrant,
            demand_score=sc.demand_score,
            gsc_clicks=0,
            desk_category=sc.desk,
            user_need_category=sc.need,
        )
        objects += [cluster, insight]
        all_ids.append(cluster.id)
        if _passes_dna(sc):
            dna_ids.append(cluster.id)

    session.add_all(objects)
    await session.flush()
    return {"all": all_ids, "dna": dna_ids}


# ---------------------------------------------------------------------------
# Helper: fetch all four endpoints for a given dna mode
# ---------------------------------------------------------------------------


async def _fetch_all(client: AsyncClient, dna: bool) -> dict:
    dna_str = "true" if dna else "false"

    morning_resp = await client.get(f"/api/v1/clusters/morning?dna={dna_str}")
    assert morning_resp.status_code == 200, f"morning?dna={dna_str} returned {morning_resp.status_code}"

    summary_resp = await client.get(f"/api/v1/clusters/quadrant-summary?dna={dna_str}")
    assert summary_resp.status_code == 200, f"quadrant-summary?dna={dna_str} returned {summary_resp.status_code}"

    bento_resp = await client.get(f"/api/v1/clusters/bento?dna={dna_str}&limit=50")
    assert bento_resp.status_code == 200, f"bento?dna={dna_str} returned {bento_resp.status_code}"

    morning_data = morning_resp.json()
    summary_data = summary_resp.json()
    bento_data = bento_resp.json()

    # Fetch distinct quadrant endpoints for quadrants that have members.
    quadrant_ids: dict[str, list[str]] = {}
    for q in ("opportunity", "winning", "evergreen", "ignore", "too_early"):
        q_resp = await client.get(f"/api/v1/clusters/quadrant/{q}?dna={dna_str}&limit=50")
        assert q_resp.status_code == 200, f"quadrant/{q}?dna={dna_str} returned {q_resp.status_code}"
        quadrant_ids[q] = [c["id"] for c in q_resp.json()["clusters"]]

    return {
        "morning_ids": [c["id"] for c in morning_data["clusters"]],
        "morning_clusters": morning_data["clusters"],
        "summary": summary_data,
        "bento_ids": [c["id"] for c in bento_data["cards"]],
        "bento_total": bento_data["total"],
        "quadrant_ids": quadrant_ids,
    }


# ---------------------------------------------------------------------------
# Main alignment test
# ---------------------------------------------------------------------------


async def test_morning_alignment(
    seeded: dict[str, list[uuid.UUID]], client: AsyncClient
) -> None:
    """All four /morning-page surfaces return consistent counts across dna modes."""

    all_id_strs = {str(i) for i in seeded["all"]}
    dna_id_strs = {str(i) for i in seeded["dna"]}

    for dna in (True, False):
        label = f"dna={'true' if dna else 'false'}"
        d = await _fetch_all(client, dna=dna)

        summary = d["summary"]
        morning_id_set = set(d["morning_ids"])
        bento_id_set = set(d["bento_ids"])

        # -- Invariant 1: quadrant_summary.total == bento.total ----------------
        assert summary["total"] == d["bento_total"], (
            f"[{label}] quadrant-summary.total ({summary['total']}) != "
            f"bento.total ({d['bento_total']}) — same leaf-cluster universe must agree"
        )

        # -- Invariant 2: quadrant cells sum to total --------------------------
        cell_sum = (
            summary["opportunity"]
            + summary["winning"]
            + summary["evergreen"]
            + summary["ignore"]
            + summary["too_early"]
        )
        assert cell_sum == summary["total"], (
            f"[{label}] quadrant cells sum ({cell_sum}) != quadrant-summary.total "
            f"({summary['total']}) — missing or double-counted quadrant bucket"
        )

        # -- Invariant 3: morning ⊆ bento AND every morning cluster uncovered --
        assert morning_id_set <= bento_id_set, (
            f"[{label}] morning ids not a subset of bento ids — "
            f"extra ids: {morning_id_set - bento_id_set}"
        )
        for c in d["morning_clusters"]:
            assert c["tempo_covered"] is False, (
                f"[{label}] cluster {c['id']} appeared in /morning but tempo_covered is not False"
            )

        # -- Invariant 4: every quadrant/{q} id is in bento id set ------------
        quadrants_with_members = [
            q for q, ids in d["quadrant_ids"].items() if ids
        ]
        # We must have at least 2 distinct non-empty quadrants for this check to be meaningful.
        assert len(quadrants_with_members) >= 2, (
            f"[{label}] fewer than 2 quadrants returned data — seed may be wrong"
        )
        for q, ids in d["quadrant_ids"].items():
            extra = set(ids) - bento_id_set
            assert not extra, (
                f"[{label}] /quadrant/{q} returned ids not in bento: {extra}"
            )

    # -- Cross-mode invariant 5: correct absolute totals ----------------------
    d_true = await _fetch_all(client, dna=True)
    d_false = await _fetch_all(client, dna=False)

    assert d_true["summary"]["total"] == _EXPECTED_DNA_TOTAL, (
        f"quadrant-summary.total(dna=true) == {d_true['summary']['total']}, "
        f"expected {_EXPECTED_DNA_TOTAL} (derived from seed)"
    )
    assert d_false["summary"]["total"] == _EXPECTED_ALL_TOTAL, (
        f"quadrant-summary.total(dna=false) == {d_false['summary']['total']}, "
        f"expected {_EXPECTED_ALL_TOTAL} (derived from seed)"
    )

    # -- Cross-mode invariant 6: dna=true total strictly < dna=false total ----
    assert d_true["bento_total"] == _EXPECTED_DNA_TOTAL, (
        f"bento.total(dna=true) == {d_true['bento_total']}, "
        f"expected {_EXPECTED_DNA_TOTAL}"
    )
    assert d_false["bento_total"] == _EXPECTED_ALL_TOTAL, (
        f"bento.total(dna=false) == {d_false['bento_total']}, "
        f"expected {_EXPECTED_ALL_TOTAL}"
    )
    assert d_true["bento_total"] < d_false["bento_total"], (
        f"bento.total(dna=true) ({d_true['bento_total']}) must be strictly less than "
        f"bento.total(dna=false) ({d_false['bento_total']})"
    )

    # -- Cross-mode invariant 7: every morning?dna=true id is in DNA-pass set -
    for cid in d_true["morning_ids"]:
        assert cid in dna_id_strs, (
            f"cluster {cid} appeared in morning?dna=true but its desk/need fail the DNA gate"
        )
