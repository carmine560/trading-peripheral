# trading-peripheral #

<!-- Python script that retrieves Hyper SBI 2 maintenance schedules, checks the
daily sales order quota, and extracts order status from the SBI Securities web
pages. -->

The `trading_peripheral.py` Python script can:

  * Retrieve the [*SBI Securities Maintenance
    Schedules*](https://search.sbisec.co.jp/v2/popwin/info/home/pop6040_maintenance.html)
    page and insert [Hyper SBI
    2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html) maintenance
    schedules into Google Calendar,
  * Replace watchlists on the SBI Securities website with Hyper SBI 2
    watchlists,
  * Check the daily sales order quota for general margin trading and send a
    notification via Gmail if it is insufficient,
  * Extract the order status from the SBI Securities order status web page and
    copy it to the clipboard,
  * Take a snapshot of the `%APPDATA%\SBI Securities\HYPERSBI2` application
    data and restore it.

> **Warning**: `trading_peripheral.py` is currently under heavy development.
> Changes in functionality may occur at any time.

## Prerequisites ##

`trading_peripheral.py` has been tested in [Python for
Windows](https://www.python.org/downloads/windows/) with Hyper SBI 2 and
requires the following web browser and packages:

  * [`google-api-python-client`](https://googleapis.github.io/google-api-python-client/docs/),
    [`google-auth-httplib2`](https://github.com/googleapis/google-auth-library-python-httplib2),
    and
    [`google-auth-oauthlib`](https://github.com/googleapis/google-auth-library-python-oauthlib)
    to access Google APIs
  * [Chrome](https://www.google.com/chrome/) to authenticate to the website and
    load the page
  * [`selenium`](https://www.selenium.dev/documentation/webdriver/) to drive a
    browser, and
    [`webdriver-manager`](https://github.com/SergeyPirogov/webdriver_manager)
    to automatically update the driver
  * [`chardet`](https://github.com/chardet/chardet),
    [`lxml`](https://lxml.de/index.html),
    [`pandas`](https://pandas.pydata.org/), and
    [`pyarrow`](https://arrow.apache.org/docs/python/) to extract data from the
    web pages
  * [`python-gnupg`](https://docs.red-dove.com/python-gnupg/) to invoke
    [GnuPG](https://gnupg.org/index.html) to encrypt and decrypt a snapshot of
    the Hyper SBI 2 application data
  * [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/en/master/index.html)
    to complete possible values or a previous value in configuring

Install each package as needed. For example:

``` powershell
winget install Google.Chrome
winget install GnuPG.GnuPG
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -U
```

## Usage ##

The `-m` and `-q` options use the Google Calendar and Gmail APIs. Follow the
[*Google Calendar API
Quickstart*](https://developers.google.com/calendar/api/quickstart/python) and
[*Gmail API
Quickstart*](https://developers.google.com/gmail/api/quickstart/python) pages
to obtain your `client_secret_*.json` file.

If you use Chrome as your default web browser, create a separate profile that
stores your credentials. Then, specify the profile directory as the value of
the `profile_directory` option, as shown below:

``` powershell
python trading_peripheral.py -G
```

The `-d` option encrypts a snapshot of the Hyper SBI 2 application data using
GnuPG. By default, it uses the default key pair of GnuPG. However, you can also
specify a key fingerprint as the value of the `fingerprint` option using the
`-G` option.

The `%LOCALAPPDATA%\trading-peripheral\trading_peripheral.ini` configuration
file stores these configurations.

### Options ###

  * `-P BROKERAGE PROCESS|PATH_TO_EXECUTABLE`: set the brokerage and the
    process [defaults: `SBI Securities` and `HYPERSBI2`]
  * `-m`: insert Hyper SBI 2 maintenance schedules into Google Calendar
  * `-s`: replace watchlists on the SBI Securities website with the Hyper SBI 2
    watchlists
  * `-q`: check the daily sales order quota for general margin trading for the
    specified Hyper SBI 2 watchlist and send a notification via Gmail if it is
    insufficient
  * `-o`: extract the order status from the SBI Securities order status web
    page and copy it to the clipboard
  * `-w`: backup the Hyper SBI 2 watchlists
  * `-d`: take a snapshot of the Hyper SBI 2 application data
  * `-D`: restore the Hyper SBI 2 application data from a snapshot
  * `-G`: configure general options and exit
  * `-O`: configure order status formats and exit
  * `-A`: configure actions and exit
  * `-C`: check configuration changes and exit

## Known Issues ##

  * For the extraction of the order status, I assume there are 1 to 10 pairs of
    orders (a pair consists of a position and repayment order) for day trading
    on margin.

## License ##

[MIT](LICENSE.md)

## Link ##

  * [*Python Scripting to Serialize WebDriver Commands to Export Hyper SBI 2
    Watchlists*](https://carmine560.blogspot.com/2023/02/python-scripting-to-export-hyper-sbi-2.html):
    a blog post about serializing WebDriver commands
