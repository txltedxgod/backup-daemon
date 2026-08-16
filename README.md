# backup-daemon

> Automated database backup daemon with **AES-256-GCM encryption**, Gzip compression, S3/MinIO cloud upload, and retention pruning in **Python**.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![AWS S3](https://img.shields.io/badge/Storage-S3%20%7C%20MinIO-569A31?style=flat-square&logo=amazons3)](https://aws.amazon.com/s3/)
[![Cryptography](https://img.shields.io/badge/Security-AES--256--GCM-green?style=flat-square)](https://cryptography.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

`#database-backup` `#postgres` `#sqlite` `#s3` `#minio` `#encryption` `#devops` `#python`

---

## Features

- **Multi-Database Support:** Dumps PostgreSQL databases and hot-copies SQLite files safely.
- **Client-Side Encryption:** Encrypts backup archives locally with authenticated AES-256-GCM prior to transmission.
- **S3 & MinIO Integration:** Uploads directly to AWS S3 or self-hosted S3-compatible object storage (MinIO, Wasabi, Cloudflare R2).
- **Automated Retention Pruning:** Deletes archives older than `retention_days` to prevent unbounded bucket storage costs.

## Quick Start

```bash
# Run one-off immediate backup
python -m backup_daemon.main --config=config.yaml --once

# Run as scheduled daemon
python -m backup_daemon.main --config=config.yaml
```

## Docker

```bash
docker build -t backup-daemon .
docker run -d \
  -v $(pwd)/config.yaml:/etc/backup-daemon/config.yaml \
  -v /var/data:/data:ro \
  backup-daemon
```
