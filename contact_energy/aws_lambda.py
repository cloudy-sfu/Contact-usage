import json
import logging
import subprocess
import time
import uuid
from random import uniform

from requests import Session

with open("contact_energy/header_login.json") as f:
    header_login = json.load(f)
with open("contact_energy/header_csrf_token.json") as f:
    # x-api-key is defined by
    # https://myaccount.contact.co.nz/main.2049c28d6664d8a2ecc3.esm.js
    header_csrf_token = json.load(f)
with open("contact_energy/request_usage.ps1") as f:
    req_usage = f.read()
sess = Session()
sess.trust_env = False


class ContactEnergyUsage:
    def __init__(self, username, password):
        # Log in, get authentication (session).
        resp_login = sess.post(
            url="https://api.contact-digital-prod.net/login/v2",
            data=json.dumps({"password": password, "username": username}),
            headers=header_login,
        )
        if resp_login.status_code != 200:
            raise Exception(f"Fail to login. Status code: {resp_login.status_code}. "
                            f"Reason: {resp_login.reason}")
        self.auth = resp_login.json().get('token')
        if not self.auth:
            raise Exception(f"Fail to login. Status code: {resp_login.status_code}. "
                            f"Reason: {resp_login.reason}")

        # Get CSRF key and contract ID.
        header_csrf_token["session"] = self.auth
        resp_csrf_token = sess.get(
            url="https://api.contact-digital-prod.net/accounts/v2?ba=",
            headers=header_csrf_token,
        )
        if resp_csrf_token.status_code != 200:
            raise Exception(f"Fail to get CSRF key, account number, and contract number. "
                            f"Status code: {resp_csrf_token.status_code}. "
                            f"Reason: {resp_csrf_token.reason}")
        resp_csrf_token = resp_csrf_token.json()
        self.csrf_token = resp_csrf_token.get('xcsrfToken')
        if not self.csrf_token:
            raise Exception(f"Fail to get CSRF key, account number, and contract number. "
                            f"Status code: {resp_csrf_token.status_code}. "
                            f"Reason: {resp_csrf_token.reason}")
        self.account_numbers_contract_id = {
            # item exists only when 'id' in keys
            account['id']: [
                contract['contractId']
                for contract in account.get('contracts', [])
            ]
            for account in resp_csrf_token.get('accountsSummary', [])
            if account.get('id')
        }
        self.uuid_ = str(uuid.uuid4())

    def get_usage(self, account_number, contract_id, date_):
        url_usage = (f"https://api.contact-digital-prod.net/usage/v2/{contract_id}?"
                     f"ba={account_number}&interval=hourly&from={date_}&to={date_}")
        req_usage_ins = req_usage % (self.auth, self.uuid_, self.csrf_token, url_usage)
        process = subprocess.Popen(['powershell', '-Command', req_usage_ins],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        resp_usage = stdout.decode('utf-8')
        try:
            usage = json.loads(resp_usage)
            time.sleep(round(uniform(0.7, 1.3), 2))
            return usage
        except json.decoder.JSONDecodeError:
            logging.warning(f"The authentication of Contact Energy account expires. "
                            f"Error: {stderr.decode('utf-8')}")
