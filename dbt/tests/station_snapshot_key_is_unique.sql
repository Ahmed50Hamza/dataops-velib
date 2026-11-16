select snapshot_date, station_id
from {{ ref('stg_station_snapshots') }}
group by snapshot_date, station_id
having count(*) > 1
