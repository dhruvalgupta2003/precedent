"""Shared fixtures and safety rails for every test (ADR0008)."""

import os
import uuid
from collections.abc import Iterator

import pytest
from falkordb import FalkorDB, Graph
from pydantic_ai import models

from precedent.adapters.falkor import connect
from safety import safe_graph_name

# Any real LLM call inside a test raises RuntimeError. Tests use TestModel; model quality is an eval's job.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def anyio_backend() -> str:
    """Async tests run on asyncio, the loop uvicorn uses."""
    return "asyncio"


@pytest.fixture(scope="session")
def database(tmp_path_factory: pytest.TempPathFactory) -> FalkorDB:
    """The server at FALKORDB_URL, or with PRECEDENT_TEST_DB=embedded the built-in database (ADR0015)."""
    if os.environ.get("PRECEDENT_TEST_DB") == "embedded":
        return connect(None, tmp_path_factory.mktemp("db") / "test.db")
    return FalkorDB.from_url(os.environ.get("FALKORDB_URL", "redis://localhost:6380"))


@pytest.fixture
def graph(database: FalkorDB) -> Iterator[Graph]:
    """A fresh FalkorDB graph per test, deleted afterwards.

    Locally the test is skipped when FalkorDB is not running; in CI (CI=true) that is a failure.
    """
    db = database
    try:
        db.list_graphs()  # not PING: a plain Redis answers PING too, but only FalkorDB knows GRAPH.LIST
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"No FalkorDB: {exc}")
    # pid + random suffix: parallel workers and concurrent runs never share a graph
    test_graph = db.select_graph(safe_graph_name(f"test_{os.getpid()}_{uuid.uuid4().hex[:8]}"))
    yield test_graph
    if test_graph.name in db.list_graphs():
        test_graph.delete()
