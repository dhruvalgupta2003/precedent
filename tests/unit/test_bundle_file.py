"""The bundle saved on this computer (ADR0025): written whole or not at all, by one load at a time."""

import os
import threading
import time

import pytest

from precedent.adapters import bundle_file
from precedent.core.errors import LoadRunningError


def test_a_saved_bundle_reads_back_byte_for_byte(tmp_path):
    path = tmp_path / "bundles" / "team.json"

    bundle_file.write(path, b'{"one": 1}')

    assert bundle_file.read(path) == b'{"one": 1}'


def test_no_saved_bundle_reads_as_none(tmp_path):
    assert bundle_file.read(tmp_path / "team.json") is None


def test_a_saved_bundle_and_its_folder_are_only_the_owners_whatever_the_umask(tmp_path):
    path = tmp_path / "bundles" / "team.json"
    old = os.umask(0)
    try:
        bundle_file.write(path, b"{}")
    finally:
        os.umask(old)

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("step", ["fsync", "replace"])
def test_a_write_that_fails_half_way_leaves_the_old_bundle_whole(tmp_path, monkeypatch, step):
    path = tmp_path / "team.json"
    bundle_file.write(path, b"old")

    def fail(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(f"os.{step}", fail)
    with pytest.raises(OSError, match="disk full"):
        bundle_file.write(path, b"new, and much longer than the old one")

    assert bundle_file.read(path) == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["team.json"]  # no half-written file left behind


def test_a_second_load_waits_for_the_first_then_gives_up_with_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle_file, "LOCK_WAIT_S", 0.3)
    path = tmp_path / "team.json"
    holding, release = threading.Event(), threading.Event()

    def first() -> None:
        with bundle_file.locked(path):
            holding.set()
            release.wait(5)

    thread = threading.Thread(target=first)
    thread.start()
    holding.wait(5)
    started = time.monotonic()
    try:
        with pytest.raises(LoadRunningError, match="another load of org 'team' is running"), bundle_file.locked(path):
            pass  # pragma: no cover (never entered)
        assert time.monotonic() - started >= 0.3  # it waited before giving up
    finally:
        release.set()
        thread.join()

    with bundle_file.locked(path):  # free again once the first load ends
        pass
