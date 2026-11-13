"""`precedent why`: which decision about something wins, and why (ADR0018), as text for people or JSON for tools."""

import re

from precedent.core.authority import Standing

Ranked = dict[tuple[str, str], list[Standing]]
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def explain(name: str, ranked: Ranked) -> str:
    if not ranked:
        return f"No recorded decision about {name}."
    return "\n\n".join(_thing(kind, value, standings) for (kind, value), standings in ranked.items())


def as_json(name: str, ranked: Ranked) -> dict:
    return {
        "name": name,
        "things": [
            {"kind": kind, "value": value, "standings": [_fields(s) for s in standings]}
            for (kind, value), standings in ranked.items()
        ],
    }


def _thing(kind: str, value: str, standings: list[Standing]) -> str:
    lines = [f"{value} ({kind}): {_verdict(standings)}"]
    for s in standings:
        when = f" · decided {s.rule.decided_at}" if s.rule.decided_at else ""
        lines.append(f"- {s.rule.decision} · {s.rule.scope.polarity} · {s.outcome}: {s.reason}{when}")
        quote = f'"{_plain(s.rule.scope.quote)}"' if s.rule.scope.quote else ""
        where = f"({s.rule.source})" if s.rule.source else ""
        if quote or where:
            lines.append(f"    {' '.join(p for p in (quote, where) if p)}")
    return "\n".join(lines)


def _plain(text: str) -> str:
    """A quote from an untrusted document, as one line with no control characters (no terminal escapes)."""
    return " ".join(CONTROL.sub(" ", text).split())


def _verdict(standings: list[Standing]) -> str:
    winners = [s.rule.decision for s in standings if s.outcome == "wins"]
    disputed = [s.rule.decision for s in standings if s.outcome == "disputed"]
    if disputed:
        return (
            f"{' and '.join(disputed)} disagree, and neither replaces the other. Ask an owner which holds, and record"
            " the answer as a decision that replaces the other."
        )
    if len(winners) > 1:
        return f"{' and '.join(winners)} agree."
    return f"{winners[0]} wins." if winners else "no decision about it is in force."


def _fields(s: Standing) -> dict:
    return {
        "decision": s.rule.decision,
        "polarity": s.rule.scope.polarity,
        "outcome": s.outcome,
        "reason": s.reason,
        "status": s.rule.status,
        "decided_at": s.rule.decided_at.isoformat() if s.rule.decided_at else None,
        "quote": s.rule.scope.quote,
        "source": s.rule.source,
    }
