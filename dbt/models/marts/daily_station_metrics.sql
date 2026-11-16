select
    snapshot_date,
    count(*) as station_count,
    sum(free_bikes) as available_bikes,
    sum(empty_slots) as available_docks,
    round(
        sum(free_bikes)::double / nullif(sum(free_bikes + empty_slots), 0),
        4
    ) as bike_availability_rate,
    count(*) filter (where free_bikes = 0 and empty_slots = 0) as unavailable_station_count,
    max(fetched_at) as last_fetched_at
from {{ ref('stg_station_snapshots') }}
group by snapshot_date
