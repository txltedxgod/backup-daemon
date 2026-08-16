import subprocess
import shutil
from pathlib import Path
from datetime import datetime


def dump_postgres(host: str, port: int, user: str, dbname: str, password: str, output_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"pg_{dbname}_{timestamp}.sql"

    env = {"PGPASSWORD": password}
    cmd = [
        "pg_dump",
        "-h", host,
        "-p", str(port),
        "-U", user,
        "-d", dbname,
        "-f", str(out_file)
    ]

    subprocess.run(cmd, env=env, check=True)
    return out_file


def dump_sqlite(db_path: Path, output_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"sqlite_{db_path.stem}_{timestamp}.db"
    shutil.copy2(db_path, out_file)
    return out_file
