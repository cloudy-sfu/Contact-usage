import socket
import sys
import webbrowser
from datetime import datetime, timedelta

import pywebio
from flask import Flask
from pyecharts.charts import Bar, HeatMap
from pyecharts.options import LabelOpts, VisualMapOpts
from pywebio.platform.flask import webio_view

from contact_energy.aws_lambda import ContactEnergyUsage
from local_db import *
from contact_energy.pricing import *

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,  # Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL
    stream=sys.stdout,
    format="%(levelname).1s %(message)s",
)

def get_unit_price_form(unit_price: dict):
    form6 = pywebio.input.input_group("Unit price (without GST)", [
        pywebio.input.input(
            label="Good Weekends electricity rate",
            type=pywebio.input.FLOAT,
            value=unit_price["weekend_price"],
            name="weekend_price",
            required=True,
            help_text="Saturday and Sunday 9:00-17:00 is free. "
                      "Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Weekends fixed daily fee",
            type=pywebio.input.FLOAT,
            value=unit_price["weekend_fixed"],
            name="weekend_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Good Nights electricity rate",
            type=pywebio.input.FLOAT,
            value=unit_price["night_price"],
            name="night_price",
            required=True,
            help_text="Everyday 21:00-0:00 is free. "
                      "Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Nights fixed daily fee",
            type=pywebio.input.FLOAT,
            value=unit_price["night_fixed"],
            name="night_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Broadband electricity rate",
            type=pywebio.input.FLOAT,
            value=unit_price["broadband_price"],
            name="broadband_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Broadband electricity authority levy",
            type=pywebio.input.FLOAT,
            value=unit_price["broadband_levy"],
            name="broadband_levy",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Broadband fixed daily fee",
            type=pywebio.input.FLOAT,
            value=unit_price["broadband_fixed"],
            name="broadband_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Good Charge electricity rate (daytime 7:00-21:00)",
            type=pywebio.input.FLOAT,
            value=unit_price["charge_day_price"],
            name="charge_day_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Charge electricity rate (night 21:00-7:00)",
            type=pywebio.input.FLOAT,
            value=unit_price["charge_night_price"],
            name="charge_night_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Good Charge fixed daily fee",
            type=pywebio.input.FLOAT,
            value=unit_price["charge_fixed"],
            name="charge_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
        pywebio.input.input(
            label="Basic electricity rate",
            type=pywebio.input.FLOAT,
            value=unit_price["basic_price"],
            name="basic_price",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Basic electricity authority levy",
            type=pywebio.input.FLOAT,
            value=unit_price["basic_levy"],
            name="basic_levy",
            required=True,
            help_text="Unit: New Zealand cents per kWh",
        ),
        pywebio.input.input(
            label="Basic fixed daily fee",
            type=pywebio.input.FLOAT,
            value=unit_price["basic_fixed"],
            name="basic_fixed",
            required=True,
            help_text="Unit: New Zealand cents per day",
        ),
    ])
    return form6


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
        "# Contact usage\n"
        "Compare electricity prices between Contact Energy electricity plans\n"
        "\n"
        "Electricity usage data from Contact Energy account will be stored in a local "
        "database. It will not be sent to the program's author or any other address "
        "on the Internet.\n"
        "\n"
        "**Shortcuts**:\n"
        "\n"
        "Set unit price for specific meter: [Enter](/unit_price)\n"
        "\n"
        "View analysis only: [Enter](/analyze)\n"
        "\n"
        "---\n"
    )
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

    # locate the meter
    row_id = get_account_contract_row_id(form2['account_number'], form3['contract_id'])

    # write usage to the database (update usage)
    missing_dates = get_missing_dates_in_usage(
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

    # read usage from the database (after updated)
    usage = get_usage(form3['start_date'], form3['end_date'], row_id)
    unit_price_ = get_unit_price(row_id)

    # analyze electricity price
    draw_charts([{
        'account_number': form2['account_number'],
        'contract_id': form3['contract_id'],
        'usage': usage,
        'unit_price': unit_price_,
    }])


def view_unit_price():
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
        pywebio.input.checkbox(
            name="copy_from_another_meter",
            type=pywebio.input.CHECKBOX,
            options=[
                ("Copy from another meter", "yes"),
            ],
        ),
    ])
    row_id = form1['row_id']

    if 'yes' in form1['copy_from_another_meter']:
        form4 = pywebio.input.input_group("Select the template meter", [
            pywebio.input.select(
                label="Meter",
                options=all_meters_options,
                name="row_id",
                required=True,
            ),
        ])
        reference_row_id = form4['row_id']
        reference_prices = get_unit_price(reference_row_id)
        save_unit_price(row_id, **reference_prices)

    # No guarantee that data in the database is complete, so even this function autofill
    # the existed unit price, default unit price is still needed.
    existed_unit_price = get_unit_price(row_id)
    existed_unit_price = {k: None if np.isnan(v) else v
                          for k, v in existed_unit_price.items()}
    form2 = get_unit_price_form(existed_unit_price)
    save_unit_price(row_id, **form2)
    pywebio.output.put_text("Unit prices of the current meter are saved to the database.")


def checkbox_non_empty(selected_options):
    if len(selected_options) == 0:
        return "At least select one option."


def draw_charts(meters: list[dict]):
    """
    Draw statistics
    :param meters: list [ dict ]
        account_number: str
        contract_id: str
        usage: returned value of `get_usage`
        unit_price: returned value of `get_unit_price
    :return:
    """
    # Figure 1: bar
    fig1 = Bar()
    for i, meter in enumerate(meters):
        account_number = meter['account_number']
        contract_id = meter['contract_id']
        total_price = get_total_price(meter['usage'], meter['unit_price'])
        if i == 0:
            common_plans = set(total_price.keys())
        else:
            common_plans.intersection_update(set(total_price.keys()))
        fig1.add_yaxis(
            f"Account number: {account_number}\nContract ID: {contract_id}",
            [total_price.get(plan) for plan in common_plans]
        )
    fig1.add_xaxis(list(common_plans))
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
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
                'Sunday']
    hour_intervals = [f'{i}:00-{i + 1}:00' for i in range(23)]
    hour_intervals.append("23:00-0:00")
    for meter in meters:
        fig2 = HeatMap()
        fig2.add_xaxis(hour_intervals)
        usage = meter['usage']
        usage['date'] = pd.to_datetime(usage[['year', 'month', 'day']])
        usage['weekday'] = usage['date'].dt.weekday
        pivot = usage[['hour', 'weekday', 'value']].groupby(by=['hour', 'weekday']).mean()
        pivot.reset_index(inplace=True)
        account_number = meter['account_number']
        contract_id = meter['contract_id']
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

    meters = []
    for row_id in rows_id:
        # total electricity price
        usage = get_usage(form1['start_date'], form1['end_date'], row_id)
        unit_price_ = get_unit_price(row_id)
        account_number = all_meters.loc[
            all_meters['rowid'] == row_id, 'account_number'][0]
        contract_id = all_meters.loc[all_meters['rowid'] == row_id, 'contract_id'][0]
        meters.append({
            'account_number': account_number,
            'contract_id': contract_id,
            'usage': usage,
            'unit_price': unit_price_,
        })
    draw_charts(meters)


app.add_url_rule(rule='/', endpoint='index', view_func=webio_view(index),
                 methods=['GET', 'POST', 'OPTIONS'])
app.add_url_rule(rule='/unit_price', endpoint='unit_price',
                 view_func=webio_view(view_unit_price), methods=['GET', 'POST', 'OPTIONS'])
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
