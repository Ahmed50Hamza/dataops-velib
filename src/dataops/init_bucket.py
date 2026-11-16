import os

from botocore.exceptions import ClientError

from dataops.storage import create_object_store_client


def main() -> None:
    client = create_object_store_client()
    bucket = os.getenv("OBJECT_STORE_BUCKET", "dataops")
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code not in ("404", "NoSuchBucket", "NotFound"):
            raise
        client.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={
                "LocationConstraint": os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
            },
        )


if __name__ == "__main__":
    main()
