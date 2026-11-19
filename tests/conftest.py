"""Shared pytest setup.

The API opens the SQLite database at import time, so point it at a throwaway
file before any test module imports ``api``.
"""

import os
import tempfile

import pytest


TEST_DB = os.path.join(
    tempfile.gettempdir(), f"dag_scheduler_test_{os.getpid()}.db")
os.environ["DAG_SCHEDULER_DB"] = TEST_DB
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)


@pytest.fixture(scope="session", autouse=True)
def _remove_test_db():
    yield
    try:
        os.remove(TEST_DB)
    except FileNotFoundError:
        pass
