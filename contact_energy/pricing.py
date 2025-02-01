import sqlite3
import pandas as pd
import numpy as np

db_path = "contact_energy.db"
gst_rate = 0.15


def get_unit_price(row_id) -> dict:
    c = sqlite3.connect(db_path)
    try:
        price = pd.read_sql_query(
            sql="select name, price from price where meter_id = ?",
            con=c,
            params=[row_id]
        )
        price = price.set_index('name').to_dict()['price']
    except pd.errors.DatabaseError:
        price = {}
    c.close()
    return price


def save_unit_price(row_id, **kwargs):
    c = sqlite3.connect(db_path)
    exist_table_price = pd.read_sql_query(
        sql="SELECT name FROM sqlite_master WHERE type='table' AND name='price'",
        con=c,
    )
    if exist_table_price.shape[0] > 0:
        c.execute("delete from price where meter_id = ?", (row_id,))
        c.commit()
    price = pd.DataFrame(list(kwargs.items()), columns=['name', 'price'])
    price.dropna(inplace=True)
    price.insert(loc=0, column='meter_id', value=row_id)
    price.to_sql(name='price', con=c, if_exists='append', index=False)
    c.close()


def get_total_price(usage, unit_price):
    """
    Calculate total electricity price for all Contact Energy plans in a specific period
    :param usage: Hourly electricity usage table, which includes columns of
        ['year', 'month', 'day', 'hour', 'value']
        where 'value' is electricity usage in the corresponding hour in unit of kWh
    :param unit_price: Unit price dictionary, values may be NaN
    :return:
    """
    total_price_excl_gst = {}
    dates = pd.to_datetime(usage[['year', 'month', 'day']])
    start_date = dates.min()
    end_date = dates.max()
    total_days = round((end_date - start_date) / pd.Timedelta(days=1)) + 1

    usage['date'] = pd.to_datetime(usage[['year', 'month', 'day']])
    usage['weekend_is_free'] = ((usage['date'].dt.weekday > 4) & (usage['hour'] >= 9) &
                                (usage['hour'] < 17))
    total_price_excl_gst['weekend'] = \
        (usage.loc[~usage['weekend_is_free'], 'value'].sum() * unit_price['weekend_price']
         + total_days * unit_price['weekend_fixed'])
    usage['night_is_free'] = usage['hour'] >= 21
    total_price_excl_gst['night'] = \
        (usage.loc[~usage['night_is_free'], 'value'].sum() * unit_price['night_price'] +
         total_days * unit_price['night_fixed'])
    total_price_excl_gst['broadband'] = \
        (usage['value'].sum() * (
                unit_price['broadband_price'] + unit_price['broadband_levy']) +
         total_days * unit_price['broadband_fixed'])
    usage['charge_is_day'] = (usage['hour'] >= 7) & (usage['hour'] < 21)
    total_price_excl_gst['charge'] = \
        usage['value'].sum() * unit_price['charge_night_price'] + \
        (usage['value'] * usage['charge_is_day']).sum() * (
            unit_price['charge_day_price'] - unit_price['charge_night_price']) + \
        total_days * unit_price['charge_fixed']
    total_price_excl_gst['basic'] = \
        (usage['value'].sum() * (
                unit_price['basic_price'] + unit_price['basic_levy']) +
         total_days * unit_price['basic_fixed'])
    # add GST, convert cents to dollars
    total_price = {}
    for k, v in total_price_excl_gst.items():
        if np.isnan(v):
            continue
        total_price[k] = round(float(v) * (1 + gst_rate) / 100, 2)
    return total_price
