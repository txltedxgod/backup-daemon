import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def dump_postgres(
    host: str,
    port: int,
    user: str,
    dbname: str,
    password: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"pg_{dbname}_{timestamp}.sql"

    env = {**os.environ, "PGPASSWORD": password}
    cmd = [
        "pg_dump",
        "-h", host,
        "-p", str(port),
        "-U", user,
        "-d", dbname,
        "-f", str(out_file),
    ]

    subprocess.run(cmd, env=env, check=True)
    return out_file


def dump_sqlite(db_path: Path, output_dir: Path) -> Path:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"sqlite_{db_path.stem}_{timestamp}.db"

    with closing(sqlite3.connect(db_path)) as src_conn, closing(sqlite3.connect(out_file)) as dst_conn:
        src_conn.backup(dst_conn)

    return out_file
