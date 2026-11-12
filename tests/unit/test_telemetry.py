from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from precedent import telemetry


def test_tracing_stays_off_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.setup() is False


def test_a_traced_function_keeps_its_name_and_result():
    @telemetry.traced("demo.add")
    def add(a: int, b: int) -> int:
        return a + b

    assert (add.__name__, add(2, 3)) == ("add", 5)


def test_a_traced_call_records_a_span_with_the_given_name():
    exporter = InMemorySpanExporter()
    assert telemetry.setup(exporter) is True

    @telemetry.traced("graph.query")
    def query() -> str:
        return "ok"

    query()
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)  # setup installed the SDK provider, not the no-op API one
    provider.force_flush()
    assert "graph.query" in [span.name for span in exporter.get_finished_spans()]
