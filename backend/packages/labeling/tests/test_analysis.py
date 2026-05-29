from labeling.analysis import run


async def test_run_returns_zero_counts():
    result = await run()
    assert result == {"analyzed": 0, "skipped": 0}
