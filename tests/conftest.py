"""Shared fixtures and safety rails for every test (ADR0008)."""

import os
import uuid
from collections.abc import Iterator

import pytest
from falkordb import FalkorDB, Graph
from pydantic_ai import models

from safety import safe_graph_name

# Any real LLM call inside a test raises RuntimeError. Tests use TestModel; model quality is an eval's job.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def anyio_backend() -> str:
    """Async tests run on asyncio, the loop uvicorn uses."""
    return "asyncio"


@pytest.fixture
def graph() -> Iterator[Graph]:
    """A fresh FalkorDB graph per test, deleted afterwards.

    Locally the test is skipped when FalkorDB is not running; in CI (CI=true) that is a failure.
    """
    url = os.environ.get("FALKORDB_URL", "redis://localhost:6380")
    try:
        db = FalkorDB.from_url(url)
        db.connection.ping()
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"FalkorDB not reachable at {url}: {exc}")
    # pid + random suffix: parallel workers and concurrent runs never share a graph
    test_graph = db.select_graph(safe_graph_name(f"test_{os.getpid()}_{uuid.uuid4().hex[:8]}"))
    yield test_graph
    if test_graph.name in db.list_graphs():
        test_graph.delete()
