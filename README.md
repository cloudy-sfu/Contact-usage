# Contact usage
 Calculate electricity usage of Contact Energy account

![dependencies Python 3.12](https://shields.io/badge/dependencies-Python_3.12-blue)
![dependencies Powershell 5.1](https://shields.io/badge/dependencies-Powershell_5.1-cyan)

## Install

**Users**:

Download the latest release.

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
python post_pyinstaller.py
```

Find the compiled program in `dist/`.

## Usage

Run `Contact Usage.exe`.

The program will open a new tab in your system default web browser. Interact with the program on that page.

To terminate this program, please close the tab in web browser, then close the command line window.

When the unit prices change, get the new price by visiting https://journey.contact.co.nz/residential/find-a-plan You should pretend to join Contact Energy as a new customer and view the quotes, but don't need to confirm and pay.

<details>
    <summary>Screenshots</summary>
    <img src="./assets/Snipaste_2024-06-22_00-23-10.png" alt="Bar plot of total electricity fee">
    <img src="./assets/Snipaste_2024-06-22_00-23-20.png" alt="Hot plot of hourly electricity usage">
</details>

