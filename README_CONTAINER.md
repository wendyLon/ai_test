# Containerization and Deployment

This repository includes Dockerfiles and docker-compose manifests to run the agent system as independent services.

Services (one per agent):
- `discovery-worker`, `crawl-worker`, `dom-worker`, `extract-worker`, `dedup-worker`, `sql-worker`

Quickstart (local dev):

1. Build and start all services:
```bash
docker-compose up --build
```

2. To expose health ports locally (dev overrides):
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

3. Scale a worker (e.g., 3 crawlers):
```bash
docker-compose up --scale crawl-worker=3
```

Logs persist under `./logs/<agent>` (mounted into containers).

Health checks:
- Each worker exposes `GET /health` on port `8000` inside the container. Use the dev compose to map host ports.

Heartbeat and monitoring:
- Each container writes a heartbeat key to Redis at `{namespace}:heartbeat:{agent}:{hostname}`.
- Prometheus metrics are exposed on port `8000` inside container (use dev mapping to scrape per-host).

Production:
- For production we recommend deploying to Kubernetes. The provided `docker-compose.prod.yml` contains placeholders but not recommended for high-scale production. Use `Deployment` and `HorizontalPodAutoscaler` with readiness/liveness probes.

Failure recovery & restart policies:
- Compose sets `restart: unless-stopped`. Worker restart will requeue unacknowledged tasks from Redis processing lists.
