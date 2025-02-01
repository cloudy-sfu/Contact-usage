# Contact usage
 Compare electricity prices between Contact Energy electricity plans

![dependencies Python 3.12](https://shields.io/badge/dependencies-Python_3.12-blue)
![dependencies Powershell 5.1](https://shields.io/badge/dependencies-Powershell_5.1-cyan)

## Install

**Users**:

Download the latest release and unzip.

To migrate data from a previous version, move `contact_energy.db` from previous version program's folder to the current version program's folder.

**Developers**:

Create a Python virtual environment, then run the following command.

```
pip install -r requirements.txt
```

To start the program, run the following command.

```
python main.py
```

To compile the program, run the following command.

```
pyinstaller main.spec
```

Find the compiled program in `dist/`.

## Usage

Run `Contact Usage.exe`.

The program will open a new tab in your system default web browser. Interact with the program on that page.

To terminate this program, please close the tab in web browser, then close the command line window.

When the unit prices change, the price of existed contract will not change, unless you get notified by Contact Energy. 

The correct way is to compare the contract (old) price of your current plan and new price of other plans from https://journey.contact.co.nz/residential/find-a-plan 

<details>
    <summary>Screenshots</summary>
    <img src="./assets/Snipaste_2024-06-22_00-23-10.png" alt="Bar plot of total electricity fee">
    <img src="./assets/Snipaste_2024-06-22_00-23-20.png" alt="Hot plot of hourly electricity usage">
</details>

