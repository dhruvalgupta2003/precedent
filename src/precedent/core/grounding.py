"""Checks on LLM-read facts before they reach the graph (docs/spec.md §6). The model proposes; code decides.

1. Grounding: the quote must be in the source word for word.
2. Shape: the value must look like what code contains (a package name, a short construct, a path), not a sentence.
3. Naming: the quote must name what the rule is about (#67): a true sentence about lodash is no evidence about moment.
4. Planted: nothing an AI found in a decision or a document that talks to an AI reader anywhere is used (#68).
   Instruction files talk to an AI on purpose, so `precedent doctor` keeps to checks 1-3.
"""

import re
import unicodedata

from precedent.core.model import Scope

PACKAGE = re.compile(r"(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*")  # as imported: lowercase, no patterns
MAX_SYMBOL_WORDS = 2  # "export default", "typeof fetch"; more is a sentence
MAX_SYMBOL_CHARS = 40
WORDS = re.compile(r"[a-z0-9]+")
CLOSE_FORM = 3  # "export" names "exports" and "exporting"; a longer ending makes another word
MIN_STEM = 3  # a shorter word must match whole: "pg" is not "pages"
# Ways a text addresses the model reading it, not the people deciding. Known forms only: one layer, not a proof.
TALKS_TO_A_READER = re.compile(
    r"\b(?:ignore|disregard|forget)\b[^.!?]{0,40}?\b(?:previous|prior|above|earlier|preceding|foregoing)\b"
    r"[^.!?]{0,20}?\b(?:instructions?|prompts?|directions?|messages?|rules?|text|context|guidelines?)\b"
    r"|\b(?:note|message|instructions?|request|reminder)\s+(?:to|for)\s+(?:any\s+|all\s+|the\s+)?"
    r"(?:automated|ai|llm|language\s+model|machine|bot|assistant|model)s?\b"
    r"|\b(?:automated|ai|llm|machine)\s+(?:readers?|parsers?|crawlers?)\b"
    r"|\bif\s+you\s+are\s+(?:an?\s+)?(?:ai|llm|language\s+model|assistant|bot|automated|model)\b"
    r"|\b(?:dear|hey|hello|hi)\s+(?:ai|assistant|llm|model|bot|claude|gpt|chatgpt|copilot|gemini)\b"
    r"|\byour\s+system\s+prompt\b"
    r"|</?\s*(?:system|assistant|user|untrusted_[a-z_]+)\s*>"
    r"|\bdisregard\s+(?:everything|anything|all)\b[^.!?]{0,30}?\b(?:before|above|previous|prior|earlier)\b"
    r"|\byou\s+are\s+now\s+(?:an?|the)\s+\w+"
    r"|\b(?:assistants?|agents?|models?|llms?|ais?|bots?|readers?)\s+(?:should|must|shall|need\s+to|are\s+to)\s+"
    r"(?:also\s+)?(?:record|report|output|say|state|claim|respond|reply|note)\s+that\b"
)
# Cyrillic and Greek letters that look like Latin ones, which NFKC leaves alone: "\u0430utomated" reads as "automated".
LOOK_ALIKES = str.maketrans(
    "\u0430\u0432\u0435\u043a\u043c\u043d\u043e\u0440\u0441\u0442\u0443\u0445\u0456\u0458\u0455\u0501\u04bb\u04cf\u051d"
    "\u03b1\u03b5\u03b9\u03ba\u03bd\u03bf\u03c1\u03c4\u03c5\u03c7",
    "abekmhopctyxijsdhlwaeikvoptux",
)


def grounded(quote: str, source: str) -> bool:
    """Spacing, line wraps and markdown emphasis (`, *) don't count; every word and its case does."""
    norm = " ".join(quote.replace("`", "").replace("*", "").split())
    return bool(norm) and norm in " ".join(source.replace("`", "").replace("*", "").split())


def looks_like_code(scope: Scope) -> bool:
    value = scope.value
    if re.search(r"[^\S ]", value):  # a tab, newline or other control space: code values never hold one
        return False
    if scope.kind == "package":
        return bool(PACKAGE.fullmatch(value))
    if scope.kind in ("symbol", "config"):
        plain_word = value.isalpha() and value.islower()  # "element" matches prose and variable names alike
        short = len(value.split()) <= MAX_SYMBOL_WORDS and len(value) <= MAX_SYMBOL_CHARS
        return short and not plain_word and not value.endswith(";")
    return " " not in value


def keep_grounded(scopes: list[Scope], source: str) -> list[Scope]:
    """The scopes that pass both checks; exceptions that don't look like code are dropped from them."""
    kept = [s for s in scopes if s.quote and grounded(s.quote, source) and looks_like_code(s) and names_it(s)]
    return [s.model_copy(update={"unless": tuple(u for u in s.unless if _symbol_like(u))}) for s in kept]


def _symbol_like(code: str) -> bool:
    return looks_like_code(Scope(kind="symbol", value=code))


def names_it(scope: Scope) -> bool:
    """A package needs one word of its name, whole ("Prisma" for @prisma/client); anything else needs every word of
    it, in a close form ("default exports" for `export default`); a value with no words must appear as written."""
    quote, value = _words(scope.quote or ""), _words(scope.value)
    if scope.kind == "package":
        return bool(set(value) & set(quote))
    if not value:
        return _plain(scope.value).strip() in _plain(scope.quote or "")
    return all(any(_close(word, said) for said in quote) for word in value)


def without_planted(scopes: list[Scope], source: str) -> list[Scope]:
    """None of the scopes when the source talks to an AI reader anywhere: whoever planted the instruction controls
    the whole text, so checking only the quoted part could be dodged by layout (a heading, another section)."""
    return [] if talks_to_a_reader(source) else scopes


def talks_to_a_reader(text: str) -> bool:
    return bool(TALKS_TO_A_READER.search(" ".join(_plain(text).replace("`", "").replace("*", "").split())))


def _plain(text: str) -> str:
    """Lowercase, with look-alike forms folded (full-width letters) and invisible characters removed."""
    visible = "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")
    return visible.lower().translate(LOOK_ALIKES)


def _words(text: str) -> list[str]:
    return WORDS.findall(_plain(text))


def _close(word: str, said: str) -> bool:
    return said == word or (len(word) >= MIN_STEM and said.startswith(word) and len(said) - len(word) <= CLOSE_FORM)
