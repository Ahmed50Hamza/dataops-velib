import os
import threading
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from dataops.storage import create_object_store_client, sync_warehouse_snapshot

app = FastAPI(title="Santé des données Vélib'", version="0.1.0")
_sync_lock = threading.Lock()


def _warehouse_path() -> Path:
    return Path(os.getenv("API_WAREHOUSE_PATH", "/data/api_warehouse.duckdb"))


def _refresh_warehouse() -> bool:
    if os.getenv("WAREHOUSE_SYNC_FROM_OBJECT_STORE", "false").lower() != "true":
        return _warehouse_path().exists()
    with _sync_lock:
        return sync_warehouse_snapshot(create_object_store_client(), _warehouse_path())


def _history() -> list[dict]:
    if not _refresh_warehouse():
        return []
    with duckdb.connect(str(_warehouse_path()), read_only=True) as connection:
        result = connection.execute(
            """
            select
                cast(snapshot_date as varchar),
                station_count,
                available_bikes,
                available_docks,
                bike_availability_rate,
                unavailable_station_count,
                cast(last_fetched_at as varchar)
            from daily_station_metrics
            order by snapshot_date desc
            limit 14
            """
        ).fetchall()
    return [
        {
            "snapshot_date": row[0],
            "station_count": row[1],
            "available_bikes": row[2],
            "available_docks": row[3],
            "bike_availability_rate": row[4],
            "unavailable_station_count": row[5],
            "last_fetched_at": row[6],
        }
        for row in result
    ]


def _data_status(history: list[dict]) -> tuple[str, str | None]:
    if not history:
        return "awaiting_first_run", None
    fetched_at = datetime.fromisoformat(history[0]["last_fetched_at"])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    age_hours = (datetime.now(UTC) - fetched_at).total_seconds() / 3600
    return ("healthy" if age_hours <= 36 else "stale"), history[0]["snapshot_date"]


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Santé des données Vélib'</title>
<style>
body{font:16px system-ui,sans-serif;max-width:900px;margin:3rem auto;padding:0 1rem;color:#172554}
h1{color:#0369a1}.cards{display:flex;gap:1rem;flex-wrap:wrap}.card{background:#f0f9ff;padding:1rem 1.5rem;border-radius:12px}
table{border-collapse:collapse;width:100%;margin-top:1.5rem}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #cbd5e1}
.muted{color:#475569}#status{font-weight:700}
</style></head><body>
<h1>Santé des données Vélib'</h1>
<p class="muted">Disponibilité quotidienne du réseau et état de fraîcheur de l'ingestion CityBikes.</p>
<p>État des données : <span id="status">chargement…</span></p>
<div class="cards"><div class="card">Dernier instantané<br><strong id="date">—</strong></div>
<div class="card">Stations observées<br><strong id="stations">—</strong></div>
<div class="card">Vélos disponibles<br><strong id="bikes">—</strong></div>
<div class="card">Taux de disponibilité<br><strong id="rate">—</strong></div></div>
<h2>Historique récent</h2><table><thead><tr><th>Date</th><th>Vélos</th><th>Places libres</th>
<th>Stations indisponibles</th></tr></thead><tbody id="rows"></tbody></table>
<script>
fetch('/api/metrics').then(r=>r.json()).then(data=>{
 document.querySelector('#status').textContent=data.data_status;
 if(!data.history.length)return;
 const latest=data.history[0];
 document.querySelector('#date').textContent=latest.snapshot_date;
 document.querySelector('#stations').textContent=latest.station_count;
 document.querySelector('#bikes').textContent=latest.available_bikes;
 document.querySelector('#rate').textContent=(latest.bike_availability_rate*100).toFixed(1)+' %';
 document.querySelector('#rows').innerHTML=data.history.map(x=>'<tr><td>'+x.snapshot_date+
 '</td><td>'+x.available_bikes+'</td><td>'+x.available_docks+'</td><td>'+
 x.unavailable_station_count+'</td></tr>').join('');
}).catch(()=>{document.querySelector('#status').textContent='indisponible'});
</script></body></html>"""


@app.get("/health")
def liveness() -> dict:
    return {"status": "ok"}


@app.get("/api/health")
def health() -> dict:
    history = _history()
    data_status, last_snapshot = _data_status(history)
    return {"service_status": "healthy", "data_status": data_status, "last_snapshot": last_snapshot}


@app.get("/api/metrics")
def metrics() -> dict:
    history = _history()
    data_status, last_snapshot = _data_status(history)
    return {
        "data_status": data_status,
        "last_snapshot": last_snapshot,
        "history": history,
    }
