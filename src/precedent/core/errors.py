"""Errors Precedent raises; surfaces map them to exit codes or HTTP statuses (ADR0009)."""


class PrecedentError(Exception):
    """Base for every error Precedent raises on purpose."""


class KnowledgeError(PrecedentError):
    """The decisions as written can't be trusted: a bad precedent.yaml entry, or two decision files with one number.

    Ingest stops before it writes anything: reviewed input is never half-applied.
    """


class ExtractionError(PrecedentError):
    """The LLM could not read a source (provider down, bad key, invalid output). Ingest continues without it."""


class NothingLoadedError(PrecedentError):
    """The org holds no decisions, so nothing can be checked: usually a misspelled --org, or a load not run yet.

    It is an error, never CLEAR: a check that looked at nothing must not pass (#66).
    """


class BundleError(PrecedentError):
    """A saved bundle can't be read: damaged, or saved by another version. It is never used; it is built again."""
