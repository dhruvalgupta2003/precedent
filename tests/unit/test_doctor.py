from precedent.core.doctor import mentions, stale_lines
from precedent.core.model import Scope
from precedent.core.preflight import Rule

CLAUDE_MD = """# Catalog backend

- TypeScript on Node.js 20.
- Backend packages make HTTP calls with `node-fetch`.
- Never add `cross-fetch`.
- Use `luxon` for dates.
"""


def stance(value: str, polarity: str, quote: str) -> Scope:
    return Scope.model_validate(
        {"kind": "package", "value": value, "polarity": polarity, "quote": quote, "extracted": True}
    )


def rule(decision: str, value: str, polarity: str, **fields) -> Rule:
    scope = {"kind": "package", "value": value, "polarity": polarity, "quote": f"{decision} says so", "extracted": True}
    base = {"decision": decision, "title": decision, "status": "accepted", "tier": "structured", "confirmed": True}
    return Rule.model_validate(base | {"scope": scope, "source": f"{decision}.md"} | fields)


RULES = [
    rule("b/ADR013", "node-fetch", "require", status="superseded", superseded_by=["b/ADR014"]),
    rule("b/ADR014", "node-fetch", "avoid"),
    rule("b/ADR014", "cross-fetch", "require"),
    rule("b/ADR010", "luxon", "prefer"),
]


def test_a_line_that_recommends_what_a_live_decision_avoids_is_stale():
    lines = stale_lines(
        "CLAUDE.md", CLAUDE_MD, [stance("node-fetch", "prefer", "make HTTP calls with `node-fetch`")], RULES
    )

    [found] = lines
    assert (found.file, found.line, found.decision) == ("CLAUDE.md", 4, "b/ADR014")
    assert found.replaced == "b/ADR013"  # it repeats the decision ADR014 replaced
    assert "avoid node-fetch" in found.message


def test_a_line_that_forbids_what_a_live_decision_requires_is_stale():
    [found] = stale_lines("CLAUDE.md", CLAUDE_MD, [stance("cross-fetch", "avoid", "Never add `cross-fetch`.")], RULES)

    assert (found.line, found.decision) == (5, "b/ADR014")


def test_a_line_that_agrees_with_live_decisions_is_fine():
    assert stale_lines("CLAUDE.md", CLAUDE_MD, [stance("luxon", "prefer", "Use `luxon` for dates.")], RULES) == []


def test_a_line_about_something_no_decision_covers_is_fine():
    assert (
        stale_lines("CLAUDE.md", CLAUDE_MD, [stance("typescript", "require", "TypeScript on Node.js 20.")], RULES) == []
    )


def test_without_ai_a_line_that_names_an_avoided_package_is_flagged_for_a_human_to_check():
    [found] = mentions("CLAUDE.md", CLAUDE_MD, RULES)

    assert (found.line, found.decision) == (4, "b/ADR014")
    assert "check this line" in found.message


def test_a_quote_that_cannot_be_placed_on_a_line_is_reported_as_line_0():
    [found] = stale_lines("CLAUDE.md", CLAUDE_MD, [stance("node-fetch", "prefer", "words not in the file")], RULES)

    assert found.line == 0
