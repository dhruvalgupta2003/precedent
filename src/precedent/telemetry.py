"""Tracing for Precedent (ADR0006).

Code emits standard OpenTelemetry spans and never names a vendor. Point the standard
OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_HEADERS variables at Langfuse (or any OTLP
backend) to collect them; with no endpoint, tracing is a no-op.
"""

import functools
import os
from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

tracer = trace.get_tracer("precedent")


def setup(exporter: SpanExporter | None = None) -> bool:
    """Install a tracer provider; returns False when there is nowhere to send spans.

    Tests pass an in-memory exporter; real runs build an OTLP exporter from the environment.
    """
    if exporter is None:
        if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            return False
        exporter = OTLPSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "precedent"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return True


def traced[**P, R](name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Wrap a function in a span named `name`, so every call is timed and visible in traces."""

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(name):
                return fn(*args, **kwargs)

        return wrapper

    return decorate
