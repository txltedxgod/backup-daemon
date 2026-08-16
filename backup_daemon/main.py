import click
import yaml
import time
import schedule
from pathlib import Path
from .dumpers import dump_postgres, dump_sqlite
from .crypto import compress_file, encrypt_file
from .storage import S3Storage


def run_backup_job(config: dict):
    tmp_dir = Path("/tmp/backups")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    s3 = S3Storage(
        endpoint_url=config.get("s3", {}).get("endpoint_url"),
        bucket=config["s3"]["bucket"],
        access_key=config["s3"]["access_key"],
        secret_key=config["s3"]["secret_key"],
    )

    key_hex = config.get("encryption_key_hex")

    for target in config.get("databases", []):
        db_type = target["type"]
        print(f"[*] Starting backup for {target['name']} ({db_type})...")

        if db_type == "postgres":
            f = dump_postgres(
                target["host"], target.get("port", 5432),
                target["user"], target["dbname"], target["password"], tmp_dir
            )
        elif db_type == "sqlite":
            f = dump_sqlite(Path(target["path"]), tmp_dir)
        else:
            continue

        f = compress_file(f)
        if key_hex:
            f = encrypt_file(f, key_hex)

        s3_key = s3.upload_backup(f, prefix=target.get("s3_prefix", "databases"))
        print(f"[+] Backup uploaded successfully: {s3_key}")
        f.unlink(missing_ok=True)

    retention_days = config.get("retention_days", 30)
    s3.enforce_retention("databases", retention_days)


@click.command()
@click.option("-c", "--config", "config_file", default="config.yaml", help="Path to config yaml")
@click.option("--once", is_flag=True, help="Run backup once and exit")
def main(config_file: str, once: bool):
    with open(config_file) as f:
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
