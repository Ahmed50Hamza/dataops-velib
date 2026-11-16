select
    cast(snapshot_date as date) as snapshot_date,
    cast(station_id as varchar) as station_id,
    trim(cast(name as varchar)) as station_name,
    cast(latitude as double) as latitude,
    cast(longitude as double) as longitude,
    cast(free_bikes as integer) as free_bikes,
    cast(empty_slots as integer) as empty_slots,
    cast(fetched_at as timestamp) as fetched_at
from {{ source('raw', 'station_snapshots') }}
