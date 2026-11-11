import gzip
import os
import sqlite3
import types
from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner
from cryptography.exceptions import InvalidTag

from backup_daemon import main as main_mod
from backup_daemon.crypto import compress_file, decrypt_file, encrypt_file
from backup_daemon.dumpers import dump_postgres, dump_sqlite
from backup_daemon.storage import S3Storage


def test_compress_encrypt_decrypt_roundtrip(tmp_path):
    raw_file = tmp_path / "sample.sql"
    payload = b"CREATE TABLE items (id INT PRIMARY KEY);\n" * 50
    raw_file.write_bytes(payload)

    gz_file = compress_file(raw_file)
    assert gz_file.exists()
    assert not raw_file.exists()
    assert gzip.decompress(gz_file.read_bytes()) == payload

    key_hex = os.urandom(32).hex()
    enc_file = encrypt_file(gz_file, key_hex)
    assert enc_file.exists()
    assert not gz_file.exists()

    dec_file = decrypt_file(enc_file, key_hex)
    assert dec_file.exists()
    assert gzip.decompress(dec_file.read_bytes()) == payload


def test_encrypt_decrypt_validation_and_wrong_key(tmp_path):
    target = tmp_path / "data.bin"
    target.write_bytes(b"secret-payload")

    with pytest.raises(ValueError, match="16, 24, or 32 bytes"):
        encrypt_file(target, "abcd")

    valid_key = os.urandom(32).hex()
    wrong_key = os.urandom(32).hex()
    enc_file = encrypt_file(target, valid_key)

    with pytest.raises(InvalidTag):
        decrypt_file(enc_file, wrong_key)

    truncated = tmp_path / "short.enc"
    truncated.write_bytes(b"short")
    with pytest.raises(ValueError, match="truncated"):
        decrypt_file(truncated, valid_key)


def test_dump_sqlite_live_wal_and_missing(tmp_path):
    db_file = tmp_path / "app.db"
    out_dir = tmp_path / "dumps"
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("INSERT INTO notes (body) VALUES ('hello-wal')")
    conn.commit()
    conn.close()

    dumped = dump_sqlite(db_file, out_dir)
    assert dumped.is_file()

    verify_conn = sqlite3.connect(dumped)
    rows = verify_conn.execute("SELECT body FROM notes").fetchall()
    verify_conn.close()
    assert rows == [("hello-wal",)]

    with pytest.raises(FileNotFoundError):
        dump_sqlite(tmp_path / "missing.db", out_dir)


def test_dump_postgres_preserves_os_environ_and_passes_pgpassword(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["check"] = check

    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin"))
    monkeypatch.setattr("backup_daemon.dumpers.subprocess.run", fake_run)

    out = dump_postgres("db.internal", 5432, "postgres", "prod", "s3cr3t", tmp_path / "pg_out")
    assert out.parent.is_dir()
    assert captured["check"] is True
    assert captured["cmd"][0] == "pg_dump"
    assert captured["env"]["PGPASSWORD"] == "s3cr3t"
    assert "PATH" in captured["env"]


def test_s3_retention_and_run_backup_job_honors_custom_prefixes(tmp_path, monkeypatch):
    sqlite_db = tmp_path / "service.db"
    conn = sqlite3.connect(sqlite_db)
    conn.execute("CREATE TABLE t (x INT)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    old_ts = datetime.now(timezone.utc) - timedelta(days=45)
    fresh_ts = datetime.now(timezone.utc) - timedelta(days=2)

    class FakeS3Client:
        def __init__(self):
            self.uploaded = []
            self.deleted = []

        def upload_file(self, filename, bucket, key):
            self.uploaded.append((bucket, key, os.path.exists(filename)))

        def list_objects_v2(self, Bucket, Prefix):
            return {
                "Contents": [
                    {"Key": f"{Prefix}/old.enc", "LastModified": old_ts},
                    {"Key": f"{Prefix}/fresh.enc", "LastModified": fresh_ts},
                ]
            }

        def delete_object(self, Bucket, Key):
            self.deleted.append((Bucket, Key))

    fake_client = FakeS3Client()
    monkeypatch.setattr("backup_daemon.storage.boto3.client", lambda *a, **kw: fake_client)

    config = {
        "s3": {
            "endpoint_url": "http://localhost:9000",
            "bucket": "my-backups",
            "access_key": "ak",
            "secret_key": "sk",
        },
        "encryption_key_hex": os.urandom(32).hex(),
        "retention_days": 30,
        "databases": [
            {"name": "sqlite-main", "type": "sqlite", "path": str(sqlite_db), "s3_prefix": "custom-sqlite"}
        ],
    }

    main_mod.run_backup_job(config)
    assert len(fake_client.uploaded) == 1
    assert fake_client.uploaded[0][0] == "my-backups"
    assert fake_client.uploaded[0][1].startswith("custom-sqlite/sqlite_service_")
    assert fake_client.uploaded[0][1].endswith(".db.gz.enc")
    assert fake_client.deleted == [("my-backups", "custom-sqlite/old.enc")]


def test_storage_negative_retention_rejected(monkeypatch):
    monkeypatch.setattr("backup_daemon.storage.boto3.client", lambda *a, **kw: types.SimpleNamespace())
    s3 = S3Storage(None, "bucket", "ak", "sk")
    with pytest.raises(ValueError, match="non-negative"):
        s3.enforce_retention("databases", -1)


def test_cli_once_invokes_backup_job(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("retention_days: 7\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(main_mod, "run_backup_job", lambda c: called.append(c))

    runner = CliRunner()
    res = runner.invoke(main_mod.main, ["--config", str(cfg), "--once"])
    assert res.exit_code == 0, res.output
    assert called == [{"retention_days": 7}]
