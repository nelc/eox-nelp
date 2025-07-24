"""Pytest configuration to enable database access globally in all tests."""
import pathlib

import pytest


@pytest.fixture(autouse=True)
def conditional_db_access(request):
    """Enable DB access only for tests outside of integration folder."""
    test_path = pathlib.Path(str(request.node.fspath))

    if "tests/integration" not in str(test_path):
        # Import and activate the real db fixture only if not integration test
        request.getfixturevalue("db")
