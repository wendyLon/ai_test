# Self-Healing

Self-healing responsibilities:

- Monitor extraction confidence metrics (low confidence spikes trigger fallback)
- When DOM structure changes detected (drop in candidate matches), increase AI extraction mode
- Auto-increase crawl depth for failing providers
- Route failing tasks to `retry_recovery` agent with exponential backoff

Implementation hooks:
- Agents emit `monitor` metrics via `platform/agents/monitoring.py`
- `RetryRecoveryAgent` handles replay and DLQ
- Agent plugins can implement adaptive strategies
