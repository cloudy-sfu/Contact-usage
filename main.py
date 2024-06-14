import logging
import socket
import sys
from datetime import datetime, timedelta
# import webbrowser

import pywebio
from flask import Flask
from pywebio.platform.flask import webio_view

from contact_energy_aws_lambda import ContactEnergyUsage
from contact_energy_local_db import get_account_contract_row_id, \
    get_usage_missing_dates, save_usage

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,  # Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    format="[%(levelname)s] [%(asctime)s]\n%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
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
        "---"
    )
    pywebio.output.put_text("Update data from Contact Energy.")
    pywebio.output.put_link(name="Enter", url="/get_data")


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

    form2 = pywebio.input.input_group("Choose account", [
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
            help_text="The earliest date is 1996-01-01.",
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


app.add_url_rule(rule='/', endpoint='index', view_func=webio_view(index),
                 methods=['GET', 'POST', 'OPTIONS'])
app.add_url_rule(rule='/get_data', endpoint='get_data', view_func=webio_view(get_data),
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
    # webbrowser.open_new_tab(f'http://localhost:{port}')
    # TODO: enable webbrowser, remove debug
    app.run(port=port, debug=True)
