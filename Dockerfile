FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backup_daemon ./backup_daemon
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["python", "-m", "backup_daemon.main"]
CMD ["--config=/etc/backup-daemon/config.yaml"]
