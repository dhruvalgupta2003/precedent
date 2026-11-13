"""Decisions remember where they were loaded from (ADR0021), end to end with real git repositories and a real graph.

A load may refuse, but it retires a decision only when this checkout proves the decision's file was deleted: the
file is missing here, and the commit it was loaded at is in this checkout's history. Anything it can't prove keeps
counting, so a skipped folder or an older branch can never lift a block (security and design reviews of PR #60).
"""

import subprocess
from pathlib import Path

import pytest

from precedent import service
from precedent.adapters.falkor import rules, save_decision
from precedent.core.diff import Change
from precedent.core.errors import KnowledgeError
from precedent.core.model import DecisionRecord

pytestmark = pytest.mark.integration

ADDS_AXIOS = [Change("src/api.ts", ("import axios from 'axios';",))]
AVOID = "# 7. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse the built-in fetch.\n"
NOTE = "# {n}. A note\n\n## Status\n\nRejected\n\n## Decision\n\nNothing.\n"
REPLACE = (
    "# 42. Use axios\n\n## Status\n\nAccepted\n\nSupersedes [ADR0007](0007-avoid-axios.md)\n\n## Decision\n\nAxios.\n"
)
STANCES = {
    "ADR0007": "ADR0007: [{kind: package, value: axios, polarity: avoid, why: we use the built-in fetch}]\n",
    "ADR0042": "ADR0042: [{kind: package, value: axios, polarity: prefer, why: interceptors}]\n",
}
WEB, PAY = "https://github.com/acme/web.git", "git@github.com:acme/pay.git"


def git(root: Path, *args: str, check: bool = True) -> str:
    """Run git in a test repository (fixed arguments, no shell). Without `check`, a failure returns "failed"."""
    who = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    done = subprocess.run(["git", "-C", str(root), *who, *args], check=check, capture_output=True, text=True)  # noqa: S603, S607
    return done.stdout.strip() if done.returncode == 0 else "failed"


def repo(root: Path, remote: str | None = WEB) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    if remote:
        git(root, "remote", "add", "origin", remote)
    return root


def commit(root: Path) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", "decisions")
    return git(root, "rev-parse", "HEAD")


def note(n: int) -> str:
    return NOTE.format(n=n)


def decisions(folder: Path, files: dict[str, str]) -> None:
    """Exactly these decision files in the folder, with a precedent.yaml for the ones that have stances."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        old.unlink()
    for name, text in files.items():
        (folder / name).write_text(text)
    ids = {f"ADR{name[:4]}" for name, text in files.items() if text in (AVOID, REPLACE)}  # notes take no stance
    (folder / "precedent.yaml").write_text("".join(v for k, v in STANCES.items() if k in ids))


def verdict(graph) -> str:
    return service.preflight(graph, ADDS_AXIOS).verdict


def live(graph) -> set[str]:
    return {r.decision for r in rules(graph)}


# ---------- one id, one owner ----------


def test_two_repositories_with_one_number_cannot_overwrite_each_other(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": note(7), "0009-other.md": note(9)})
    service.ingest(graph, str(web), "team")
    assert verdict(graph) == "BLOCK"

    with pytest.raises(KnowledgeError) as error:
        service.ingest(graph, str(pay), "team")

    assert str(error.value).startswith(
        "team/ADR0007 is already loaded from github.com/acme/web (docs/adr/0007-avoid-axios.md), and this load reads "
        "it from github.com/acme/pay (docs/adr/0007-a-note.md)"
    )
    assert "load this folder with --source NAME" in str(error.value)
    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision {id: 'team/ADR0009'}) RETURN count(d)").result_set == [[0]]


def test_with_a_source_name_each_repository_keeps_its_own_ids(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": note(7)})
    service.ingest(graph, str(web), "team")

    service.ingest(graph, str(pay), "team/pay")

    assert verdict(graph) == "BLOCK"


def test_once_the_first_repository_moves_to_its_own_source_name_the_other_can_load(graph, tmp_path):
    """The old id was read again under a new name, so it is retired and freed (design review of PR #60)."""
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": note(7)})
    service.ingest(graph, str(web), "team")
    service.ingest(graph, str(web), "team/web")

    service.ingest(graph, str(pay), "team")

    assert live(graph) == {"team/web/ADR0007"}
    assert verdict(graph) == "BLOCK"


def test_two_folders_of_one_repository_loaded_separately_with_one_number_are_refused(graph, tmp_path):
    root = repo(tmp_path / "shop")
    decisions(root / "services" / "web" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(root / "services" / "pay" / "adr", {"0007-a-note.md": note(7)})
    service.ingest(graph, str(root / "services" / "web" / "adr"), "team")

    with pytest.raises(KnowledgeError, match="or load the folder that holds both"):
        service.ingest(graph, str(root / "services" / "pay" / "adr"), "team")

    assert verdict(graph) == "BLOCK"


def test_a_symlinked_decision_file_cannot_take_an_id_from_another_folder(graph, tmp_path):
    """Security review of PR #60: a link in another folder, pointing at the real file, took its id and its block.
    Its target is outside the folder being loaded, so it isn't read at all (security review of PR #59)."""
    root = repo(tmp_path / "shop")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root / "docs" / "adr"), "team")
    other = root / "services" / "pay" / "adr"
    other.mkdir(parents=True)
    (other / "0007-x.md").symlink_to(root / "docs" / "adr" / "0007-avoid-axios.md")
    (other / "0001-own.md").write_text(note(1))

    report = service.ingest(graph, str(other), "team/pay")

    assert report.written + report.unchanged == 1  # its own decision only, never the link
    assert verdict(graph) == "BLOCK"


# ---------- retiring only what this checkout proves was deleted ----------


def test_a_deleted_decision_file_stops_counting_and_is_kept_as_history(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-keep.md": note(1)})
    commit(root)
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "BLOCK"

    decisions(folder, {"0001-keep.md": note(1)})
    commit(root)
    report = service.ingest(graph, str(root), "team")

    assert verdict(graph) == "CLEAR"
    assert report.retired == 1
    assert graph.query(
        "MATCH (d:Decision {id: 'team/ADR0007'})-[a:APPLIES_TO]->() RETURN a.invalid_at IS NOT NULL"
    ).result_set == [[True]]


def test_a_deleted_replacement_brings_the_old_decision_back(graph, tmp_path):
    """Security review of PR #58: deleting the file that replaced ADR0007 left the replacement in force."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0042-use-axios.md": REPLACE})
    commit(root)
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "CLEAR"

    decisions(folder, {"0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_a_restored_file_counts_again(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(root)
    service.ingest(graph, str(root), "team")
    decisions(folder, {"0001-other.md": note(1)})
    commit(root)
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "CLEAR"

    decisions(folder, {"0001-other.md": note(1), "0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_renaming_a_decision_file_keeps_the_decision(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")

    decisions(folder, {"0007-no-axios.md": AVOID})
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision {id: 'team/ADR0007'}) RETURN d.path").result_set == [
        ["docs/adr/0007-no-axios.md"]
    ]


def test_a_folder_the_load_skips_keeps_its_decisions(graph, tmp_path):
    """Security review of PR #60: `precedent load .` skips hidden and build folders. Their decisions' files still
    exist, so they must not be retired."""
    root = repo(tmp_path / "web")
    decisions(root / ".github" / "adr", {"0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root / ".github" / "adr"), "team")
    assert verdict(graph) == "BLOCK"

    report = service.ingest(graph, str(root), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_load_from_an_older_branch_keeps_decisions_added_later(graph, tmp_path):
    """Security review of PR #60: a branch cut before ADR0007 existed doesn't prove ADR0007 was deleted."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0001-other.md": note(1)})
    old = commit(root)
    decisions(folder, {"0001-other.md": note(1), "0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")
    git(root, "checkout", "-q", old)

    report = service.ingest(graph, str(root), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_branch_that_deletes_the_file_retires_it(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0001-other.md": note(1), "0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")
    git(root, "checkout", "-q", "-b", "drop-axios-rule")
    decisions(folder, {"0001-other.md": note(1)})
    commit(root)

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "CLEAR"


def test_two_clones_of_one_repository_are_one_repository(graph, tmp_path):
    """A laptop (ssh remote) loads; CI (a clone, https remote) deletes the file in a later commit and loads."""
    laptop = repo(tmp_path / "laptop", "git@github.com:acme/web.git")
    decisions(laptop / "docs" / "adr", {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(laptop)
    service.ingest(graph, str(laptop), "team")
    ci = tmp_path / "ci"
    git(tmp_path, "clone", "-q", str(laptop), str(ci))
    git(ci, "remote", "set-url", "origin", "https://github.com/acme/web")
    decisions(ci / "docs" / "adr", {"0001-other.md": note(1)})
    commit(ci)

    service.ingest(graph, str(ci), "team")

    assert verdict(graph) == "CLEAR"


def test_a_checkout_that_cant_see_the_history_retires_nothing(graph, tmp_path):
    """A shallow or unrelated checkout with the same remote can't prove the file was deleted, so it stays."""
    first = repo(tmp_path / "first")
    decisions(first / "docs" / "adr", {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(first)
    service.ingest(graph, str(first), "team")
    other = repo(tmp_path / "other")
    decisions(other / "docs" / "adr", {"0001-other.md": note(1)})
    commit(other)

    report = service.ingest(graph, str(other), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_never_committed_decision_is_not_retired(graph, tmp_path):
    """A file loaded before it was ever committed has no commit to prove anything with, so it keeps counting."""
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    service.ingest(graph, str(root), "team")
    decisions(root / "docs" / "adr", {"0001-other.md": note(1)})
    commit(root)

    report = service.ingest(graph, str(root), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_deletion_not_yet_committed_retires_nothing(graph, tmp_path):
    """The file is still in the checked-out commit, so nothing proves the team deleted it yet."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(root)
    service.ingest(graph, str(root), "team")
    decisions(folder, {"0001-other.md": note(1)})

    report = service.ingest(graph, str(root), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_sparse_checkout_without_the_decision_folder_retires_nothing(graph, tmp_path):
    """Security review of PR #60: the files are in the commit but not on disk; that proves nothing was deleted."""
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    (root / "src").mkdir()
    (root / "src" / "notes.md").write_text("# Notes\n")
    commit(root)
    service.ingest(graph, str(root), "team")
    git(root, "sparse-checkout", "set", "src")
    assert not (root / "docs" / "adr" / "0007-avoid-axios.md").exists()

    report = service.ingest(graph, str(root), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")


def test_a_squash_merged_branch_can_still_prove_a_later_deletion(graph, tmp_path):
    """Security review of PR #60: the first commit a decision was loaded at is lost in a squash merge; the latest one
    a load saw it in still proves the deletion."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID})
    commit(root)
    main = git(root, "branch", "--show-current")
    git(root, "checkout", "-q", "-b", "use-axios")
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0042-use-axios.md": REPLACE})
    commit(root)
    service.ingest(graph, str(root), "team")  # first loaded on the branch
    git(root, "checkout", "-q", main)
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(root)  # main moves on meanwhile, so the squash commit is new
    git(root, "merge", "-q", "--squash", "use-axios")
    commit(root)
    assert git(root, "merge-base", "--is-ancestor", "use-axios", "HEAD", check=False) == "failed"
    service.ingest(graph, str(root), "team")  # loaded again on main after the squash
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(root)

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_a_load_run_from_a_git_hook_with_git_dir_set_still_knows_its_folder(graph, tmp_path, monkeypatch):
    """Security review of PR #60: hooks export GIT_DIR, which made git treat the loaded sub-folder as the top."""
    root = repo(tmp_path / "shop")
    decisions(root / "services" / "web" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(root / "docs" / "adr", {"0001-other.md": note(1)})
    commit(root)
    service.ingest(graph, str(root / "services" / "web" / "adr"), "team/web")
    monkeypatch.setenv("GIT_DIR", str(root / ".git"))

    report = service.ingest(graph, str(root / "docs" / "adr"), "team/docs")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")
    assert graph.query("MATCH (d:Decision {id: 'team/docs/ADR0001'}) RETURN d.path").result_set == [
        ["docs/adr/0001-other.md"]
    ]


def test_a_retirement_cut_short_heals_on_the_next_load(graph, tmp_path, monkeypatch):
    """Security review of PR #60: a crash between the steps must never leave a decision's stances off while its
    hash still says nothing changed."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})
    commit(root)
    service.ingest(graph, str(root), "team")
    decisions(folder, {"0001-other.md": note(1)})
    commit(root)
    real = graph.query
    calls = []

    def stop_after_two_steps(query: str, params: dict | None = None):
        if ("d.id IN $ids" in query and "$now" in query) or "SET d.hash = null" in query:
            calls.append(query)
            if len(calls) > 2:
                raise RuntimeError("the machine went down")
        return real(query, params)

    monkeypatch.setattr(graph, "query", stop_after_two_steps)
    with pytest.raises(RuntimeError):
        service.ingest(graph, str(root), "team")
    monkeypatch.setattr(graph, "query", real)
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-other.md": note(1)})  # the file comes back
    commit(root)

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_a_load_outside_a_named_repository_cannot_take_a_repositorys_id(graph, tmp_path):
    """Security review of PR #60: a folder with no repository name overwrote github.com/acme/web's ADR0007."""
    web = repo(tmp_path / "web")
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(web), "team")
    loose = tmp_path / "loose"
    decisions(loose, {"0007-a-note.md": note(7)})

    with pytest.raises(KnowledgeError, match=r"already loaded from github\.com/acme/web"):
        service.ingest(graph, str(loose), "team")

    assert verdict(graph) == "BLOCK"


def test_a_file_name_git_cant_spell_in_utf8_doesnt_crash_the_load(graph, tmp_path):
    """Security review of PR #60: a path that isn't UTF-8, in the commit but not on disk, crashed the load midway."""
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    commit(root)
    blob = git(root, "hash-object", "-w", str(root / "docs" / "adr" / "0007-avoid-axios.md"))
    subprocess.run(  # noqa: S603 (a test repository, fixed arguments)
        [  # noqa: S607
            "git",
            "-C",
            str(root),
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},".encode() + b"docs/adr/\xff.md",
        ],
        check=True,
        capture_output=True,
    )
    git(root, "commit", "-q", "-m", "a name that isn't UTF-8")  # not commit(): add -A would drop it again
    tree = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD"], capture_output=True, check=True)  # noqa: S603, S607
    assert b"\xff" in tree.stdout

    report = service.ingest(graph, str(root), "team")

    assert report.written + report.unchanged == 1
    assert verdict(graph) == "BLOCK"


def test_a_load_with_nothing_missing_asks_git_about_no_history(graph, tmp_path, monkeypatch):
    """Security review of PR #60: one history question per recorded commit on every load made reloads slow."""
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")
    asked = []
    monkeypatch.setattr("precedent.connectors.folder.in_history", lambda repo, c: asked.append(c) or True)

    service.ingest(graph, str(root), "team")

    assert asked == []


def test_a_deleted_symlinked_decision_file_stops_counting(graph, tmp_path):
    """The origin is the link's own path, so deleting the link retires the decision (design review of PR #60)."""
    root = repo(tmp_path / "web")
    shared = root / "shared"
    shared.mkdir()
    (shared / "avoid-axios.txt").write_text(AVOID)
    folder = root / "docs" / "adr"
    decisions(folder, {"0001-other.md": note(1)})
    (folder / "0007-avoid-axios.md").symlink_to(shared / "avoid-axios.txt")
    (folder / "precedent.yaml").write_text(STANCES["ADR0007"])
    commit(root)
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "BLOCK"

    (folder / "0007-avoid-axios.md").unlink()
    (folder / "precedent.yaml").write_text("")
    commit(root)
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "CLEAR"


def test_loading_one_folder_then_the_whole_repository_moves_the_ids_once(graph, tmp_path):
    """With a second decision folder, ids gain the folder's name; the old ids were read again, so they retire."""
    root = repo(tmp_path / "shop")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    commit(root)
    service.ingest(graph, str(root), "team")
    decisions(root / "services" / "pay" / "adr", {"0001-other.md": note(1)})
    commit(root)

    service.ingest(graph, str(root), "team")

    assert live(graph) == {"team/docs-adr/ADR0007"}
    assert verdict(graph) == "BLOCK"


def test_a_load_never_retires_another_repositorys_decisions(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0001-something.md": note(1)})
    commit(web)
    commit(pay)
    service.ingest(graph, str(web), "team")

    service.ingest(graph, str(pay), "team")

    assert verdict(graph) == "BLOCK"


# ---------- naming the repository ----------


def test_no_credential_from_a_remote_is_ever_stored(graph, tmp_path):
    root = repo(tmp_path / "web", "https://x-access-token:ghp_secret123@github.com/acme/web.git")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.repo").result_set == [["github.com/acme/web"]]
    assert "ghp_secret123" not in str(graph.query("MATCH (d:Decision) RETURN properties(d)").result_set)


def test_precedent_repo_names_a_repository_that_has_no_remote(graph, tmp_path, monkeypatch):
    """Normalised like a remote, so a CI variable that carries a token stores only the name (security review)."""
    monkeypatch.setenv("PRECEDENT_REPO", "https://gitlab-ci-token:glcbt-SECRET@gitlab.com/Acme/Web.git")
    root = repo(tmp_path / "web", None)
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.repo, d.path").result_set == [
        ["gitlab.com/acme/web", "docs/adr/0007-avoid-axios.md"]
    ]


def test_a_remote_wins_over_precedent_repo(graph, tmp_path, monkeypatch):
    """Security review of PR #60: a PRECEDENT_REPO left exported must not make every repository act as another."""
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0001-something.md": note(1)})
    commit(web)
    commit(pay)
    service.ingest(graph, str(web), "team")
    monkeypatch.setenv("PRECEDENT_REPO", "github.com/acme/web")

    service.ingest(graph, str(pay), "team")

    assert graph.query("MATCH (d:Decision {id: 'team/ADR0001'}) RETURN d.repo").result_set == [["github.com/acme/pay"]]
    assert verdict(graph) == "BLOCK"


def test_a_precedent_repo_that_names_no_repository_stops_the_load(graph, tmp_path, monkeypatch):
    monkeypatch.setenv("PRECEDENT_REPO", "not a repository")
    root = repo(tmp_path / "web", None)
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    with pytest.raises(KnowledgeError, match="PRECEDENT_REPO"):
        service.ingest(graph, str(root), "team")


def test_outside_a_named_repository_nothing_is_refused_or_retired(graph, tmp_path):
    """No repository name, no origin: a deleted file keeps counting (it fails closed), and two folders that happen to
    sit at one path on two machines can't retire each other (security review of PR #60)."""
    folder = tmp_path / "decisions"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-keep.md": note(1)})
    service.ingest(graph, str(folder), "team")
    decisions(folder, {"0001-keep.md": note(1)})

    report = service.ingest(graph, str(folder), "team")

    assert (report.retired, verdict(graph)) == (0, "BLOCK")
    assert graph.query("MATCH (d:Decision) WHERE d.repo IS NOT NULL RETURN count(d)").result_set == [[0]]


def test_a_relative_root_from_another_folder_and_a_symlinked_root_name_the_same_files(graph, tmp_path, monkeypatch):
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "link").symlink_to(root)
    monkeypatch.chdir(tmp_path / "elsewhere")

    service.ingest(graph, str(Path("..") / "web" / "docs" / "adr"), "team")
    service.ingest(graph, str(tmp_path / "link" / "docs" / "adr"), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.path").result_set == [["docs/adr/0007-avoid-axios.md"]]


def case_insensitive(folder: Path) -> bool:
    (folder / "CaseProbe").write_text("")
    return (folder / "caseprobe").exists()


def test_a_root_typed_in_another_letter_case_is_the_same_folder(graph, tmp_path):
    """Design review of PR #60: on macOS, docs/adr typed as Docs/ADR refused itself as a clash."""
    if not case_insensitive(tmp_path):
        pytest.skip("this disk tells letter case apart, so the other spelling is a different folder")
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root / "docs" / "adr"), "team")

    service.ingest(graph, str(tmp_path / "WEB" / "Docs" / "ADR"), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.path").result_set == [["docs/adr/0007-avoid-axios.md"]]


# ---------- what was there before ----------


def test_a_decision_loaded_before_origins_were_kept_becomes_this_loads(graph, tmp_path):
    record = {
        "id": "team/ADR0007",
        "org": "team",
        "title": "Avoid axios",
        "status": "accepted",
        "tier": "structured",
        "confirmed": True,
        "sources": [{"url": "old/0007.md", "kind": "adr"}],
    }
    save_decision(graph, DecisionRecord.model_validate(record))
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision) RETURN d.repo").result_set == [["github.com/acme/web"]]


def test_a_decision_found_in_a_document_is_never_retired_as_a_deleted_file(graph, tmp_path):
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0001-other.md": note(1)})
    (root / "README.md").write_text("# Web\n\nDecision: we do not use `axios`, we use the built-in fetch.\n")
    commit(root)
    service.ingest(graph, str(root), "team")
    found = live(graph)

    service.ingest(graph, str(root), "team")

    assert found
    assert live(graph) == found


def test_a_load_refused_for_taking_another_files_id_never_calls_the_ai(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", PAY)
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": note(7)})
    service.ingest(graph, str(web), "team")
    read = []

    with pytest.raises(KnowledgeError):
        service.ingest(graph, str(pay), "team", service.Readers(adrs=lambda text: read.append(text) or []))

    assert read == []
