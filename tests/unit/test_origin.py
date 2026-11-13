"""Where a decision was loaded from, and what one load owns (ADR0021).

Bugs this guards (security reviews of PRs #58 and #59): two repositories loaded into one org could make the same
decision id, and the one loaded last overwrote the other's status; and a deleted decision file kept its stances and
"replaces" links forever. The tests walk every shape of remote URL, every relation between an earlier decision and
this load, then random graphs of earlier loads.
"""

from itertools import product
from typing import NamedTuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.core.model import Origin
from precedent.core.origin import Earlier, Proof, Reach, clashes, covers, repo_name, retired, taken_without_origin

# ---------- 1. naming a repository from its remote URL ----------

HOSTS = [("github.com", "github.com"), ("GitHub.com", "github.com"), ("gitlab.example.com:8443", "gitlab.example.com")]
PATHS = [("acme/web", "acme/web"), ("Acme/Web", "acme/web"), ("group/sub/web", "group/sub/web")]
ENDINGS = ["", ".git", "/", ".git/"]
CREDENTIALS = ["", "git@", "alice@", "alice:s3cret@", "x-access-token:ghp_abcdef123456@", "oauth2:glpat-xyz@"]
AFTER = ["", "?private_token=abc123", "#readme"]  # a query string can carry a token too (design review of PR #60)
SECRETS = ("s3cret", "ghp_", "glpat", "alice", "private_token", "abc123", "@", ":", "?", "#")


def forms(host: str, path: str, ending: str, who: str) -> list[str]:
    """Every way git writes this remote: https, http, ssh, git, and scp-like (host:path, no port there)."""
    urls = [f"{scheme}://{who}{host}/{path}{ending}" for scheme in ("https", "http", "ssh", "git")]
    if ":" not in host:
        urls.append(f"{who or 'git@'}{host}:{path}{ending}")
    return urls


def test_every_form_of_a_remote_names_the_same_repository_and_never_keeps_a_credential():
    """3 hosts x 3 paths x 4 endings x 6 credentials x 3 tails, each in every form git writes (5 forms, or 4 for a
    host with a port): 3,024 URLs."""
    seen = 0
    for (host, want_host), (path, want_path), ending, who, after in product(HOSTS, PATHS, ENDINGS, CREDENTIALS, AFTER):
        for url in forms(host, path, ending + after, who):
            name = repo_name(url)
            assert name == f"{want_host}/{want_path}", url
            assert all(secret not in name for secret in SECRETS), url
            seen += 1
    assert seen == 3024


@pytest.mark.parametrize(
    "url",
    [
        "git@ssh.dev.azure.com:v3/acme/shop/web",
        "ssh://git@ssh.dev.azure.com/v3/acme/shop/web",
        "https://acme@dev.azure.com/acme/shop/_git/web",
        "https://dev.azure.com/acme/shop/_git/web",
    ],
)
def test_azure_devops_ssh_and_https_remotes_name_one_repository(url):
    """Azure DevOps writes the same repository two ways, so a laptop and CI would otherwise disagree."""
    assert repo_name(url) == "dev.azure.com/acme/shop/web"


@pytest.mark.parametrize(
    "url",
    [
        "/srv/git/web.git",
        "file:///srv/git/web.git",
        "../web",
        "./web.git",
        "C:\\repos\\web",
        "C:/repos/web",
        "git@github.com:.git",
        "https://github.com/acme/we@b",
        "c:/repos/web.git",
        "",
        "   ",
        "https://",
        "git@:",
    ],
)
def test_a_remote_that_is_a_path_on_this_machine_or_empty_names_no_repository(url):
    assert repo_name(url) is None


@pytest.mark.parametrize(
    "url",
    [
        "alice@devbox:/srv/alice/web.git",  # an absolute folder on the server
        "devbox:~/web.git",
        "ssh://devbox/~alice/web.git",
        "ssh://alice@devbox/HOME/alice/src/web.git",  # home folders, in any letter case
        "ssh://devbox/users/alice/web",
    ],
)
def test_a_remote_that_is_a_folder_in_someones_home_names_no_repository(url):
    """Security review of PR #60: the path would carry a person's user name into every decision and message."""
    assert repo_name(url) is None


@settings(max_examples=500)
@given(st.text())
def test_any_text_either_names_a_repository_without_a_credential_or_nothing(url):
    name = repo_name(url)
    assert name is None or (not any(c in name for c in "@:?#") and name == name.lower() and "/" in name)


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


@pytest.mark.parametrize(
    ("before", "taken"),
    [(Origin(repo=WEB, path=HERE), True), (None, False)],
    ids=["owned-by-a-repository", "no-origin"],
)
def test_a_load_with_no_origin_never_takes_an_id_a_repository_owns(before, taken):
    """Security review of PR #60: a folder outside git overwrote github.com/acme/web's ADR0007."""
    loaded = [("team/ADR0007", before), ("team/ADR0008", Origin(repo=WEB, path=HERE))]

    found = taken_without_origin(["team/ADR0007"], loaded)

    message = (
        "team/ADR0007 is already loaded from github.com/acme/web (docs/adr/0007-avoid-axios.md), and this load"
        " reads it from a folder outside a git repository with a name"
    )
    assert found == ([message] if taken else [])


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


def test_a_clash_message_spells_out_hidden_characters():
    """Security review of PR #60: a folder name with an escape sequence must not reach the terminal as is."""
    found = clashes(
        [("team/ADR0007", Origin(repo=WEB, path="docs\x1b[2Kadr/0007.md"))],
        [("team/ADR0007", Origin(repo=PAY, path="adr/0007.md"))],
        Reach(WEB, ""),
    )

    assert "\x1b" not in found[0]
    assert "'docs\\x1b[2Kadr/0007.md'" in found[0]


# ---------- 3. retiring only what this checkout can prove is gone ----------

PLACES = {  # where an earlier decision's file was, relative to a load of docs/adr/ in WEB
    "in-folder": Origin(repo=WEB, path="docs/adr/0042.md"),
    "other-folder": Origin(repo=WEB, path="services/adr/0042.md"),
    "other-repo": Origin(repo=PAY, path="docs/adr/0042.md"),
    "no-origin": None,
}
COMMITS = {"in-history": "c1", "not-in-history": "c9", "never-committed": None}
REACH = Reach(WEB, "docs/adr/")


class Case(NamedTuple):
    place: str
    read: bool
    missing: bool
    commit: str
    loaded: bool

    def name(self) -> str:
        flags = ("read" if self.read else "unread", "missing" if self.missing else "present", self.commit)
        return "-".join((self.place, *flags, "loaded" if self.loaded else "not-loaded"))


def should_retire(case: Case) -> bool:
    """ADR0021, written out: only a decision this load owns and didn't load, whose file it read again under another
    id, or whose file is missing here and was committed in this checkout's history."""
    owned = case.place == "in-folder" and not case.loaded
    return owned and (case.read or (case.missing and case.commit == "in-history"))


CASES = [Case(*c) for c in product(PLACES, (True, False), (True, False), COMMITS, (True, False))]


@pytest.mark.parametrize("case", CASES, ids=[c.name() for c in CASES])
def test_a_decision_is_retired_only_when_this_checkout_proves_its_file_is_gone(case):
    """4 places x read again x missing x 3 commits x loaded = 96 cases."""
    origin = PLACES[case.place]
    path = origin.path if origin else "docs/adr/0042.md"
    proof = Proof(
        read=frozenset({path} if case.read else ()),
        missing=frozenset({path} if case.missing else ()),
        history=frozenset({"c1"}),
    )
    kept = {"team/ADR0042"} if case.loaded else set()

    got = retired([Earlier("team/ADR0042", origin, COMMITS[case.commit])], kept, REACH, proof)

    assert got == (["team/ADR0042"] if should_retire(case) else [])


def test_the_latest_commit_a_file_was_seen_in_proves_a_deletion_too():
    """After a squash merge or a rebase, the first commit is in no branch any more; the latest one still is."""
    earlier = [Earlier("team/ADR0042", Origin(repo=WEB, path="docs/adr/0042.md"), "feature", "main-tip")]
    proof = Proof(frozenset(), frozenset({"docs/adr/0042.md"}), frozenset({"main-tip"}))

    assert retired(earlier, set(), REACH, proof) == ["team/ADR0042"]


def test_a_file_in_a_folder_the_load_skipped_is_not_proof_of_anything():
    """Security review of PR #60: `precedent load .` skips .github/; the file is still there, so nothing retires."""
    earlier = [Earlier("team/ADR0007", Origin(repo=WEB, path=".github/adr/0007.md"), "c1")]

    assert retired(earlier, set(), Reach(WEB, ""), Proof(frozenset(), frozenset(), frozenset({"c1"}))) == []


def test_an_older_branch_cant_prove_a_later_decision_was_deleted():
    earlier = [Earlier("team/ADR0007", Origin(repo=WEB, path="docs/adr/0007.md"), "later")]
    proof = Proof(frozenset(), frozenset({"docs/adr/0007.md"}), frozenset({"older"}))

    assert retired(earlier, set(), REACH, proof) == []


def test_a_file_read_again_under_a_new_id_retires_the_old_id():
    """After --source, or a second decision folder, the same file has a new id: the old one is retired and freed."""
    earlier = [Earlier("team/ADR0007", Origin(repo=WEB, path="docs/adr/0007.md"), None)]
    proof = Proof(frozenset({"docs/adr/0007.md"}), frozenset(), frozenset())

    assert retired(earlier, {"team/web/ADR0007"}, REACH, proof) == ["team/ADR0007"]


# ---------- 4. any history of earlier loads ----------

REPOS = [WEB, PAY]
FILES = ["docs/adr/0001.md", "docs/adr/0007.md", "docs/adr-old/0007.md", "services/adr/0007.md", "0007.md"]


@st.composite
def histories(draw: st.DrawFn) -> tuple[list[Earlier], list[tuple[str, Origin]], Reach, Proof]:
    """Decisions already in the graph, the decisions this load reads (all from its own folder), its reach, and what
    this checkout can prove."""
    ids = [f"team/ADR{n:04d}" for n in range(1, 6)]
    origins = st.none() | st.builds(Origin, repo=st.sampled_from(REPOS), path=st.sampled_from(FILES))
    earlier = draw(
        st.lists(
            st.builds(
                Earlier,
                st.sampled_from(ids),
                origins,
                st.sampled_from([None, "c1", "c2"]),
                st.sampled_from([None, "c2"]),
            ),
            unique_by=lambda e: e.decision,
            max_size=5,
        )
    )
    reach = Reach(draw(st.sampled_from(REPOS)), draw(st.sampled_from(["", "docs/adr/", "services/"])))
    mine = [f for f in FILES if f.startswith(reach.under)]
    loading = draw(
        st.lists(st.tuples(st.sampled_from(ids), st.sampled_from(mine)), unique_by=lambda e: e[0], max_size=4)
        if mine
        else st.just([])
    )
    proof = Proof(
        frozenset(p for _, p in loading),
        frozenset(draw(st.lists(st.sampled_from(FILES)))),
        frozenset(draw(st.lists(st.sampled_from(["c1", "c2"])))),
    )
    return earlier, [(i, Origin(repo=reach.repo, path=p)) for i, p in loading], reach, proof


@settings(max_examples=1000)
@given(histories())
def test_a_load_never_retires_or_takes_a_decision_it_doesnt_own(history):
    """Rules that hold whatever happened before, checked without re-stating how ownership is computed."""
    earlier, loading, reach, proof = history
    loaded_ids = {i for i, _ in loading}
    gone = set(retired(earlier, loaded_ids, reach, proof))
    refused = {m.split(" ", 1)[0] for m in clashes(loading, [(e.decision, e.origin) for e in earlier], reach)}
    where = {e.decision: e for e in earlier}

    assert gone.isdisjoint(loaded_ids)  # nothing this load reads is retired by it
    assert refused <= loaded_ids  # only ids this load wants can be refused
    for decision in gone:
        _, origin, commit, _ = where[decision]
        assert origin is not None  # a decision of unknown origin is never retired
        assert origin.repo == reach.repo  # never another repository's
        assert origin.path.startswith(reach.under)  # never outside the loaded folder
        commits = {commit, where[decision].last}
        assert origin.path in proof.read or (origin.path in proof.missing and commits & proof.history)  # proven
    for decision in refused:
        assert where[decision].origin is not None  # a decision of unknown origin is never refused
        assert where[decision].origin != dict(loading)[decision]  # the same file loading again is never refused
