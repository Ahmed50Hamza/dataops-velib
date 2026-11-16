from dataops.storage import create_object_store_client


def test_minio_client_uses_path_style(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://minio:9000")

    client = create_object_store_client()

    assert client.meta.config.s3["addressing_style"] == "path"
