import sqlite3

import pandas as pd

db_path = "contact_energy.db"
gst_rate = 0.15
all_plans = ['weekend', 'night', 'broadband', 'charge', 'basic']
plans_default_items = pd.DataFrame({'name': [
    'weekend_price', 'weekend_fixed', 'night_price', 'night_fixed', 'broadband_price',
    'broadband_fixed', 'broadband_levy', 'charge_day_price', 'charge_night_price',
    'charge_fixed', 'basic_levy', 'basic_fixed', 'basic_price'
]})


def upgrade_price_table_1():
    c = sqlite3.connect(db_path)
    try:
        r = c.cursor()
        r.execute(f"PRAGMA table_info(price);")
        columns = r.fetchall()
    except sqlite3.OperationalError:
        columns = []
    if 'announced_date' not in columns:
        price = pd.read_csv("price.csv")
        price.to_sql(name='price', con=c, if_exists='replace', index=False)
    c.close()


def get_unit_price(announced_date, is_low_user) -> dict:
    # although constants, intended not expose to outer scope
    # believe compiler or runtime can optimize
    c = sqlite3.connect(db_path)
    price = pd.read_sql_query(
        sql="select name, price from price where announced_date = ? and "
            "is_low_user = ?",
        con=c,
        params=[announced_date, is_low_user]
    )
    price = pd.merge(plans_default_items, price, on='name', how='left')
    c.close()
    # Because the template is left joined, it's guaranteed there is no missing keys.
    price = dict(zip(price['name'], price['price']))
    return price


def exists_unit_price(announced_date, is_low_user) -> bool:
    c = sqlite3.connect(db_path)
    price = pd.read_sql_query(
        sql="select count(*) from price where announced_date = ? and "
            "is_low_user = ?",
        con=c,
        params=[announced_date, is_low_user]
    )
    c.close()
    return price.iloc[0, 0] > 0


def list_announced_dates():
    c = sqlite3.connect(db_path)
    price = pd.read_sql_query(
        sql="select distinct(announced_date) from price",
        con=c,
    )
    c.close()
    return price['announced_date'].tolist()


def save_unit_price(announced_date, is_low_user, **kwargs):
    c = sqlite3.connect(db_path)
    exist_table_price = pd.read_sql_query(
        sql="SELECT name FROM sqlite_master WHERE type='table' AND name='price'",
        con=c,
    )
    if exist_table_price.shape[0] > 0:
        c.execute("delete from price where announced_date = ? and "
            "is_low_user = ?", (announced_date, is_low_user))
        c.commit()
    price = pd.DataFrame(list(kwargs.items()), columns=['name', 'price'])
    price.insert(loc=0, column='announced_date', value=announced_date)
    price.insert(loc=1, column='is_low_user', value=is_low_user)
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
