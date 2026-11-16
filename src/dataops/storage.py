import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

_synced_warehouse_etag: str | None = None


def create_object_store_client():
    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    options = (
        {
            "endpoint_url": endpoint_url,
            "config": Config(s3={"addressing_style": "path"}),
        }
        if endpoint_url
        else {}
    )
    return boto3.client("s3", **options)


def upload_object(client, key: str, body: bytes, content_type: str) -> None:
    client.put_object(
        Bucket=os.getenv("OBJECT_STORE_BUCKET", "dataops"),
        Key=key,
        Body=body,
        ContentType=content_type,
    )


def sync_warehouse_snapshot(client, destination: Path) -> bool:
    global _synced_warehouse_etag
    bucket = os.getenv("OBJECT_STORE_BUCKET", "dataops")
    key = "warehouse/warehouse.duckdb"
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        metadata = client.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise

    etag = metadata["ETag"]
    if etag == _synced_warehouse_etag and destination.exists():
        return True

    temporary_path = destination.with_suffix(destination.suffix + ".tmp")
    try:
        client.download_file(bucket, key, str(temporary_path))
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    _synced_warehouse_etag = etag
    return True
