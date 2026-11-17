"""Which Precedent saved a bundle (ADR0025): its rules were ranked by that version's code, so another one never
reads it. An install from git between releases must count as another version too."""

import pytest

from precedent import service


class Installed:
    """What `importlib.metadata` knows about an install: its version, and how it was installed."""

    version = "0.3.1"

    def __init__(self, record: str | None) -> None:
        self.record = record

    def read_text(self, name: str) -> str | None:
        return self.record if name == "direct_url.json" else None


FROM_GIT = '{"url": "https://github.com/acme/precedent", "vcs_info": {"vcs": "git", "commit_id": "e807616456c2917ae7"}}'
INSTALLS = {
    "from git": (FROM_GIT, "0.3.1+e807616456c2"),
    "editable": ('{"url": "file:///src/precedent", "dir_info": {"editable": true}}', "0.3.1"),
    "from an index": (None, "0.3.1"),  # no install record
}


@pytest.mark.parametrize(("record", "version"), INSTALLS.values(), ids=INSTALLS.keys())
def test_an_install_from_git_names_its_commit(monkeypatch, record, version):
    monkeypatch.setattr("precedent.service.metadata.distribution", lambda name: Installed(record))

    assert service.installed_version() == version
