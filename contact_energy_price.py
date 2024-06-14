import logging
import sqlite3

import pandas as pd

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
    "bach_price": 44.1,
    "bach_levy": 0.16,
}
default_unit_price = pd.DataFrame(
    list(default_unit_price.items()), columns=['name', 'price'])


def get_unit_price(row_id):
    c = sqlite3.connect(db_path)
    price = None
    try:
        price = pd.read_sql_query(
            sql="select name, price from price where meter_id = ?",
            con=c,
            params=[row_id]
        )
    except pd.errors.DatabaseError:
        pass
    c.close()
    if (price is None) or price.shape[0] == 0:
        logging.warning("The unit price for the current account is not configured, so "
                        "the default values are applied.")
        price = default_unit_price.copy()
    # There lacks a high efficient method to judge whether "name" column of price and
    # default price is the same.
    # "pd.testing.assert_series_equal" order matters, raise an error instead of returning
    # True or False.
    # Comparing "set" is not a "pandas" function.
    # Therefore, "elif price['name'] and default_price['name'] exactly match" is not
    # implemented.
    else:
        price = pd.merge(default_unit_price, price, on='name', how='left',
                         suffixes=('_default', ''))
        price['price'] = price['price'].combine_first(price['price_default'])
        price = price[['name', 'price']].drop_duplicates(subset='name')  # keep='first'
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


def get_total_price(start_date, end_date, row_id):
    total_price_excl_gst = {
        "weekend": 0,
        "night": 0,
        "broadband": 0,
        "charge": 0,
        "basic": 0,
        "bach": 0,
    }
    c = sqlite3.connect(db_path)
    usage = None
    try:
        usage = pd.read_sql_query(
            sql="select * from usage where date(printf('%04d-%02d-%02d', year, month, "
                "day)) between date(?) and date(?) and meter_id = ?",
            con=c,
            params=[start_date, end_date, row_id]
        )
    except pd.errors.DatabaseError:
        logging.warning(
            "The table \"usage\" does not exist. Please start getting usage data of "
            "your first meter, or extend the start and end date."
        )
    if (usage is None) or usage.shape[0] == 0:
        logging.warning(
            "No usage data for the current meter, or please extend the start and end "
            "date."
        )
        c.close()
        return total_price_excl_gst
    unit_price = get_unit_price(row_id)
    # Because the template is left joined, it's guaranteed there is no missing keys.
    unit_price = dict(zip(unit_price['name'], unit_price['price']))
    # calc total price
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
    total_price_excl_gst['bach'] = usage['value'].sum() * (
            unit_price['bach_price'] + unit_price['bach_levy'])
    # add GST, convert cents to dollars
    total_price = {k: round(float(v) * (1 + gst_rate) / 100, 2)
                   for k, v in total_price_excl_gst.items()}
    logging.info("The program's calculation is slightly different to Contact Energy's "
                 "bill, because they round both peak (or charged) usage and off-peak "
                 "(or free) usage to integer kWh. This program's calculation will be "
                 "more accurate. The difference should be smaller than 1kWh average "
                 "unit price of your plan (usually smaller than $1).")
    return total_price
