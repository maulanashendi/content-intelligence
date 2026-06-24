import sys
from pathlib import Path

import pytest

analyst_src = Path(__file__).parent.parent / "src"
core_src = Path(__file__).parent.parent.parent / "core" / "src"
llm_src = Path(__file__).parent.parent.parent / "llm" / "src"

for p in (analyst_src, core_src, llm_src):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    """Override root conftest's database fixture — analyst tests don't need a DB."""
    pass


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end() -> None:
    """Override root conftest's database cleanup fixture."""
    yield
