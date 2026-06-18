import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    """Override root conftest's database fixture — analyst routes use no DB."""
    pass


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end() -> None:
    """Override root conftest's database cleanup fixture."""
    yield
