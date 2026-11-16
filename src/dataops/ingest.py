import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import jsonschema
import requests

from dataops.storage import create_object_store_client, upload_object

PROJECT_ROOT = Path(os.getenv("APP_ROOT", Path(__file__).resolve().parents[2]))
CONTRACT_PATH = PROJECT_ROOT / "contracts" / "citybikes_velib.schema.json"


def validate_payload(payload: dict[str, Any]) -> None:
    with CONTRACT_PATH.open(encoding="utf-8") as contract_file:
        contract = json.load(contract_file)
    jsonschema.validate(instance=payload, schema=contract)


def fetch_payload() -> dict[str, Any]:
    network = os.getenv("CITYBIKES_NETWORK", "velib")
    endpoint = os.getenv(
        "CITYBIKES_API_URL"
    ) or f"https://api.citybik.es/v2/networks/{network}"
    response = requests.get(endpoint, timeout=30)
    response.raise_for_status()
    payload = response.json()
    validate_payload(payload)
    return payload


def persist_snapshot(
    payload: dict[str, Any],
    snapshot_date: date,
    warehouse_path: str | Path,
    s3_client=None,
) -> int:
    validate_payload(payload)
    network = payload["network"]
    stations = network["stations"]
    station_ids = [station["id"] for station in stations]
    if len(station_ids) != len(set(station_ids)):
        raise ValueError("The source contract requires unique station IDs per snapshot.")
    fetched_at = datetime.now(UTC).replace(tzinfo=None)
    warehouse = Path(warehouse_path)
    warehouse.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(warehouse)) as connection:
        connection.execute(
            """
            create table if not exists raw_station_snapshots (
                snapshot_date date not null,
                station_id varchar not null,
                name varchar not null,
                latitude double not null,
                longitude double not null,
                free_bikes integer not null,
                empty_slots integer not null,
                fetched_at timestamp not null,
                primary key (snapshot_date, station_id)
            )
            """
        )
        connection.executemany(
            """
            insert into raw_station_snapshots values (?, ?, ?, ?, ?, ?, ?, ?)
            on conflict (snapshot_date, station_id) do update set
                name = excluded.name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                free_bikes = excluded.free_bikes,
                empty_slots = excluded.empty_slots,
                fetched_at = excluded.fetched_at
            """,
            [
                (
                    snapshot_date,
                    str(station["id"]),
                    station["name"],
                    station["latitude"],
                    station["longitude"],
                    station["free_bikes"],
                    station["empty_slots"],
                    fetched_at,
                )
                for station in stations
            ],
        )

    client = s3_client or create_object_store_client()
    raw_key = f"raw/citybikes/{network['id']}/{snapshot_date.isoformat()}.json"
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    upload_object(client, raw_key, raw_body, "application/json")
    return len(stations)
