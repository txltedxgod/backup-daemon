import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

import click
import schedule
import yaml

from .crypto import compress_file, encrypt_file
from .dumpers import dump_postgres, dump_sqlite
from .storage import S3Storage


def run_backup_job(config: dict):
    work_dir_cfg = config.get("work_dir")
    ctx = (
        nullcontext(Path(work_dir_cfg))
        if work_dir_cfg
        else tempfile.TemporaryDirectory(prefix="backup_daemon_")
    )

    s3 = S3Storage(
        endpoint_url=config.get("s3", {}).get("endpoint_url"),
        bucket=config["s3"]["bucket"],
        access_key=config["s3"]["access_key"],
        secret_key=config["s3"]["secret_key"],
        region=config.get("s3", {}).get("region", "us-east-1"),
    )

    key_hex = config.get("encryption_key_hex")
    prefixes: set[str] = set()

    with ctx as raw_dir:
        tmp_dir = Path(raw_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        for target in config.get("databases", []):
            db_type = target["type"]
            print(f"[*] Starting backup for {target['name']} ({db_type})...")

            if db_type == "postgres":
                f = dump_postgres(
                    target["host"],
                    target.get("port", 5432),
                    target["user"],
                    target["dbname"],
                    target["password"],
                    tmp_dir,
                )
            elif db_type == "sqlite":
                f = dump_sqlite(Path(target["path"]), tmp_dir)
            else:
                continue

            f = compress_file(f)
            if key_hex:
                f = encrypt_file(f, key_hex)

            prefix = target.get("s3_prefix", "databases")
            prefixes.add(prefix)
            s3_key = s3.upload_backup(f, prefix=prefix)
            print(f"[+] Backup uploaded successfully: {s3_key}")
            f.unlink(missing_ok=True)

    retention_days = config.get("retention_days", 30)
    for prefix in sorted(prefixes or {"databases"}):
        s3.enforce_retention(prefix, retention_days)


@click.command()
@click.option("-c", "--config", "config_file", default="config.yaml", help="Path to config yaml")
@click.option("--once", is_flag=True, help="Run backup once and exit")
def main(config_file: str, once: bool):
    with open(config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if once:
        run_backup_job(config)
        return

    schedule_time = config.get("schedule_time", "03:00")
    schedule.every().day.at(schedule_time).do(run_backup_job, config=config)

    print(f"[*] Backup daemon running. Scheduled daily at {schedule_time} UTC.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
