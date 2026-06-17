# `trading-peripheral`

<!-- Python script that retrieves Hyper SBI 2 maintenance schedules and extracts order status from the SBI Securities web page -->

The `trading_peripheral.py` Python script can:

  * Check the [*Hyper SBI 2 Release
    Notes*](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112_update.html) and
    send a notification via Gmail if they are updated
  * Check the [*SBI Securities Maintenance
    Schedules*](https://search.sbisec.co.jp/v2/popwin/info/home/pop6040_maintenance.html)
    and insert [Hyper SBI
    2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html) maintenance
    schedules into Google Calendar
  * Replace watchlists on the SBI Securities website with Hyper SBI 2
    watchlists
  * Extract the order status from the SBI Securities order status web page and
    copy it to the clipboard
  * Take a snapshot of the `%APPDATA%\SBI Securities\HYPERSBI2` application
    data and restore it

## Prerequisites

`trading_peripheral.py` has been tested in [Python for
Windows](https://www.python.org/downloads/windows/) with Hyper SBI 2 on Windows
10 with ESU and requires the following packages:

  * [Firefox](https://www.firefox.com/en-US/) to authenticate to the website
    and load the web page
  * [GnuPG](https://gnupg.org/index.html) to encrypt and decrypt the Google
    OAuth token and a snapshot of the Hyper SBI 2 application data
  * [`charset-normalizer`](https://github.com/jawah/charset_normalizer),
    [`lxml`](https://github.com/lxml/lxml),
    [`pandas`](https://github.com/pandas-dev/pandas), and
    [`requests`](https://github.com/psf/requests) to extract data from the web
    pages
  * [`google-api-python-client`](https://github.com/googleapis/google-api-python-client),
    [`google-auth`](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth),
    and
    [`google-auth-oauthlib`](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth-oauthlib)
    to access Google APIs
  * [`prompt_toolkit`](https://github.com/prompt-toolkit/python-prompt-toolkit)
    to complete possible values or a previous value in configuring
  * [`selenium`](https://github.com/SeleniumHQ/selenium/tree/trunk/py) to drive
    a browser

Install each package as needed. For example:

``` powershell
winget install Mozilla.Firefox
winget install GnuPG.GnuPG
git clone --recurse-submodules git@github.com:carmine560/trading-peripheral.git
cd trading-peripheral
# Run 'git submodule update --init' if you cloned without
# '--recurse-submodules'.
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -c constraints.txt
```

## Run Tests (Optional)

``` powershell
python -m pip install -r requirements-dev.txt -c constraints.txt
python -m pytest -q
```

## Usage

The `-r` option uses the Gmail API, and the `-m` option uses the Google
Calendar API. Follow the [*Gmail API
Quickstart*](https://developers.google.com/workspace/gmail/api/quickstart/python)
and [*Google Calendar API
Quickstart*](https://developers.google.com/workspace/calendar/api/quickstart/python)
to obtain your `client_secret_*.json` file.

Create a non-default Firefox profile and specify its “Root Directory” as the
value of the `firefox_profile_directory` option, as shown below:

``` powershell
python trading_peripheral.py -G
```

`trading_peripheral.py` stores its configuration in a file located at
`%LOCALAPPDATA%\trading-peripheral\trading_peripheral.ini`.

### Encrypt OAuth Token and Snapshot of Hyper SBI 2 Application Data

The Google OAuth token used by the `-r` and `-m` options is stored in
`%LOCALAPPDATA%\trading-peripheral\token.json.gpg`. The `-d` option creates a
snapshot of the Hyper SBI 2 application data and encrypts it using GnuPG.

By default, the script uses your default GnuPG key. To use a different key,
specify its fingerprint with the `-G` option. The Google OAuth token and
encrypted snapshot use the same fingerprint setting.

### Options

  * `-P BROKERAGE PROCESS|EXECUTABLE_PATH`: set the brokerage and the process
    [defaults: `SBI Securities` and `HYPERSBI2`]
  * `-r`: check the `PROCESS` release notes and send a notification via Gmail
    if they are updated
  * `-m`: insert `PROCESS` maintenance schedules into Google Calendar
  * `-s`: replace watchlists on the `BROKERAGE` website with the `PROCESS`
    watchlists
  * `-S`: replace the `PROCESS` watchlists with watchlists on the `BROKERAGE`
    website
  * `-o`: extract the order status from the `BROKERAGE` order status web page
    and copy it to the clipboard
  * `-w`: backup the `PROCESS` watchlists
  * `-d`: take a snapshot of the `PROCESS` application data
  * `-D`: restore the `PROCESS` application data from a snapshot
  * `-BS [OUTPUT_DIRECTORY]`: generate a WSL Bash script to launch this script
    and exit
  * `-PS [OUTPUT_DIRECTORY]`: generate a PowerShell 7 script to launch this
    script and exit
  * `-G`: configure general options and exit
  * `-O`: configure order status formats and exit
  * `-A`: configure actions and exit
  * `-C`: check configuration changes and exit

## Known Issue

  * The extraction of the order status assumes up to 100 orders for day trading
    on margin. These orders include sequentially paired orders (each consisting
    of a position order followed by its repayment order) and canceled orders.
    It does not support multiple web pages of the order status.

## License

This project is licensed under the [MIT License](LICENSE). The `.gitignore`
file is sourced from [`gitignore`](https://github.com/github/gitignore), which
is licensed under the CC0-1.0 license.

## Link

  * [*Python Scripting to Serialize WebDriver Commands to Export Hyper SBI 2
    Watchlists*](https://carmine560.blogspot.com/2023/02/python-scripting-to-export-hyper-sbi-2.html):
    a blog post about serializing WebDriver commands
