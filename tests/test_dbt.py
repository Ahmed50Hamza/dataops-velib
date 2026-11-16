import os
import subprocess
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def test_dbt_builds_layered_models(tmp_path):
    warehouse = tmp_path / "models.duckdb"
    with duckdb.connect(str(warehouse)) as connection:
        connection.execute(
            """
            create table raw_station_snapshots (
                snapshot_date date, station_id varchar, name varchar,
                latitude double, longitude double, free_bikes integer,
                empty_slots integer, fetched_at timestamp
            )
            """
        )
        connection.execute(
            """
            insert into raw_station_snapshots values
            ('2026-01-02', 'station-1', 'A', 48.85, 2.35, 4, 12, '2026-01-02 06:00:00'),
            ('2026-01-02', 'station-2', 'B', 48.86, 2.36, 6, 8, '2026-01-02 06:00:00')
            """
        )

    subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
        ],
        check=True,
        cwd=ROOT,
        env={**os.environ, "WAREHOUSE_PATH": str(warehouse)},
        capture_output=True,
        text=True,
    )

    with duckdb.connect(str(warehouse), read_only=True) as connection:
        metrics = connection.execute(
            "select station_count, available_bikes, available_docks "
            "from daily_station_metrics"
        ).fetchone()
    assert metrics == (2, 10, 20)
