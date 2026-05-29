"""Structured JSON logging with trace correlation."""
import logging
import sys
from pythonjsonlogger import jsonlogger
from opentelemetry.trace import get_current_span


def setup_logging(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)
    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)


def get_logger(name: str):
    return logging.getLogger(name)


def enrich_log_with_trace(logger, msg: str, **kwargs):
    # attach trace ids from current span if available
    span = get_current_span()
    span_ctx = getattr(span, 'get_span_context', lambda: None)()
    extra = kwargs.copy()
    try:
        if span_ctx and span_ctx.trace_id:
            extra['trace_id'] = format(span_ctx.trace_id, '032x')
            extra['span_id'] = format(span_ctx.span_id, '016x')
    except Exception:
        pass
    logger.info(msg, extra=extra)
