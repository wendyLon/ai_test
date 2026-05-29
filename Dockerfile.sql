FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ARG AGENT_NAME=sql
ENV AGENT_NAME=${AGENT_NAME}
ENV WORKER_CLASS=platform.agents.sql.sql_worker:SQLWorker
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
VOLUME ["/app/logs"]
EXPOSE 8000
CMD ["python", "infra/container_entry.py"]
