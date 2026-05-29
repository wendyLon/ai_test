# Monitoring

Expose metrics and structured logs:

- Counters: tasks_processed, tasks_failed, tasks_retried
- Gauges: queue_depth per-agent
- Latencies: per-agent processing time histograms
- Extraction metrics: avg confidence, low-confidence ratio

Integrations:
- Emits metrics via `platform/agents/monitoring.monitor`
- Prepare Prometheus exporters and OpenTelemetry traces (hooks present)
