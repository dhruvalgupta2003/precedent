"""Errors Precedent raises; surfaces map them to exit codes or HTTP statuses (ADR0009)."""


class PrecedentError(Exception):
    """Base for every error Precedent raises on purpose."""


class KnowledgeError(PrecedentError):
    """The decisions as written can't be trusted: a bad precedent.yaml entry, or two decision files with one number.

    Ingest stops before it writes anything: reviewed input is never half-applied.
    """


class ExtractionError(PrecedentError):
    """The LLM could not read a source (provider down, bad key, invalid output). Ingest continues without it."""
