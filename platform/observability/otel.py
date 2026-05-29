"""OpenTelemetry helpers for tracing across agents and tasks."""
import os
from typing import Dict
from opentelemetry import trace, propagators
from opentelemetry.trace import TracerProvider
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:
    OTLPSpanExporter = None

tracer = None


def init_tracer(service_name: str = 'platform'):
    global tracer
    provider = SDKTracerProvider()
    # choose exporter: OTLP if configured, otherwise console
    otlp_endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT')
    if OTLPSpanExporter and otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name)
    return tracer


def get_tracer():
    global tracer
    if tracer is None:
        return init_tracer()
    return tracer


def inject_trace_into_message(message: Dict):
    """Inject current trace context into message.metadata so downstream workers can extract it."""
    carrier = {}
    propagators.inject(carrier)
    md = message.setdefault('metadata', {})
    md.setdefault('trace_context', {}).update(carrier)
    # also ensure trace_id exists
    try:
        span = trace.get_current_span()
        span_ctx = span.get_span_context()
        if span_ctx and span_ctx.trace_id:
            md['otel_trace_id'] = format(span_ctx.trace_id, '032x')
    except Exception:
        pass
    return message


def extract_context_from_message(message: Dict):
    # Expect trace_context in metadata
    md = message.get('metadata', {})
    carrier = md.get('trace_context', {})
    ctx = propagators.extract(lambda k: carrier.get(k))
    return ctx
