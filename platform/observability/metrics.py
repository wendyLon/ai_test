"""Prometheus metrics and helpers for agent observability."""
from prometheus_client import start_http_server, Gauge, Histogram, Counter
from typing import Dict
import time

# Metrics definitions
QUEUE_LENGTH = Gauge('agent_queue_length', 'Queue length per agent', ['agent'])
PROCESSING_LENGTH = Gauge('agent_processing_length', 'Processing list length per agent', ['agent'])
DLQ_LENGTH = Gauge('agent_dlq_length', 'Dead letter queue length per agent', ['agent'])
PROCESS_LATENCY = Histogram('agent_processing_seconds', 'Processing latency seconds', ['agent'])
EXTRACTION_CONFIDENCE = Histogram('extraction_confidence', 'Extraction confidence distribution', ['agent'])
FAILURE_COUNT = Counter('agent_failures_total', 'Failures per agent', ['agent','provider_id'])


def start_prometheus(port: int = 8000):
    start_http_server(port)


def record_queue_lengths(qm, agents):
    for a in agents:
        try:
            qlen = qm.len(a)
            proc = qm.processing_len(a)
            dlq = qm.dlq_len(a)
            QUEUE_LENGTH.labels(agent=a).set(qlen)
            PROCESSING_LENGTH.labels(agent=a).set(proc)
            DLQ_LENGTH.labels(agent=a).set(dlq)
        except Exception:
            continue


def record_processing_latency(agent: str, latency_seconds: float):
    PROCESS_LATENCY.labels(agent=agent).observe(latency_seconds)


def record_extraction_confidence(agent: str, confidence: float):
    EXTRACTION_CONFIDENCE.labels(agent=agent).observe(confidence)


def record_failure(agent: str, provider_id: str):
    FAILURE_COUNT.labels(agent=agent, provider_id=str(provider_id)).inc()
