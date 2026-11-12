import pytest

from precedent.core.grounding import grounded, keep_grounded
from precedent.core.model import Scope

ADR = "All code that is executed in Node.js should use the\nnative `fetch` for HTTP data fetching."


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("should use the native `fetch`", True),
        ("should use the native fetch", True),  # markdown backticks don't count
        ("should   use the\n native `fetch`", True),  # line wraps and spacing don't count
        ("should use native fetch", False),  # a paraphrase is not a quote
        ("Should use the native fetch", False),  # case counts
        ("  ", False),
    ],
    ids=["exact", "no-backticks", "rewrapped", "paraphrase", "case", "empty"],
)
def test_a_quote_counts_only_if_the_source_says_it_word_for_word(quote, expected):
    assert grounded(quote, ADR) is expected


def test_keep_grounded_drops_made_up_quotes():
    real = Scope(kind="package", value="node-fetch", polarity="avoid", quote="native `fetch`", extracted=True)
    invented = Scope(kind="package", value="axios", polarity="avoid", quote="never use axios", extracted=True)

    assert keep_grounded([real, invented], ADR) == [real]


@pytest.mark.parametrize(
    ("kind", "value", "usable"),
    [
        ("package", "node-fetch", True),
        ("package", "@mswjs/interceptors", True),
        ("package", "Moment.js", False),  # a product name, not what code imports
        ("package", "@backstage/core-*", False),  # a pattern, not a package
        ("symbol", "React.FC", True),
        ("symbol", "export default", True),
        ("symbol", "string form of entity references as a single URL segment", False),  # a sentence
        ("symbol", "import { helperFunc } from '../../lib/UtilityX/helper';", False),  # a whole line
        ("path", "packages/catalog-client", True),
        ("path", "some folder name", False),
    ],
)
def test_an_ai_read_scope_must_look_like_code(kind, value, usable):
    scope = Scope.model_validate({"kind": kind, "value": value, "polarity": "avoid", "quote": "q", "extracted": True})

    assert keep_grounded([scope], "q") == ([scope] if usable else [])
