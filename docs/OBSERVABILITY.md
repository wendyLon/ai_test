# Observability

This folder contains helpers for tracing, metrics, logging and debug tools.

Components:
- OpenTelemetry tracing: `platform/observability/otel.py` (initializes tracer, inject/extract trace context)
- Prometheus metrics: `platform/observability/metrics.py` (queue lengths, latency, confidence, failures)
- Structured logging: `platform/observability/logging.py` (JSON logs with trace correlation)
- Debug tools: `platform/observability/debug_tools.py` (find and replay tasks by `trace_id`)

Integration points:
- `platform/worker_base.py` starts a span per message and records latency/ failures.
- `platform/queue_manager.py` injects trace context into messages on push.
- `scripts/example_worker.py` initializes tracer, Prometheus server, and logging.

Running Prometheus exporter:
- `platform/observability/metrics.start_prometheus(port=8000)` starts an HTTP endpoint with metrics.

Trace collection:
- Configure `OTEL_EXPORTER_OTLP_ENDPOINT` to send spans to an OTLP-compatible collector.
- Otherwise spans are printed to console via `ConsoleSpanExporter`.
