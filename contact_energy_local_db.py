import logging
import sqlite3

import pandas as pd

db_path = "contact_energy.db"


def get_account_contract_row_id(account_number, contract_id):
    meter = None
    c = sqlite3.connect(db_path)
    try:
        meter = pd.read_sql_query(
            sql="select ROWID from meter where account_number = ? and contract_id = ?",
            con=c,
            params=[account_number, contract_id],
        )
    except pd.errors.DatabaseError:
        logging.info(f"Create a new database \"{db_path}\".")
    if (meter is None) or meter.shape[0] == 0:
        meter = pd.DataFrame([
            {"account_number": account_number, "contract_id": contract_id}
        ])
        meter.to_sql(name="meter", con=c, index=False, if_exists="append")
        c.commit()
    meter = pd.read_sql_query(
        sql="select ROWID from meter where account_number = ? and contract_id = ?",
        con=c,
        params=[account_number, contract_id],
    )
    c.close()
    row_id = int(meter.loc[0, "rowid"])
    return row_id


def get_account_contract_list():
    c = sqlite3.connect(db_path)
    try:
        meter = pd.read_sql_table(table_name='meter', con=c)
    except pd.errors.DatabaseError:
        meter = pd.DataFrame(columns=['account_number', 'contract_id'])
    c.close()
    return meter


def get_usage_missing_dates(start_date, end_date, row_id):
    all_dates = pd.date_range(start=start_date, end=end_date, freq='1d')
    c = sqlite3.connect(db_path)
    try:
        exist_dates = pd.read_sql_query(
            sql="select distinct year, month, day from usage where date(printf("
                "'%04d-%02d-%02d', year, month, day)) between date(?) and date(?) "
                "and meter_id = ?",
            con=c,
            params=[start_date, end_date, row_id]
        )
    except pd.errors.DatabaseError:
        return all_dates
    c.close()
    exist_dates = pd.DatetimeIndex(pd.to_datetime(exist_dates))
    missing_dates = all_dates.difference(exist_dates)
    return missing_dates


def save_usage(usage, row_id):
    if usage is None:
        logging.warning("The usage data to save into database is empty, so this action "
                        "is abandoned.")
        return
    usage = pd.DataFrame(usage)
    usage = usage[['year', 'month', 'day', 'hour', 'value']]
    usage['value'] = usage['value'].astype(float)
    usage.insert(loc=0, column='meter_id', value=row_id)
    c = sqlite3.connect(db_path)
    usage.to_sql(name="usage", con=c, index=False, if_exists="append")
    c.close()
