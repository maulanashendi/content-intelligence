from pipeline.cli import _STEP_RUNNERS, cli


def test_reembed_command_registered():
    assert "reembed" in cli.commands


def test_reembed_not_in_daily_runners():
    # run-daily iterates _STEP_RUNNERS; reembed must never auto-run
    assert "reembed" not in _STEP_RUNNERS
