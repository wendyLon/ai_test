import time
from typing import Dict, Any

class MonitoringHooks:
    def __init__(self):
        self.metrics = {}

    def inc(self, key: str, value: int = 1):
        self.metrics[key] = self.metrics.get(key, 0) + value

    def gauge(self, key: str, value: Any):
        self.metrics[key] = value

    def record_latency(self, key: str, latency: float):
        self.metrics.setdefault(key + '.latencies', []).append(latency)

    def dump(self) -> Dict[str, Any]:
        return {'ts': int(time.time()), 'metrics': self.metrics}

monitor = MonitoringHooks()
