import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dataops.ingest import fetch_payload, persist_snapshot
from dataops.storage import create_object_store_client, upload_object

PROJECT_ROOT = Path(os.getenv("APP_ROOT", Path(__file__).resolve().parents[2]))


def run_pipeline() -> int:
    warehouse_path = Path(os.getenv("WAREHOUSE_PATH", "/data/warehouse.duckdb"))
    payload = fetch_payload()
    station_count = persist_snapshot(payload, datetime.now(UTC).date(), warehouse_path)

    subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(PROJECT_ROOT / "dbt"),
            "--profiles-dir",
            str(PROJECT_ROOT / "dbt"),
        ],
        check=True,
        env={**os.environ, "WAREHOUSE_PATH": str(warehouse_path)},
    )

    client = create_object_store_client()
    upload_object(
        client,
        "warehouse/warehouse.duckdb",
        warehouse_path.read_bytes(),
        "application/octet-stream",
    )
    return station_count


if __name__ == "__main__":
    run_pipeline()
