"""Pytest configuration to enable database access globally in all tests."""
import pytest


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):  # pylint: disable=unused-argument
    """Enable database access for all tests automatically."""
