import pandas as pd

from contact_energy_local_db import get_usage

weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
hour_intervals = [f'{i}:00-{i+1}:00' for i in range(23)]
hour_intervals.append("23:00-0:00")


def weekday_hour_pivot(start_date, end_date, row_id):
    usage = get_usage(start_date, end_date, row_id)
    usage['date'] = pd.to_datetime(usage[['year', 'month', 'day']])
    usage['weekday'] = usage['date'].dt.weekday
    pivot = usage[['hour', 'weekday', 'value']].groupby(by=['hour', 'weekday']).mean()
    pivot.reset_index(inplace=True)
    return pivot
