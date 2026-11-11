from datetime import datetime, timezone
from pathlib import Path

import boto3


class S3Storage:
    def __init__(
        self,
        endpoint_url: str | None,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def upload_backup(self, file_path: Path, prefix: str = "backups") -> str:
        s3_key = f"{prefix}/{file_path.name}"
        self.client.upload_file(str(file_path), self.bucket, s3_key)
        return s3_key

    def enforce_retention(self, prefix: str, max_age_days: int):
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")

        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        if "Contents" not in resp:
            return

        now = datetime.now(timezone.utc)
        for obj in resp["Contents"]:
            last_modified = obj["LastModified"]
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=timezone.utc)
            age_days = (now - last_modified).days
            if age_days > max_age_days:
                self.client.delete_object(Bucket=self.bucket, Key=obj["Key"])
