import sys
from pathlib import Path

import pytest

llm_src = Path(__file__).parent.parent / "src"
if str(llm_src) not in sys.path:
    sys.path.insert(0, str(llm_src))


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    """Override root conftest's database fixture — llm tests don't need a DB."""
    pass


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end() -> None:
    """Override root conftest's database cleanup fixture."""
    yield
