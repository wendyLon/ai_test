# Message Flow Examples

This file contains JSON examples for end-to-end flows.

## Discovery -> Crawl

```json
{
  "task_id": "...",
  "agent": "crawl",
  "source_agent": "discovery",
  "timestamp": "...",
  "provider_id": 12,
  "url": "https://example.org/events",
  "payload": {"type":"crawl","url":"https://example.org/events","depth":0},
  "metadata": {"discovered_by":"discovery"},
  "retry_count": 0,
  "priority": "high",
  "status": "pending",
  "trace_id": "..."
}
```

## Crawl -> DOM Analysis

```json
{
  "agent": "dom_analysis",
  "source_agent": "crawl",
  "payload": {"html_path":"data/raw/example_org_events.html","screenshot":"data/raw/example_org_events.png"}
}
```

## DOM Analysis -> Event Extraction

```json
{
  "agent": "event_extraction",
  "source_agent": "dom_analysis",
  "payload": {"block_html":"<div class=\"card\">...</div>"}
}
```

## Event Extraction -> SEN Classification -> Dedup -> SQL Export

Each agent enriches `payload.event` and forwards to the next queue. See `tests/flow_example.py` for runnable simulation.
