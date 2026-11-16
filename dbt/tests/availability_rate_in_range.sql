select *
from {{ ref('daily_station_metrics') }}
where bike_availability_rate < 0
   or bike_availability_rate > 1
