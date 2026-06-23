"""Tests for _compute_quadrant — 2×2 editorial matrix."""

import pytest
from scoring.pipeline import _compute_quadrant


@pytest.mark.parametrize(
    "high_demand,performance_level,expected",
    [
        # opportunity: high demand + no or low performance
        (True, "none", "opportunity"),
        (True, "low", "opportunity"),
        # winning: high demand + high performance
        (True, "high", "winning"),
        # evergreen: low demand + high performance
        (False, "high", "evergreen"),
        # ignore: low demand + no/low performance
        (False, "none", "ignore"),
        (False, "low", "ignore"),
        # too_early overrides demand axis
        (True, "too_early", "too_early"),
        (False, "too_early", "too_early"),
    ],
)
def test_quadrant_mapping(high_demand: bool, performance_level: str, expected: str) -> None:
    assert _compute_quadrant(high_demand, performance_level) == expected
