import socket
import sys
import webbrowser
from datetime import datetime, timedelta
from math import isnan

import pywebio
from flask import Flask
from pyecharts.charts import Bar, HeatMap
from pyecharts.options import LabelOpts, VisualMapOpts
from pywebio.platform.flask import webio_view

from contact_energy_analysis import *
from contact_energy_aws_lambda import ContactEnergyUsage
from contact_energy_local_db import *
from contact_energy_price import *

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,  # Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    # https://docs.python.org/3/library/logging.html#logrecord-attributes
    format="[%(levelname)s] %(message)s",
)


def validate_end_date(date_str):
    latest_date = datetime.now() - timedelta(days=3)
    input_date = datetime.strptime(date_str, "%Y-%m-%d")
    if input_date > latest_date:
        return "The date cannot be later than " + latest_date.strftime("%Y-%m-%d")


def validate_start_date(date_str):
    # Contact Energy is founded in 1996-01-01.
    earliest_date = datetime(1996, 1, 1)
    input_date = datetime.strptime(date_str, "%Y-%m-%d")
    if input_date < earliest_date:
        return "The date cannot be earlier than " + earliest_date.strftime("%Y-%m-%d")


def index():
    pywebio.output.put_markdown(
        "# Contact electricity usage\n"
        "Calculate electricity usage of Contact Energy account\n"
        "\n"
        "If finding any issue, "
        "please read more detailed information in the terminal. To raise the issue to "
        "the author at github, please attach these information.\n"
        "\n"
        "To use this program, **the user agrees** this program to store electricity "
        "usage data in a local database from their Contact Energy account. The data will "
        "not be sent to the program's author or any other online services. The user has "
        "the full control to their data.\n"
        "\n"
        "---\n"
        "Update data from Contact Energy and view analysis. [Enter](/get_data)\n"
        "\n"
        "Set unit price for your electricity meter. [Enter](/unit_price)\n"
        "\n"
        "View analysis. [Enter](/analyze)\n"
    )


def get_data():
    pywebio.output.put_link(name="Back", url="/")
    form1 = pywebio.input.input_group('Login', [
        pywebio.input.input(
            label="Username",
            type=pywebio.input.TEXT,
            required=True,
            name="username",
            help_text="Input username and password of Contact Energy account. This "
                      "program does not store username and password."
        ),
        pywebio.input.input(
            label="Password",
            type=pywebio.input.PASSWORD,
            required=True,
            name="password",
            help_text="Refer to the note of \"Username\"."
        ),
    ])
    api = ContactEnergyUsage(username=form1['username'], password=form1['password'])

    form2 = pywebio.input.input_group("Select account", [
        pywebio.input.select(
            label="Account number",
            # (label, value)
            options=[(v, v) for v in api.account_numbers_contract_id.keys()],
            required=True,
            name="account_number",
            help_text="If the user has multiple properties, please input the account "
                      "number and contract ID corresponding to the property to look up. "
                      "Otherwise, the user only have one property and these values have "
                      "only one option. The user can look up these numbers by signing "
                      "in Contact Energy official website."
        )
    ])

    form3 = pywebio.input.input_group("Collect data", [
        pywebio.input.select(
            label="Contract ID",
            options=[(v, v) for v in api.account_numbers_contract_id[
                form2['account_number']]],
            required=True,
            name="contract_id",
            help_text="Refer to the note of \"Account number\"."
        ),
        pywebio.input.input(
            label="Start date",
            type=pywebio.input.DATE,
            required=True,
            name="start_date",
            help_text="The earliest date is 1996-01-01. This date is included in the "
                      "period.",
            validate=validate_start_date,
        ),
        pywebio.input.input(
            label="End date",
            type=pywebio.input.DATE,
            required=True,
            name="end_date",
            help_text="The latest end date is today minus 3 days. This date is included "
                      "in the period.",
            validate=validate_end_date,
        ),
    ])
    row_id = get_account_contract_row_id(form2['account_number'], form3['contract_id'])
    missing_dates = get_usage_missing_dates(
        form3['start_date'], form3['end_date'], row_id)
    pywebio.output.put_text(
        "The program is getting electricity usage data from Contact Energy."
    )
    pywebio.output.put_progressbar(name="get_usage", init=0)
    progress_total = len(missing_dates)
    for i, date_ in enumerate(missing_dates):
        usage = api.get_usage(form2['account_number'], form3['contract_id'], date_)
        if usage is not None:
            save_usage(usage, row_id)
        progress_current = (i + 1) / progress_total
        pywebio.output.set_progressbar(name="get_usage", value=progress_current)
    pywebio.output.put_text(
        "The program has finished updating electricity usage data."
    )

    # Figure 1: bar
    fig1 = Bar()
    fig1.add_xaxis(all_plans)
    # total electricity price
    total_price = get_total_price(form3['start_date'], form3['end_date'], row_id)
    account_number = form2['account_number']
    contract_id = form3['contract_id']
    fig1.add_yaxis(
        f"Account number: {account_number}\nContract ID: {contract_id}",
        [total_price.get(plan) for plan in all_plans]
    )
    pywebio.output.put_markdown(
        "# Total electricity cost (including GST)\n"
        "\n"
        "The program's calculation is slightly different to Contact Energy's "
        "bill, because they round both peak (or charged) usage and off-peak "
        "(or free) usage to integer kWh. This program's calculation will be "
        "more accurate. The difference should be smaller than 1kWh average "
        "unit price of your plan (usually smaller than $1). \n"
        "\n"
        "Unit: NZD"
    )
    pywebio.output.put_html(fig1.render_notebook())

    # Figure 2: heatmap
    pywebio.output.put_markdown(
        "# Temporal electricity usage\n"
        "\n"
        "The average electricity usage for each weekday and intraday 1-hour interval.\n"
        "\n"
        "Unit: kWh"
    )
    fig2 = HeatMap()
    fig2.add_xaxis(hour_intervals)
    pivot = weekday_hour_pivot(form3['start_date'], form3['end_date'], row_id)
    fig2.add_yaxis(
        f"Account number: {account_number}\nContract ID: {contract_id}",
        weekdays,
        pivot.round(2).values.tolist(),
        label_opts=LabelOpts(is_show=True, position="inside"),
    )
    fig2.set_global_opts(
        visualmap_opts=VisualMapOpts(min_=0, max_=pivot['value'].max())
    )
    pywebio.output.put_html(fig2.render_notebook())


def unit_price():
    pywebio.output.put_link(name="Back", url="/")
    all_meters = get_account_contract_list()
    all_meters_options = [
        (f"Account number: {row['account_number']}, Contract ID: {row['contract_id']}",
         row['rowid']) for _, row in all_meters.iterrows()
    ]
    # select the meter
    form1 = pywebio.input.input_group("Select meter", [
        pywebio.input.select(
            label="Meter",
            options=all_meters_options,
            name="row_id",
            required=True
        ),
    ])
    row_id = form1['row_id']

    existed_unit_price = get_unit_price(row_id)
    existed_unit_price = {k: None if isnan(v) else v
                          for k, v in existed_unit_price.items()}
    pywebio.output.put_markdown(
        "---\n"
        "Default price is for the non-rural area low user in Auckland, collected on "
        "2024-06-17. You cannot leave some fields blank, so please copy the default "
        "value if you don't know and won't consider some plans.\n"
    )
    form2 = pywebio.input.input_group("Unit price (without GST)", [
        pywebio.input.input(
            label="Good Weekends electricity rate",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["weekend_price"]}',
            value=existed_unit_price["weekend_price"],
            name="weekend_price",
            required=True,
            help_text="Saturday and Sunday 9:00-17:00 is free. "
                      "Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Weekends fixed daily fee",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["weekend_fixed"]}',
            value=existed_unit_price["weekend_fixed"],
            name="weekend_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Good Nights electricity rate",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["night_price"]}',
            value=existed_unit_price["night_price"],
            name="night_price",
            required=True,
            help_text="Everyday 21:00-0:00 is free. "
                      "Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Nights fixed daily fee",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["night_fixed"]}',
            value=existed_unit_price["night_fixed"],
            name="night_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Broadband electricity rate",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["broadband_price"]}',
            value=existed_unit_price["broadband_price"],
            name="broadband_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Broadband electricity authority levy",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["broadband_levy"]}',
            value=existed_unit_price["broadband_levy"],
            name="broadband_levy",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Broadband fixed daily fee",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["broadband_fixed"]}',
            value=existed_unit_price["broadband_fixed"],
            name="broadband_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Good Charge electricity rate (daytime 7:00-21:00)",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["charge_day_price"]}',
            value=existed_unit_price["charge_day_price"],
            name="charge_day_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Charge electricity rate (night 21:00-7:00)",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["charge_night_price"]}',
            value=existed_unit_price["charge_night_price"],
            name="charge_night_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Charge fixed daily fee",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["charge_fixed"]}',
            value=existed_unit_price["charge_fixed"],
            name="charge_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Basic electricity rate",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["basic_price"]}',
            value=existed_unit_price["basic_price"],
            name="basic_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Basic electricity authority levy",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["basic_levy"]}',
            value=existed_unit_price["basic_levy"],
            name="basic_levy",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Basic fixed daily fee",
            type=pywebio.input.FLOAT,
            placeholder=f'Default: {default_unit_price["basic_fixed"]}',
            value=existed_unit_price["basic_fixed"],
            name="basic_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
    ])
    save_unit_price(row_id, **form2)
    pywebio.output.put_text("Unit prices of the current meter are saved to the database.")


def checkbox_non_empty(selected_options):
    if len(selected_options) == 0:
        return "At least select one option."


def analyze():
    pywebio.output.put_link(name="Back", url="/")
    all_meters = get_account_contract_list()
    all_meters_options = [
        (f"Account number: {row['account_number']}, Contract ID: {row['contract_id']}",
         row['rowid']) for _, row in all_meters.iterrows()
    ]
    # select the meter
    form1 = pywebio.input.input_group("Selete meters", [
        pywebio.input.checkbox(
            label="Meters",
            options=all_meters_options,
            name="rows_id",
            required=True,
            help_text="Select all meters to compare plans for.",
            validate=checkbox_non_empty,
        ),
        pywebio.input.input(
            label="Start date",
            type=pywebio.input.DATE,
            required=True,
            name="start_date",
            help_text="The earliest date is 1996-01-01. The analysis is based on the "
                      "historical data from \"Start date\" to \"End date\" (include "
                      "boundary).",
            validate=validate_start_date,
        ),
        pywebio.input.input(
            label="End date",
            type=pywebio.input.DATE,
            required=True,
            name="end_date",
            help_text="The latest end date is today minus 3 days.",
            validate=validate_end_date,
        ),
    ])
    rows_id = form1['rows_id']

    # Figure 1: bar
    fig1 = Bar()
    fig1.add_xaxis(all_plans)
    for row_id in rows_id:
        # total electricity price
        total_price = get_total_price(form1['start_date'], form1['end_date'], row_id)
        account_number = all_meters.loc[
            all_meters['rowid'] == row_id, 'account_number'][0]
        contract_id = all_meters.loc[all_meters['rowid'] == row_id, 'contract_id'][0]
        fig1.add_yaxis(
            f"Account number: {account_number}\nContract ID: {contract_id}",
            [total_price.get(plan) for plan in all_plans]
        )
    pywebio.output.put_markdown(
        "# Total electricity cost (including GST)\n"
        "\n"
        "The program's calculation is slightly different to Contact Energy's "
        "bill, because they round both peak (or charged) usage and off-peak "
        "(or free) usage to integer kWh. This program's calculation will be "
        "more accurate. The difference should be smaller than 1kWh average "
        "unit price of your plan (usually smaller than $1). \n"
        "\n"
        "Unit: NZD"
    )
    pywebio.output.put_html(fig1.render_notebook())

    # Figure 2: heatmap
    pywebio.output.put_markdown(
        "# Temporal electricity usage\n"
        "\n"
        "The average electricity usage for each weekday and intraday 1-hour interval.\n"
        "\n"
        "Unit: kWh"
    )
    for row_id in rows_id:
        fig2 = HeatMap()
        fig2.add_xaxis(hour_intervals)
        pivot = weekday_hour_pivot(form1['start_date'], form1['end_date'], row_id)
        account_number = all_meters.loc[
            all_meters['rowid'] == row_id, 'account_number'][0]
        contract_id = all_meters.loc[all_meters['rowid'] == row_id, 'contract_id'][0]
        fig2.add_yaxis(
            f"Account number: {account_number}\nContract ID: {contract_id}",
            weekdays,
            pivot.round(2).values.tolist(),
            label_opts=LabelOpts(is_show=True, position="inside"),
        )

        fig2.set_global_opts(
            visualmap_opts=VisualMapOpts(min_=0, max_=pivot['value'].max())
        )
        pywebio.output.put_html(fig2.render_notebook())


app.add_url_rule(rule='/', endpoint='index', view_func=webio_view(index),
                 methods=['GET', 'POST', 'OPTIONS'])
app.add_url_rule(rule='/get_data', endpoint='get_data', view_func=webio_view(get_data),
                 methods=['GET', 'POST', 'OPTIONS'])
app.add_url_rule(rule='/unit_price', endpoint='unit_price',
                 view_func=webio_view(unit_price), methods=['GET', 'POST', 'OPTIONS'])
app.add_url_rule(rule='/analyze', endpoint='analyze', view_func=webio_view(analyze),
                 methods=['GET', 'POST', 'OPTIONS'])


def find_available_port(start_port: int, tries: int = 100):
    """
    Find the first available port from {start_port} to {start_port + tries}
    :param start_port: The port that the program starts to scan, if it's occupied, the
    program will scan {start_port + 1}. If it's occupied again, try the next one...
    :param tries: Default 100, the maximum trying times from the start port.
    :return:
    """
    for i in range(tries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", start_port + i))
            s.close()
            return start_port + i
        except OSError:
            pass
    raise Exception(f"Tried {tries} times, no available port from {start_port} to "
                    f"{start_port + tries}.")


if __name__ == '__main__':
    port = find_available_port(5000)
    webbrowser.open_new_tab(f'http://localhost:{port}')
    app.run(port=port)
