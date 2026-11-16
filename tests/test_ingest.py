from datetime import date

import duckdb
import jsonschema
import pytest

from dataops.ingest import fetch_payload, persist_snapshot, validate_payload


def sample_payload(free_bikes=4):
    return {
        "network": {
            "id": "velib",
            "stations": [
                {
                    "id": "station-1",
                    "name": "Test station",
                    "latitude": 48.85,
                    "longitude": 2.35,
                    "free_bikes": free_bikes,
                    "empty_slots": 12,
                }
            ],
        }
    }


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]


def test_contract_rejects_invalid_station():
    payload = sample_payload()
    payload["network"]["stations"][0]["free_bikes"] = -1

    with pytest.raises(jsonschema.ValidationError):
        validate_payload(payload)


def test_fetch_uses_default_endpoint_when_override_is_empty(monkeypatch):
    requested_urls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return sample_payload()

    def fake_get(url, timeout):
        requested_urls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setenv("CITYBIKES_NETWORK", "velib")
    monkeypatch.setenv("CITYBIKES_API_URL", "")
    monkeypatch.setattr("dataops.ingest.requests.get", fake_get)

    fetch_payload()

    assert requested_urls == [("https://api.citybik.es/v2/networks/velib", 30)]


def test_ingestion_rejects_duplicate_station_ids(tmp_path):
    payload = sample_payload()
    payload["network"]["stations"].append(payload["network"]["stations"][0])

    with pytest.raises(ValueError, match="unique station IDs"):
        persist_snapshot(payload, date(2026, 1, 2), tmp_path / "warehouse.duckdb", FakeS3())


def test_ingestion_is_idempotent_for_same_day(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_BUCKET", "test-bucket")
    client = FakeS3()
    warehouse = tmp_path / "warehouse.duckdb"

    persist_snapshot(sample_payload(4), date(2026, 1, 2), warehouse, client)
    persist_snapshot(sample_payload(7), date(2026, 1, 2), warehouse, client)

    with duckdb.connect(str(warehouse), read_only=True) as connection:
        rows = connection.execute(
            "select count(*), max(free_bikes) from raw_station_snapshots"
        ).fetchone()
    assert rows == (1, 7)
    assert len(client.objects) == 1
    assert next(iter(client.objects))[1].endswith("2026-01-02.json")
