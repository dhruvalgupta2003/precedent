"""Checks on LLM-read facts before they reach the graph (docs/spec.md §6). The model proposes; code decides.

1. Grounding: the quote must be in the source word for word.
2. Shape: the value must look like what code contains (a package name, a short construct, a path), not a sentence.
"""

import re

from precedent.core.model import Scope

PACKAGE = re.compile(r"(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*")  # as imported: lowercase, no patterns
MAX_SYMBOL_WORDS = 2  # "export default", "typeof fetch"; more is a sentence
MAX_SYMBOL_CHARS = 40


def grounded(quote: str, source: str) -> bool:
    """Spacing, line wraps and markdown emphasis (`, *) don't count; every word and its case does."""
    norm = " ".join(quote.replace("`", "").replace("*", "").split())
    return bool(norm) and norm in " ".join(source.replace("`", "").replace("*", "").split())


def looks_like_code(scope: Scope) -> bool:
    value = scope.value
    if scope.kind == "package":
        return bool(PACKAGE.fullmatch(value))
    if scope.kind in ("symbol", "config"):
        plain_word = value.isalpha() and value.islower()  # "element" matches prose and variable names alike
        short = len(value.split()) <= MAX_SYMBOL_WORDS and len(value) <= MAX_SYMBOL_CHARS
        return short and not plain_word and not value.endswith(";")
    return " " not in value


def keep_grounded(scopes: list[Scope], source: str) -> list[Scope]:
    """The scopes that pass both checks; exceptions that don't look like code are dropped from them."""
    kept = [s for s in scopes if s.quote and grounded(s.quote, source) and looks_like_code(s)]
    return [s.model_copy(update={"unless": tuple(u for u in s.unless if _symbol_like(u))}) for s in kept]


def _symbol_like(code: str) -> bool:
    return looks_like_code(Scope(kind="symbol", value=code))
