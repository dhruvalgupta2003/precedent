"""Which database Precedent uses (ADR0015): a server when FALKORDB_URL is set, else the built-in one, else Docker."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from precedent.adapters import falkor
from precedent.adapters.falkor import connect

pytestmark = pytest.mark.integration


def test_a_url_always_means_that_server(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(falkor.FalkorDB, "from_url", lambda url: seen.append(url) or "server")

    assert connect("redis://db.internal:6379", tmp_path / "p.db") == "server"
    assert seen == ["redis://db.internal:6379"]
    assert not (tmp_path / "p.db").exists()  # the built-in database is never started when a server is named


def test_without_a_url_or_the_built_in_database_it_uses_the_local_server(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(falkor.FalkorDB, "from_url", lambda url: seen.append(url) or "server")
    monkeypatch.setitem(sys.modules, "redislite.falkordb_client", None)  # precedent[embedded] not installed

    assert connect(None, tmp_path / "p.db") == "server"
    assert seen == [falkor.DEFAULT_URL]


def test_without_a_url_the_built_in_database_keeps_its_data_in_one_file(tmp_path):
    path = tmp_path / "new-folder" / "precedent.db"

    connect(None, path).select_graph("test_connect").query("CREATE (:Decision {id: 'team/ADR1'})")
    rows = connect(None, path).select_graph("test_connect").query("MATCH (d:Decision) RETURN d.id").result_set

    assert rows == [["team/ADR1"]]  # the second connection reads what the first wrote
    assert path.parent.is_dir()


def _run(code: str) -> float:
    started = time.monotonic()
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603 (our own interpreter and code)
    return time.monotonic() - started


def test_a_short_process_on_the_built_in_database_saves_and_exits_quickly(tmp_path):
    """The hook is a new process on every edit, so stopping the database must not add seconds to each one."""
    db = str(tmp_path / "p.db")
    use = f"from pathlib import Path; from precedent.adapters.falkor import connect; g = connect(None, Path({db!r}))"
    use += ".select_graph('test_connect'); "
    _run(use + "g.query('RETURN 1')")  # the first run pays the one-time start-up

    took = _run(use + "g.query(\"CREATE (:Decision {id: 'team/ADR1'})\")")
    rows = connect(None, Path(db)).select_graph("test_connect").query("MATCH (d:Decision) RETURN d.id").result_set

    assert took < 2  # was ~4.3 s: the client retried with back-off after SHUTDOWN closed the socket
    assert rows == [["team/ADR1"]]  # and the write was saved before the process ended
