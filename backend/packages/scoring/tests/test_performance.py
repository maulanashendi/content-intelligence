"""Tests for scoring.performance — classify_performance()."""

from scoring.performance import classify_performance
from scoring.pipeline import ClusterFacts


def _facts(
    tempo_covered: bool = False,
    gsc_impressions: int = 0,
    underperformed: bool = False,
) -> ClusterFacts:
    f = ClusterFacts()
    f.tempo_covered = tempo_covered
    f.gsc_impressions = gsc_impressions
    f.underperformed = underperformed
    return f


# ---------------------------------------------------------------------------
# none — not covered by Tempo
# ---------------------------------------------------------------------------


def test_uncovered_cluster_is_none() -> None:
    from uuid import uuid4
    cid = uuid4()
    facts = {cid: _facts(tempo_covered=False, gsc_impressions=500)}
    classify_performance(facts, 0.66)
    assert facts[cid].performance_level == "none"


# ---------------------------------------------------------------------------
# too_early — covered but no GSC data yet
# ---------------------------------------------------------------------------


def test_covered_no_gsc_is_too_early() -> None:
    from uuid import uuid4
    cid = uuid4()
    facts = {cid: _facts(tempo_covered=True, gsc_impressions=0)}
    classify_performance(facts, 0.66)
    assert facts[cid].performance_level == "too_early"


# ---------------------------------------------------------------------------
# underperformed → always low regardless of impressions
# ---------------------------------------------------------------------------


def test_underperformed_with_high_impressions_is_low() -> None:
    from uuid import uuid4
    cid = uuid4()
    facts = {cid: _facts(tempo_covered=True, gsc_impressions=10000, underperformed=True)}
    classify_performance(facts, 0.66)
    assert facts[cid].performance_level == "low"


# ---------------------------------------------------------------------------
# percentile classification
# ---------------------------------------------------------------------------


def test_top_third_is_high_performance() -> None:
    """With 3 covered clusters and p=0.66, the highest-impression one is high."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(3)]
    facts = {
        ids[0]: _facts(tempo_covered=True, gsc_impressions=100),
        ids[1]: _facts(tempo_covered=True, gsc_impressions=500),
        ids[2]: _facts(tempo_covered=True, gsc_impressions=5000),
    }
    classify_performance(facts, 0.66)
    assert facts[ids[2]].performance_level == "high"
    assert facts[ids[0]].performance_level == "low"
    assert facts[ids[1]].performance_level == "low"


def test_equal_impressions_all_high_when_cutoff_equals_value() -> None:
    """When all covered clusters have equal impressions, cutoff == value,
    all are >= cutoff → all high (if not underperformed)."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(3)]
    facts = {i: _facts(tempo_covered=True, gsc_impressions=200) for i in ids}
    classify_performance(facts, 0.66)
    for i in ids:
        assert facts[i].performance_level == "high"


def test_empty_facts_does_nothing() -> None:
    classify_performance({}, 0.66)  # no error


def test_no_covered_clusters_no_cutoff() -> None:
    """If no covered cluster has impressions, impression_cutoff=0 → all covered
    with gsc_impressions>0 would be 'high', but there are none here."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(2)]
    facts = {
        ids[0]: _facts(tempo_covered=False),
        ids[1]: _facts(tempo_covered=True, gsc_impressions=0),
    }
    classify_performance(facts, 0.66)
    assert facts[ids[0]].performance_level == "none"
    assert facts[ids[1]].performance_level == "too_early"


def test_mixed_covered_uncovered() -> None:
    from uuid import uuid4
    ids = [uuid4() for _ in range(4)]
    facts = {
        ids[0]: _facts(tempo_covered=False),                          # none
        ids[1]: _facts(tempo_covered=True, gsc_impressions=0),        # too_early
        ids[2]: _facts(tempo_covered=True, gsc_impressions=100),      # low (p=0.66 on [100,1000])
        ids[3]: _facts(tempo_covered=True, gsc_impressions=1000),     # high
    }
    classify_performance(facts, 0.66)
    assert facts[ids[0]].performance_level == "none"
    assert facts[ids[1]].performance_level == "too_early"
    assert facts[ids[3]].performance_level == "high"
    assert facts[ids[2]].performance_level == "low"
