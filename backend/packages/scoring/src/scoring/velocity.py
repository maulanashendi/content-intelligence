def compute_trend_velocity(count_24h: int, count_7d: int) -> float:
    """Ratio of articles published in the last 24h vs the last 7d.

    Range [0, 1]. Returns 0.0 when count_7d is 0 (empty cluster window).
    """
    if count_7d == 0:
        return 0.0
    return round(min(count_24h / count_7d, 1.0), 4)
