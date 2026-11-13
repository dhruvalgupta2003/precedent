"""Where a decision was loaded from, and what one load owns (ADR0021).

Bugs this guards (security reviews of PRs #58 and #59): two repositories loaded into one org could make the same
decision id, and the one loaded last overwrote the other's status; and a deleted decision file kept its stances and
"replaces" links forever. The tests walk every shape of remote URL, every relation between an earlier decision and
this load, then random graphs of earlier loads.
"""

from itertools import product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.core.model import Origin
from precedent.core.origin import Reach, clashes, covers, gone, repo_name

# ---------- 1. naming a repository from its remote URL ----------

HOSTS = [("github.com", "github.com"), ("GitHub.com", "github.com"), ("gitlab.example.com:8443", "gitlab.example.com")]
PATHS = [("acme/web", "acme/web"), ("Acme/Web", "acme/web"), ("group/sub/web", "group/sub/web")]
ENDINGS = ["", ".git", "/", ".git/"]
CREDENTIALS = ["", "git@", "alice@", "alice:s3cret@", "x-access-token:ghp_abcdef123456@", "oauth2:glpat-xyz@"]


def forms(host: str, path: str, ending: str, who: str) -> list[str]:
    """Every way git writes this remote: https, http, ssh, git, and scp-like (host:path, no port there)."""
    urls = [f"{scheme}://{who}{host}/{path}{ending}" for scheme in ("https", "http", "ssh", "git")]
    if ":" not in host:
        urls.append(f"{who or 'git@'}{host}:{path}{ending}")
    return urls


def test_every_form_of_a_remote_names_the_same_repository_and_never_keeps_a_credential():
    """3 hosts x 3 paths x 4 endings x 6 credentials, each in every form git writes: 1,152 URLs."""
    seen = 0
    for (host, want_host), (path, want_path), ending, who in product(HOSTS, PATHS, ENDINGS, CREDENTIALS):
        for url in forms(host, path, ending, who):
            name = repo_name(url)
            assert name == f"{want_host}/{want_path}", url
            assert all(secret not in name for secret in ("s3cret", "ghp_", "glpat", "alice", "@", ":")), url
            seen += 1
    assert seen > 1000


@pytest.mark.parametrize(
    "url",
    [
        "/srv/git/web.git",
        "file:///srv/git/web.git",
        "../web",
        "./web.git",
        "C:\\repos\\web",
        "",
        "   ",
        "https://",
        "git@:",
    ],
)
def test_a_remote_that_is_a_path_on_this_machine_or_empty_names_no_repository(url):
    assert repo_name(url) is None


@settings(max_examples=500)
@given(st.text())
def test_any_text_either_names_a_repository_without_a_credential_or_nothing(url):
    name = repo_name(url)
    assert name is None or ("@" not in name and ":" not in name and name == name.lower() and "/" in name)


# ---------- 2. what one load owns, and when it would take another's decision ----------

WEB, PAY = "github.com/acme/web", "github.com/acme/pay"
HERE = "docs/adr/0007-avoid-axios.md"
REACHES = {"whole-repo": Reach(WEB, ""), "adr-folder": Reach(WEB, "docs/adr/")}
# An earlier decision with the same id, by where its file was (or no origin: loaded before origins were kept).
EARLIER = {
    "no-origin": None,
    "same-file": Origin(repo=WEB, path=HERE),
    "renamed-in-folder": Origin(repo=WEB, path="docs/adr/0007-old-name.md"),
    "other-folder-same-repo": Origin(repo=WEB, path="services/pay/adr/0007-x.md"),
    "other-repo-same-path": Origin(repo=PAY, path=HERE),
    "other-repo-other-path": Origin(repo=PAY, path="adr/0007-x.md"),
}
# Whether this load would take the id from a file it doesn't own, for each reach.
CLASH = {
    ("no-origin", "whole-repo"): False,  # can't tell where it came from: it becomes this load's
    ("no-origin", "adr-folder"): False,
    ("same-file", "whole-repo"): False,
    ("same-file", "adr-folder"): False,
    ("renamed-in-folder", "whole-repo"): False,  # the old file is in this load's folder and gone: a rename
    ("renamed-in-folder", "adr-folder"): False,
    ("other-folder-same-repo", "whole-repo"): False,  # the whole repo is loaded, and that file isn't in it any more
    ("other-folder-same-repo", "adr-folder"): True,  # another folder of this repo, loaded on its own
    ("other-repo-same-path", "whole-repo"): True,
    ("other-repo-same-path", "adr-folder"): True,
    ("other-repo-other-path", "whole-repo"): True,
    ("other-repo-other-path", "adr-folder"): True,
}


@pytest.mark.parametrize(("earlier", "reach"), list(CLASH), ids=[f"{e}__{r}" for e, r in CLASH])
def test_a_load_takes_an_id_only_from_a_file_it_owns(earlier, reach):
    before = EARLIER[earlier]
    found = clashes([("team/ADR0007", Origin(repo=WEB, path=HERE))], [("team/ADR0007", before)], REACHES[reach])

    assert bool(found) == CLASH[(earlier, reach)]


def test_a_clash_says_where_both_files_are_and_what_to_do():
    found = clashes(
        [("team/ADR0007", Origin(repo=WEB, path=HERE))],
        [("team/ADR0007", Origin(repo=PAY, path="adr/0007-x.md"))],
        Reach(WEB, ""),
    )

    assert found == [
        "team/ADR0007 is already loaded from github.com/acme/pay (adr/0007-x.md), and this load reads it from "
        "github.com/acme/web (docs/adr/0007-avoid-axios.md)"
    ]


def test_different_ids_never_clash():
    assert (
        clashes(
            [("team/ADR0007", Origin(repo=WEB, path=HERE))],
            [("team/ADR0008", Origin(repo=PAY, path=HERE))],
            Reach(WEB, ""),
        )
        == []
    )


@pytest.mark.parametrize(
    ("path", "under", "owned"),
    [
        ("docs/adr/0007.md", "", True),
        ("docs/adr/0007.md", "docs/adr/", True),
        ("docs/adr/sub/0007.md", "docs/adr/", True),
        ("docs/adr-old/0007.md", "docs/adr/", False),  # a folder whose name starts the same is not inside
        ("docs/0007.md", "docs/adr/", False),
        ("services/pay/adr/0007.md", "docs/adr/", False),
    ],
)
def test_a_load_owns_exactly_the_files_under_its_folder_in_its_repository(path, under, owned):
    assert covers(Reach(WEB, under), Origin(repo=WEB, path=path)) is owned
    assert covers(Reach(PAY, under), Origin(repo=WEB, path=path)) is False  # never another repository's


def test_a_decision_with_no_origin_is_owned_by_no_load():
    assert covers(Reach(WEB, ""), None) is False


def test_a_decision_this_load_owns_but_did_not_load_is_gone():
    earlier = [
        ("team/ADR0007", Origin(repo=WEB, path="docs/adr/0007-a.md")),  # loaded again
        ("team/ADR0042", Origin(repo=WEB, path="docs/adr/0042-b.md")),  # file deleted
        ("team/ADR0050", Origin(repo=WEB, path="services/adr/0050.md")),  # outside this load's folder
        ("team/ADR0060", Origin(repo=PAY, path="docs/adr/0060.md")),  # another repository
        ("team/ADR0070", None),  # no origin
    ]

    assert gone(earlier, {"team/ADR0007"}, Reach(WEB, "docs/adr/")) == ["team/ADR0042"]


# ---------- 3. any history of earlier loads ----------

REPOS = [WEB, PAY]
FILES = ["docs/adr/0001.md", "docs/adr/0007.md", "docs/adr-old/0007.md", "services/adr/0007.md", "0007.md"]


@st.composite
def histories(draw: st.DrawFn) -> tuple[list[tuple[str, Origin | None]], list[tuple[str, Origin]], Reach]:
    """Decisions already in the graph, the decisions this load reads (all from its own folder), and its reach."""
    ids = [f"team/ADR{n:04d}" for n in range(1, 6)]
    origins = st.none() | st.builds(Origin, repo=st.sampled_from(REPOS), path=st.sampled_from(FILES))
    earlier = draw(st.lists(st.tuples(st.sampled_from(ids), origins), unique_by=lambda e: e[0], max_size=5))
    reach = Reach(draw(st.sampled_from(REPOS)), draw(st.sampled_from(["", "docs/adr/", "services/"])))
    mine = [f for f in FILES if f.startswith(reach.under)]
    loading = draw(
        st.lists(st.tuples(st.sampled_from(ids), st.sampled_from(mine)), unique_by=lambda e: e[0], max_size=4)
        if mine
        else st.just([])
    )
    return earlier, [(i, Origin(repo=reach.repo, path=p)) for i, p in loading], reach


@settings(max_examples=500)
@given(histories())
def test_a_load_never_retires_or_takes_a_decision_it_doesnt_own(history):
    earlier, loading, reach = history
    retired = gone(earlier, {i for i, _ in loading}, reach)
    refused = clashes(loading, earlier, reach)
    loaded_ids = {i for i, _ in loading}

    for decision, origin in earlier:
        owned = origin is not None and origin.repo == reach.repo and origin.path.startswith(reach.under)
        assert (decision in retired) == (owned and decision not in loaded_ids)
        takes = decision in loaded_ids and origin is not None and not owned and dict(loading)[decision] != origin
        assert any(m.startswith(f"{decision} ") for m in refused) == takes
