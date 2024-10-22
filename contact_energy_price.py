import sqlite3
import pandas as pd
import numpy as np

db_path = "contact_energy.db"
gst_rate = 0.15
# low user rate: 2024-06-17 before GST, NZ cents per kWh
default_unit_price = {
    "weekend_price": 23.4,  # except Sat Sun 9:00-17:00
    "weekend_fixed": 90,
    "night_price": 30.2,  # except 21:00-0:00
    "night_fixed": 90,
    "broadband_price": 24.4,
    "broadband_fixed": 90,
    "broadband_levy": 0.16,
    "charge_day_price": 28.3,  # 7:00-21:00
    "charge_night_price": 14.1,
    "charge_fixed": 90,
    "basic_levy": 0.16,
    "basic_fixed": 90,
    "basic_price": 24.4,
}
all_plans = ['weekend', 'night', 'broadband', 'charge', 'basic']


def get_unit_price(row_id) -> dict:
    # although constants, intended not expose to outer scope
    # believe compiler or runtime can optimize
    plans_charged_items = \
        pd.DataFrame(data=list(default_unit_price.keys()), columns=['name'])
    c = sqlite3.connect(db_path)
    try:
        price = pd.read_sql_query(
            sql="select name, price from price where meter_id = ?",
            con=c,
            params=[row_id]
        )
        price = pd.merge(plans_charged_items, price, on='name', how='left')
    except pd.errors.DatabaseError:
        price = plans_charged_items.copy()
        price['price'] = np.nan
    c.close()
    # Because the template is left joined, it's guaranteed there is no missing keys.
    price = dict(zip(price['name'], price['price']))
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
    price.insert(loc=0, column='meter_id', value=row_id)
    price.to_sql(name='price', con=c, if_exists='append', index=False)
    c.close()


def get_total_price(start_date, end_date, usage, unit_price):
    """
    Calculate total electricity price for all Contact Energy plans in a specific period
    :param start_date: Start date of the period (include this date)
    :param end_date: End date of the period (include this date)
    :param usage: Hourly electricity usage table, which includes columns of
        ['year', 'month', 'day', 'hour', 'value']
        where 'value' is electricity usage in the corresponding hour in unit of kWh
    :param unit_price: Unit price dictionary, where keys are fixed and the same as
        variable "default_unit_price"; values are allowed to be "pd.NA"
    :return:
    """
    total_price_excl_gst = {}
    total_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
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
    total_price = {k: round(float(v) * (1 + gst_rate) / 100, 2)
                   for k, v in total_price_excl_gst.items()}
    return total_price
