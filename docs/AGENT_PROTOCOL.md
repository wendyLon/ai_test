# Agent Protocol

This document describes the standard JSON message protocol used by agents.

All messages are JSON objects using the following fields:

- `task_id`: unique task identifier (UUID)
- `agent`: target agent name
- `source_agent`: originating agent name
- `timestamp`: ISO8601 UTC timestamp
- `provider_id`: optional provider identifier
- `url`: optional URL associated with the task
- `payload`: agent-specific payload dictionary
- `metadata`: free-form metadata dict (for routing, trace, plugin hints)
- `retry_count`: integer retries performed
- `priority`: `low`/`normal`/`high`
- `status`: `pending`/`running`/`failed`/`completed`
- `trace_id`: correlation id for distributed tracing

Messages must be serializable as UTF-8 JSON strings for queue transport.

Agents SHOULD include `metadata.target_agent` to indicate intended recipient queue.

Examples and schema are provided in `platform/agents/message.py`.
