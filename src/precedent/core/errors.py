"""Errors Precedent raises; surfaces map them to exit codes or HTTP statuses (ADR0009)."""


class PrecedentError(Exception):
    """Base for every error Precedent raises on purpose."""


class KnowledgeError(PrecedentError):
    """precedent.yaml has an entry that can't be trusted. Ingest stops: reviewed input is never half-applied."""


class ExtractionError(PrecedentError):
    """The LLM could not read a source (provider down, bad key, invalid output). Ingest continues without it."""
