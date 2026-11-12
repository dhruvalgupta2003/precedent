"""Errors Precedent raises; surfaces map them to exit codes or HTTP statuses (ADR0009)."""


class PrecedentError(Exception):
    """Base for every error Precedent raises on purpose."""


class ExtractionError(PrecedentError):
    """The LLM could not read a source (provider down, bad key, invalid output). Ingest continues without it."""
