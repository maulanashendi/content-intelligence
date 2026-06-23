"""Tests for scoring.demand — classify_demand()."""

import pytest
from scoring.demand import _minmax, _percentile_cutoff, classify_demand
from scoring.pipeline import ClusterFacts


def _facts(
    trend_match: int = 0,
    weighted_trend_score: float = 0.0,
    count_24h: int = 0,
    count_7d: int = 0,
) -> ClusterFacts:
    f = ClusterFacts()
    f.trend_match_count = trend_match
    f.weighted_trend_score = weighted_trend_score
    f.count_24h = count_24h
    f.count_7d = count_7d
    return f


# ---------------------------------------------------------------------------
# Unit: helpers
# ---------------------------------------------------------------------------


def test_minmax_normal() -> None:
    assert _minmax([0.0, 5.0, 10.0]) == pytest.approx([0.0, 0.5, 1.0])


def test_minmax_all_same_nonzero_returns_ones() -> None:
    assert _minmax([3.0, 3.0, 3.0]) == [1.0, 1.0, 1.0]


def test_minmax_all_zero_returns_zeros() -> None:
    assert _minmax([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


def test_minmax_empty() -> None:
    assert _minmax([]) == []


def test_percentile_cutoff_66_of_three() -> None:
    # sorted [1,2,3], idx = round(0.66*3)=round(1.98)=2 → value=3
    assert _percentile_cutoff([1.0, 2.0, 3.0], 0.66) == pytest.approx(3.0)


def test_percentile_cutoff_empty() -> None:
    assert _percentile_cutoff([], 0.66) == 0.0


# ---------------------------------------------------------------------------
# classify_demand
# ---------------------------------------------------------------------------


def test_empty_facts_does_nothing() -> None:
    classify_demand({}, 0.66)  # no error


def test_single_cluster_with_signals_is_high_demand() -> None:
    from uuid import uuid4
    cid = uuid4()
    facts = {cid: _facts(trend_match=3, weighted_trend_score=80.0, count_24h=5, count_7d=10)}
    classify_demand(facts, 0.66)
    assert facts[cid].demand_score > 0.0
    assert facts[cid].high_demand is True


def test_single_cluster_no_signals_is_not_high_demand() -> None:
    from uuid import uuid4
    cid = uuid4()
    facts = {cid: _facts()}
    classify_demand(facts, 0.66)
    assert facts[cid].demand_score == 0.0
    assert facts[cid].high_demand is False


def test_top_third_classified_high_demand() -> None:
    """With 3 clusters and high_percentile=0.66, the top 1 should be high_demand."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(3)]
    facts = {
        ids[0]: _facts(trend_match=0, weighted_trend_score=0.0),
        ids[1]: _facts(trend_match=2, weighted_trend_score=50.0, count_24h=2, count_7d=10),
        ids[2]: _facts(trend_match=5, weighted_trend_score=200.0, count_24h=8, count_7d=10),
    }
    classify_demand(facts, 0.66)
    # ids[0] has no signal → not high
    assert facts[ids[0]].high_demand is False
    # ids[2] has most signal → high
    assert facts[ids[2]].high_demand is True


def test_demand_score_monotonic_in_trend_match() -> None:
    """Higher trend_match_count should produce higher demand_score (other things equal)."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(3)]
    facts = {
        ids[0]: _facts(trend_match=1),
        ids[1]: _facts(trend_match=3),
        ids[2]: _facts(trend_match=5),
    }
    classify_demand(facts, 0.66)
    scores = [facts[i].demand_score for i in ids]
    assert scores[0] <= scores[1] <= scores[2]


def test_zero_demand_cluster_never_high_even_if_at_cutoff() -> None:
    """A cluster with all-zero signals is never high_demand, even if it meets
    the percentile cutoff (e.g. when all clusters have zero demand)."""
    from uuid import uuid4
    ids = [uuid4() for _ in range(2)]
    facts = {ids[0]: _facts(), ids[1]: _facts()}
    classify_demand(facts, 0.0)  # even with p=0, score>0 guard applies
    assert all(not facts[i].high_demand for i in ids)
