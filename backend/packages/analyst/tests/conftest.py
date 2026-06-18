import sys
from pathlib import Path

import pytest

# Add the analyst package and core package to the path for imports
analyst_src = Path(__file__).parent.parent / "src"
core_src = Path(__file__).parent.parent.parent / "core" / "src"

if str(analyst_src) not in sys.path:
    sys.path.insert(0, str(analyst_src))
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    """Override root conftest's database fixture — analyst tests don't need a DB."""
    pass


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end() -> None:
    """Override root conftest's database cleanup fixture."""
    yield
