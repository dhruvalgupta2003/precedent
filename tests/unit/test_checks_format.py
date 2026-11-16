"""The checks format (docs/design/production-architecture.md \u00a74, phase 1a): checks, promotions, skip lists, globs.

A check always warns; only a promotion (a frozen snapshot of a check) can block. Every field is validated, and any
problem stops the whole load with the file, the check and the field named (as ADR0020): nothing partial is kept,
and nothing unknown is silently ignored, because a typo like `polartiy` must never drop a stance. Security and
design reviews of the first version added the hostile-input, glob and v0.3-equivalence cases.
"""

import os
import time
from datetime import date
from fnmatch import fnmatchcase

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.connectors.adr import _knowledge  # today's precedent.yaml reader: the reference for v0.3
from precedent.connectors.checks_file import legacy_checks, local_promotions, read_checks, read_promotions
from precedent.connectors.yamlfile import read
from precedent.core.checks import Check, Home, contains, entry_ok, glob_ok, matches
from precedent.core.errors import KnowledgeError

REPO = Home(repo="shop")
ORG = Home()
NAME = "precedent/checks.yaml"
NOTE = (
    "# 42. Payments\n\n## Decision\n\nNo service other than payments-api imports `@acme/payments-db`.\n\n"
    "Services talk to each other over HTTP.\n\nOld scripts still import `@\u0430cme/payments-db`.\n"
)
NOTES = {"ADR0042": NOTE}
GOOD = """\
ADR0042:
  - id: payments-db-only-in-api
    engine: package
    value: "@acme/payments-db"
    polarity: avoid
    where: ["services/**"]
    except: ["services/payments-api/**"]
    why: services reach payments only through payments-api
"""


def checks(text: str, home: Home = REPO) -> tuple[Check, ...]:
    return read_checks(text.encode(), NAME, home, NOTES).checks


def test_a_check_reads_with_every_field():
    [check] = checks(GOOD)

    assert check.model_dump(by_alias=True) == {
        "id": "payments-db-only-in-api",
        "decision": "ADR0042",
        "engine": "package",
        "value": "@acme/payments-db",
        "range": None,
        "polarity": "avoid",
        "where": ("services/**",),
        "except": ("services/payments-api/**",),
        "why": "services reach payments only through payments-api",
        "quote": None,
        "home": {"repo": "shop", "path": ""},
    }


def test_where_defaults_to_the_whole_home_and_lists_are_sorted_without_repeats():
    text = GOOD.replace('    where: ["services/**"]\n', "").replace(
        '["services/payments-api/**"]', '["b/**", "a/**", "b/**"]'
    )

    [check] = checks(text)

    assert (check.where, check.except_) == (("**",), ("a/**", "b/**"))


ENTRY = {
    "id": "payments-db-only-in-api",
    "engine": "package",
    "value": '"@acme/payments-db"',
    "polarity": "avoid",
    "why": "a reason",
}


def entry(**changes: str | None) -> str:
    fields = {**ENTRY, **changes}
    lines = "".join(f"    {k}: {v}\n" for k, v in fields.items() if v is not None)
    return "ADR0042:\n  -" + lines[3:]


REFUSED = {
    "no id": (entry(id=None), ": id: "),
    "id with capitals": (entry(id="PaymentsDb"), ": id: "),
    "id too long": (entry(id="a" * 65), ": id: "),
    "no engine": (entry(engine=None), ": engine: "),
    "unknown engine": (entry(engine="regex"), ": engine: "),
    "engine not built yet": (entry(engine="semgrep"), "isn't available yet"),
    "no value": (entry(value=None), ": value: "),
    "value not code": (entry(value='"use the payments api"'), "doesn't look like a package"),
    "value read as a boolean": (entry(value="no"), ": value: "),
    "unknown polarity": (entry(polarity="forbid"), ": polarity: "),
    "unknown field": (entry(polartiy="avoid"), "unknown field polartiy"),
    "no why or quote": (entry(why=None), "why or quote"),
    "why read as a date": (entry(why="2026-12-01"), ": why: "),
    "range on a package": (entry(range='">=18"'), "range is for version checks"),
    "version without a range": (entry(engine="version", value="react"), "range is for version checks"),
    "empty where": (entry(where="[]"), "where can't be empty"),
    "where not a list": (entry(where='"services/**"'), "expected a list of paths"),
    "where leaves the home": (entry(where='["../other/**"]'), "inside this home"),
    "absolute where": (entry(where='["/etc/**"]'), "inside this home"),
    "backslash where": (entry(where='["services\\\\x"]'), "inside this home"),
    "empty glob": (entry(where='[""]'), "inside this home"),
    "dot segment": (entry(where='["./services/**"]'), "inside this home"),
    "trailing slash": (entry(where='["services/"]'), "inside this home"),
    "repo prefix outside the org home": (entry(where='["shop:services/**"]'), "inside this home"),
    "tag with a bad name": (entry(where='["tag:Not A Tag"]'), "inside this home"),
    "except leaves the home": (entry(**{"except": '["../x"]'}), "inside this home"),
    "unknown decision": (entry().replace("ADR0042", "ADR0099"), "no decision ADR0099"),
    "entry not a mapping": ("ADR0042:\n  - just text\n", "ADR0042: expected a list of checks"),
    "decision not a list": ("ADR0042: {id: x}\n", "ADR0042: expected a list of checks"),
}


@pytest.mark.parametrize(("text", "named"), REFUSED.values(), ids=REFUSED.keys())
def test_every_mistake_stops_the_load_and_names_where_it_is(text, named):
    with pytest.raises(KnowledgeError) as refused:
        checks(text)

    assert named in str(refused.value)
    assert str(refused.value).startswith(NAME)


def test_the_org_home_also_takes_repo_prefixed_paths_and_tags():
    text = entry(where='["shop:services/**", "tag:services", "**"]')

    assert checks(text, home=ORG)[0].where == ("**", "shop:services/**", "tag:services")


def test_the_same_id_twice_in_one_file_is_refused():
    with pytest.raises(KnowledgeError, match="payments-db-only-in-api appears twice"):
        checks(GOOD + GOOD.replace("ADR0042:\n", ""))


QUOTES = {
    "in the note and names the value": ("No service other than payments-api imports `@acme/payments-db`.", True),
    "not in the note": ("We never import the payments database.", False),
    "in the note but names something else": ("Services talk to each other over HTTP.", False),
    # The note shows the look-alike letter to its reviewer, and the quote must match the note exactly.
    "names it through a look-alike letter": ("Old scripts still import `@\u0430cme/payments-db`.", True),
}


@pytest.mark.parametrize(("quote", "kept"), QUOTES.values(), ids=QUOTES.keys())
def test_a_quote_must_be_in_the_note_word_for_word_and_name_the_value(quote, kept):
    text = entry(why=None, quote=f'"{quote}"')

    if kept:
        assert checks(text)[0].quote == quote
    else:
        with pytest.raises(KnowledgeError, match="quote must be in ADR0042"):
            checks(text)


def test_a_version_check_reads_its_range():
    [check] = checks(entry(engine="version", value="react", range='">=18"'))

    assert (check.engine, check.value, check.range) == ("version", "react", ">=18")


def test_a_skip_list_reads_beside_the_checks():
    loaded = read_checks((GOOD + 'skip: ["**/generated/**", "vendor/**"]\n').encode(), NAME, REPO, NOTES)

    assert loaded.skip == ("**/generated/**", "vendor/**")


SKIPS = {
    "leaves home": '["../x/**"]',
    "absolute": '["/abs"]',
    "empty": '[""]',
    "not a list": '"not a list"',
    "everything": '["**"]',
    "precedent folder": '["precedent/**"]',
    "exceptions": '["precedent/exceptions.yaml"]',
    "nested precedent folder": '["**/precedent/**"]',
    "github folder": '[".github/**"]',
    "codeowners": '["CODEOWNERS"]',
    "docs codeowners": '["docs/CODEOWNERS"]',
}


@pytest.mark.parametrize("skip", SKIPS.values(), ids=SKIPS.keys())
def test_a_skip_list_can_never_leave_its_home_or_hide_governance_files(skip):
    with pytest.raises(KnowledgeError, match="skip"):
        read_checks((GOOD + f"skip: {skip}\n").encode(), NAME, REPO, NOTES)


def test_an_empty_checks_file_has_no_checks():
    assert read_checks(b"", NAME, REPO, NOTES) == ((), ())


# ---------- hostile YAML ----------

HAZARDS = {
    "alias": ("base: &x [a, b]\nADR0042: *x\n", "aliases"),
    "duplicate key": (GOOD + GOOD, "written twice"),
    "not a mapping": ("- a\n- b\n", "top level"),
    "merge key": ("<<: {ADR0042: [x]}\nADR0042: []\n", "merge keys"),
    "keys that collapse": ("on: 1\ntrue: 2\n", "keys must be text"),
    "null key": ("~: 1\n", "keys must be text"),
    "number key": ("42: [x]\n", "keys must be text"),
    "deep list": ("[" * 20000 + "]" * 20000, "nested too deeply"),
    "deep mapping": ("{b: " * 5000 + "1" + "}" * 5000, "nested too deeply"),
    "impossible date": ("ADR0042: 2026-13-45\n", "can't be read"),
    "control characters in a key": ('"a\\x07b": 1\nADR0042: []\n', "no decision a\\x07b"),
}


@pytest.mark.parametrize(("text", "named"), HAZARDS.values(), ids=HAZARDS.keys())
def test_hostile_yaml_is_refused_with_a_clear_reason_never_a_crash(text, named):
    with pytest.raises(KnowledgeError) as refused:
        checks(text)

    assert named in str(refused.value)
    assert len(str(refused.value)) < 200  # messages never echo much file text


def test_a_raw_control_character_in_the_text_is_refused():
    with pytest.raises(KnowledgeError, match="not valid YAML"):
        read_checks(b"ADR0042: \x07\n", NAME, REPO, NOTES)


def test_text_that_is_not_utf8_is_refused():
    with pytest.raises(KnowledgeError, match="UTF-8"):
        read_checks(GOOD.encode() + b"\xff\xfe", NAME, REPO, NOTES)


def test_text_over_one_megabyte_is_refused():
    with pytest.raises(KnowledgeError, match="too large"):
        read_checks((GOOD + "#" * 1_048_577).encode(), NAME, REPO, NOTES)


def test_reading_from_disk_refuses_a_link(tmp_path):
    (tmp_path / "real.yaml").write_text(GOOD)
    (tmp_path / "checks.yaml").symlink_to(tmp_path / "real.yaml")

    with pytest.raises(KnowledgeError, match="not a link"):
        read(tmp_path / "checks.yaml", NAME)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no named pipes here")
def test_reading_from_disk_refuses_a_pipe_without_hanging(tmp_path):
    os.mkfifo(tmp_path / "checks.yaml")

    with pytest.raises(KnowledgeError, match="regular file"):
        read(tmp_path / "checks.yaml", NAME)


def test_reading_from_disk_refuses_a_file_over_one_megabyte(tmp_path):
    (tmp_path / "checks.yaml").write_text("#" * 1_048_577)

    with pytest.raises(KnowledgeError, match="too large"):
        read(tmp_path / "checks.yaml", NAME)


# ---------- promotions ----------

PROMOTION = """\
- check: payments-db-only-in-api
  snapshot:
    decision: ADR0042
    engine: package
    value: "@acme/payments-db"
    polarity: avoid
    where: ["services/**"]
    except: ["services/payments-api/**"]
    why: services reach payments only through payments-api
"""
PROMOTIONS = "precedent/promotions.yaml"


def promotions(text: str):
    return read_promotions(text.encode(), PROMOTIONS, REPO)


def test_a_promotion_is_a_frozen_snapshot_of_its_check():
    [check] = checks(GOOD)
    [promotion] = promotions(PROMOTION)

    assert promotion.check == check.id
    assert promotion.snapshot == check.content
    assert (promotion.scope, promotion.from_, promotion.critical) == ("all", None, False)


def test_a_promotion_reads_its_scope_date_and_critical_flag():
    [promotion] = promotions(PROMOTION + "  scope: new-code\n  from: 2026-12-01\n  critical: true\n")

    assert (promotion.scope, promotion.from_, promotion.critical) == ("new-code", date(2026, 12, 1), True)


PROMOTION_REFUSED = {
    "no snapshot": ("- check: payments-db-only-in-api\n", "snapshot"),
    "snapshot unknown field": (PROMOTION + "    unless: [x]\n", "snapshot: unknown field unless"),
    "snapshot with an id": (
        PROMOTION.replace("    decision:", "    id: x\n    decision:"),
        "snapshot: unknown field id",
    ),
    "snapshot leaves the home": (PROMOTION.replace('["services/**"]', '["../x"]'), "inside this home"),
    "unknown scope": (PROMOTION + "  scope: everything\n", ": scope: "),
    "from as text": (PROMOTION + '  from: "soon"\n', ": from: "),
    "from as a number": (PROMOTION + "  from: 0\n", ": from: "),
    "from with a time": (PROMOTION + "  from: 2026-12-01T10:00:00Z\n", ": from: "),
    "critical not a boolean": (PROMOTION + '  critical: "yes"\n', ": critical: "),
    "unknown field": (PROMOTION + "  until: 2027-01-01\n", "unknown field until"),
    "twice for one check": (PROMOTION + PROMOTION, "payments-db-only-in-api appears twice"),
    "not a list": ("check: x\n", "list of promotions"),
    "an empty mapping": ("{}\n", "list of promotions"),
    "false": ("false\n", "list of promotions"),
    "zero": ("0\n", "list of promotions"),
    "an empty string": ('""\n', "list of promotions"),
    "entry not a mapping": ("- just text\n", "check and snapshot"),
}


@pytest.mark.parametrize(("text", "named"), PROMOTION_REFUSED.values(), ids=PROMOTION_REFUSED.keys())
def test_every_promotion_mistake_stops_the_load(text, named):
    with pytest.raises(KnowledgeError) as refused:
        promotions(text)

    assert named in str(refused.value)


def test_an_empty_promotions_file_has_none():
    assert promotions("") == ()


SAME = {
    "field order": PROMOTION.replace(
        '    engine: package\n    value: "@acme/payments-db"\n', '    value: "@acme/payments-db"\n    engine: package\n'
    ),
    "glob order and repeats": PROMOTION.replace('["services/**"]', '["services/**", "services/**"]'),
    "comments and quoting": PROMOTION.replace("engine: package", "engine: 'package'  # the same"),
}
DIFFERENT = {
    "decision": PROMOTION.replace("decision: ADR0042", "decision: ADR0043"),
    "engine": PROMOTION.replace("engine: package", "engine: component"),
    "value": PROMOTION.replace("@acme/payments-db", "@acme/payments-dbx"),
    "polarity": PROMOTION.replace("polarity: avoid", "polarity: prefer"),
    "where": PROMOTION.replace('["services/**"]', '["services/a/**"]'),
    "except": PROMOTION.replace('["services/payments-api/**"]', "[]"),
    "why": PROMOTION.replace("only through payments-api", "only through the api"),
    "quote added": PROMOTION + '    quote: "No service other than payments-api imports `@acme/payments-db`."\n',
}


@pytest.mark.parametrize("text", SAME.values(), ids=SAME.keys())
def test_a_snapshot_equals_its_check_whatever_the_formatting(text):
    [check] = checks(GOOD)

    assert promotions(text)[0].snapshot == check.content


@pytest.mark.parametrize("text", DIFFERENT.values(), ids=DIFFERENT.keys())
def test_a_snapshot_differs_from_its_check_when_any_real_field_does(text):
    [check] = checks(GOOD)

    assert promotions(text)[0].snapshot != check.content


def test_a_version_snapshot_differs_when_its_range_does():
    [check] = checks(entry(engine="version", value="react", range='">=18"'))
    snapshot = (
        "- check: payments-db-only-in-api\n  snapshot: {decision: ADR0042, engine: version, value: react, "
        "polarity: avoid, why: a reason, range: '>=17'}\n"
    )

    assert promotions(snapshot)[0].snapshot != check.content


# ---------- v0.3 precedent.yaml ----------

LEGACY = """\
ADR0042:
  - {kind: package, value: "@acme/payments-db", polarity: avoid, why: services use payments-api}
  - {kind: path, value: services/legacy/, polarity: avoid, why: frozen}
"""
LEGACY_NAME = "docs/adr/precedent.yaml"


def legacy(text: str) -> tuple[Check, ...]:
    return legacy_checks(text.encode(), LEGACY_NAME, REPO, {"ADR0042"})


def test_a_v03_precedent_yaml_reads_as_checks_that_block_in_local_mode():
    found = legacy(LEGACY)
    promoted = local_promotions(found)

    assert [(c.engine, c.value, c.where, c.why) for c in found] == [
        ("package", "@acme/payments-db", ("**",), "services use payments-api"),
        ("path", "services/legacy/", ("**",), "frozen"),
    ]
    assert [p.snapshot for p in promoted] == [c.content for c in found]


def test_v03_ids_are_stable_and_one_per_rule():
    first, second = legacy(LEGACY), legacy(LEGACY)

    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)


def test_a_v03_why_that_is_a_number_reads_as_text_as_today():
    [check] = legacy("ADR0042:\n  - {kind: package, value: axios, polarity: avoid, why: 5}\n")

    assert check.why == "5"


def test_the_same_v03_rule_twice_is_refused_naming_it():
    with pytest.raises(KnowledgeError, match="appears twice"):
        legacy(LEGACY + '  - {kind: package, value: "@acme/payments-db", polarity: avoid, why: again}\n')


@pytest.mark.parametrize(
    "line",
    [
        "{kind: package, value: axios, polarity: avoid}",
        "{kind: package, value: axios, polarity: avoid, why: x, unless: [y]}",
    ],
    ids=["missing why", "extra field"],
)
def test_a_v03_entry_in_the_wrong_shape_is_refused(line):
    with pytest.raises(KnowledgeError, match="exactly kind, value, polarity and why"):
        legacy(f"ADR0042:\n  - {line}\n")


RULES = st.lists(
    st.tuples(
        st.sampled_from(["package", "path"]),
        st.from_regex(r"[a-z][a-z0-9-]{0,12}", fullmatch=True),
        st.sampled_from(["avoid", "prefer", "require"]),
        st.text(alphabet="abc ", min_size=1, max_size=8).filter(str.strip),
    ),
    min_size=1,
    max_size=4,
    unique_by=lambda r: (r[0], r[1], r[2]),
)


@settings(deadline=None)  # writes a file per example; disk speed under parallel runs isn't the property
@given(rules=RULES)
def test_any_v03_file_reads_exactly_as_todays_loader_reads_it(rules, tmp_path_factory):
    lines = "".join(f'  - {{kind: {k}, value: "{v}", polarity: {p}, why: "{w}"}}\n' for k, v, p, w in rules)
    text = "ADR0042:\n" + lines
    path = tmp_path_factory.mktemp("legacy") / "precedent.yaml"
    path.write_text(text)
    scopes = _knowledge(path, {"ADR0042"})["ADR0042"]

    today = [(s.kind, s.value, s.polarity, (s.quote or "").removesuffix(" (precedent.yaml)")) for s in scopes]

    assert [(c.engine, c.value, c.polarity, c.why) for c in legacy(text)] == today


# ---------- one meaning for globs, everywhere ----------

GLOBS = [
    ("**", "a.ts", True),
    ("**", "a/b/c.ts", True),
    ("services/**", "services/a.ts", True),
    ("services/**", "services/x/y.ts", True),
    ("services/**", "servicesx/a.ts", False),
    ("services/**", "services", False),
    ("**/generated/**", "generated/a.ts", True),
    ("**/generated/**", "a/b/generated/c.ts", True),
    ("**/generated/**", "a/generatedx/c.ts", False),
    ("*.ts", "a.ts", True),
    ("*.ts", "x/a.ts", False),
    ("src/*/index.ts", "src/a/index.ts", True),
    ("src/*/index.ts", "src/a/b/index.ts", False),
    ("a?.ts", "ab.ts", True),
    ("a?.ts", "a/.ts", False),
    ("a+b.ts", "a+b.ts", True),
    ("a+b.ts", "aab.ts", False),
    ("[x].ts", "[x].ts", True),
    ("[x].ts", "x.ts", False),
    ("\u65e5\u672c/*", "\u65e5\u672c/menu.md", True),
    ("my docs/*", "my docs/a.md", True),
    ("Services/**", "services/a.ts", False),
    ("**", "src/evil\nname.py", True),
    ("src/*.py", "src/evil\nname.py", True),
]


@pytest.mark.parametrize(("glob", "path", "hit"), GLOBS, ids=[f"{g!r} vs {p!r}" for g, p, _ in GLOBS])
def test_a_glob_means_the_same_thing_everywhere(glob, path, hit):
    assert matches(glob, path) is hit


SEGMENT = st.text(alphabet="ab*?.", min_size=1, max_size=5).filter(lambda s: s not in (".", "..") and "**" not in s)
PART = st.text(alphabet="ab.", min_size=1, max_size=5).filter(lambda s: s not in (".", ".."))


@given(st.lists(SEGMENT, min_size=1, max_size=4), st.lists(PART, min_size=1, max_size=4))
def test_without_double_stars_a_glob_matches_like_fnmatch_segment_by_segment(globs, parts):
    """The reference: the same number of segments, each matched by Python's fnmatch (no character classes here)."""
    expected = len(globs) == len(parts) and all(fnmatchcase(p, g) for g, p in zip(globs, parts, strict=False))

    assert matches("/".join(globs), "/".join(parts)) is expected


@pytest.mark.parametrize(
    ("glob", "path"),
    [("**/" * 8 + "x", "a/" * 400 + "y"), ("*a" * 12 + "b", "a" * 60), ("**/" * 20 + "**", "a/" * 1000)],
    ids=["many double stars", "many stars in a segment", "double stars to the end"],
)
def test_matching_stays_fast_on_hostile_globs(glob, path):
    start = time.perf_counter()
    matches(glob, path)
    assert time.perf_counter() - start < 0.05


@pytest.mark.parametrize(
    "glob",
    ["", "a//b", "a/./b", "./a", "a/", "/a", "a/../b", "a\\b", "a\0b", "x" * 257],
    ids=[
        "empty",
        "empty segment",
        "dot segment",
        "leading dot",
        "trailing slash",
        "absolute",
        "dot dot",
        "backslash",
        "nul",
        "too long",
    ],
)
def test_a_glob_that_could_mean_two_things_is_refused(glob):
    assert not glob_ok(glob)


ENTRIES = [
    ("services/**", REPO, True),
    ("tag:services", REPO, True),
    ("tag:Bad Tag", REPO, False),
    ("shop:services/**", REPO, False),
    ("shop:services/**", ORG, True),
    ("*:**", ORG, True),
    ("a/b:services/**", ORG, False),
    ("shop:../x", ORG, False),
]


@pytest.mark.parametrize(
    ("where", "home", "ok"), ENTRIES, ids=[f"{e} in {'org' if h.repo is None else 'repo'}" for e, h, _ in ENTRIES]
)
def test_where_entries_follow_the_home(where, home, ok):
    assert entry_ok(where, home) is ok


CONTAINS = [
    (Home(), Home(repo="shop", path="services/payments"), True),
    (Home(repo="shop"), Home(repo="shop", path="services/payments"), True),
    (Home(repo="shop", path="services"), Home(repo="shop", path="services/payments"), True),
    (Home(repo="shop", path="services/payments"), Home(repo="shop", path="services/payments"), True),
    (Home(repo="shop", path="services/payments"), Home(repo="shop", path="services"), False),
    (Home(repo="shop", path="services/pay"), Home(repo="shop", path="services/payments"), False),
    (Home(repo="shop"), Home(repo="web"), False),
    (Home(repo="shop"), Home(), False),
]


@pytest.mark.parametrize(("outer", "inner", "inside"), CONTAINS)
def test_one_home_contains_another_only_when_its_folder_does(outer, inner, inside):
    assert contains(outer, inner) is inside
