"""An AI-read rule must name what it quotes (issue #67).

Bug this guards: a model returned "avoid moment" with the quote "Avoid `lodash` in new code, except
`lodash.debounce`, which stays." The quote was in the document word for word, so it was kept, and every
`import moment` warned. A quote that is true but about something else is no evidence for the rule.

The rule, per kind:
- a package: at least one word of its name appears as a whole word in the quote ("Prisma" for @prisma/client,
  "fetch" for node-fetch), never just inside another word ("momentum" is not "moment");
- anything else (a code construct, a path, a setting): every word of it appears, in any order and in any word form
  close to it ("default exports" names `export default`); one with no words must appear as written.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from precedent.core.grounding import keep_grounded, names_it
from precedent.core.model import Scope

LODASH = "Avoid `lodash` in new code, except `lodash.debounce`, which stays."

CASES = [  # kind, value, quote, and whether the quote names it
    ("package", "moment", LODASH, False),
    ("package", "lodash", LODASH, True),
    ("package", "lodash.debounce", LODASH, True),
    ("package", "node-fetch", "should use the native `fetch`", True),
    ("package", "@prisma/client", "The API server talks to Postgres through Prisma.", True),
    ("package", "@tanstack/react-query", "We use React Query for server state.", True),
    ("package", "moment", "Use `Moment` only in the old scripts.", True),
    ("package", "moment", "Lists use momentum scrolling.", False),
    ("package", "pg", "Talk to Postgres with `pg`.", True),
    ("package", "pg", "Keep pages small.", False),
    ("package", "axios", "Use the built-in fetch for every HTTP call.", False),
    ("package", "styled-components", "Avoid class components.", True),  # loose on purpose: any word of the name
    ("symbol", "export default", "We don't use default exports, except for React.lazy pages.", True),
    ("symbol", "export default", "Default timeouts are 30 seconds.", False),
    ("symbol", "React.lazy", "Pages load with React.lazy.", True),
    ("symbol", "fetchApiRef", "Frontend plugins should prefer the shared HTTP client.", False),
    ("symbol", "export *", "Index files that re-export other index files use the wildcard form.", True),
    ("symbol", "useEffect", "Avoid useEffect for data fetching.", True),
    ("symbol", "?.", "Use ?. for optional access.", True),
    ("symbol", "?.", "Use optional chaining.", False),
    ("path", "src/legacy/", "Nothing new goes in src/legacy.", True),
    ("path", "docs/adr", "A decision was made to store ADRs in a log in the project repository.", False),
    ("config", "strict: true", "TypeScript runs with strict set to true.", True),
    ("config", "strict: true", "Reviews are strict.", False),
]


@pytest.mark.parametrize(("kind", "value", "quote", "named"), CASES, ids=[f"{c[1]}-{c[3]}" for c in CASES])
def test_a_quote_must_name_what_the_rule_is_about(kind, value, quote, named):
    scope = Scope(kind=kind, value=value, polarity="avoid", quote=quote, extracted=True)

    assert names_it(scope) is named
    assert (keep_grounded([scope], quote) == [scope]) is named


def test_the_reported_pair_is_dropped_and_the_true_rules_from_that_sentence_are_kept():
    """#67 exactly as reported (gpt-4o-mini): moment only appeared in a Context sentence about old scripts."""
    adr = f"## Context\n\nSome old scripts still use moment.\n\n## Decision\n\n{LODASH}\n"
    found = [
        Scope(kind="package", value="moment", polarity="avoid", quote=LODASH, extracted=True),
        Scope(
            kind="package", value="lodash", polarity="avoid", quote=LODASH, extracted=True, unless=("lodash.debounce",)
        ),
    ]

    assert [s.value for s in keep_grounded(found, adr)] == ["lodash"]


WORD = st.text(alphabet="bcdfghjklmnpqrstvwxz", min_size=3, max_size=8)  # no vowels: never an English word


@given(name=WORD, inserted=st.booleans())
def test_a_package_is_named_exactly_when_its_name_is_in_the_quote(name, inserted):
    quote = f"New code must not use `{name}` at all." if inserted else "New code must not use it at all."
    scope = Scope(kind="package", value=name, polarity="avoid", quote=quote, extracted=True)

    assert names_it(scope) is inserted


@given(name=WORD)
def test_a_package_name_inside_a_longer_word_is_not_a_mention(name):
    scope = Scope(kind="package", value=name, polarity="avoid", quote=f"Avoid {name}ish code.", extracted=True)

    assert not names_it(scope)
