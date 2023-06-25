# trading-peripheral #

<!-- Python script that exports Hyper SBI 2 watchlists to Yahoo Finance,
extracts order status, and inserts maintenance schedules into Google Calendar
-->

The `trading_peripheral.py` Python script can:

  * Replace watchlists on the SBI Securities website with [Hyper SBI
    2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html) watchlists,
  * Export them from the `%APPDATA%\SBI
    Securities\HYPERSBI2\IDENTIFIER\portfolio.json` file to [*My
    Portfolio*](https://finance.yahoo.com/portfolios) on Yahoo Finance,
  * Extract the order status from the SBI Securities web page and copy it to
    the clipboard,
  * Retrieve [*SBI Securities Maintenance
    Schedules*](https://search.sbisec.co.jp/v2/popwin/info/home/pop6040_maintenance.html)
    and insert them into Google Calendar,
  * Take a snapshot of the `%APPDATA%\SBI Securities\HYPERSBI2` application
    data and restore it.

> **Warning**: This script is currently under heavy development.  Changes in
> functionality may occur at any time.

## Prerequisites ##

This script has been tested in [Python for
Windows](https://www.python.org/downloads/windows/) with Hyper SBI 2 and uses
the following web browser and packages:

  * [Chrome](https://www.google.com/chrome/) to authenticate to the website and
    load the page
  * [`selenium`](https://www.selenium.dev/documentation/webdriver/) to drive a
    browser
  * [`webdriver-manager`](https://github.com/SergeyPirogov/webdriver_manager)
    to automatically update the driver
  * [`pandas`](https://pandas.pydata.org/) and
    [`lxml`](https://lxml.de/index.html) to extract data from the web pages
  * [`google-api-python-client`](https://googleapis.github.io/google-api-python-client/docs/),
    [`google-auth-httplib2`](https://github.com/googleapis/google-auth-library-python-httplib2),
    and
    [`google-auth-oauthlib`](https://github.com/googleapis/google-auth-library-python-oauthlib)
    to access Google APIs
  * [GnuPG](https://gnupg.org/index.html) and
    [`python-gnupg`](https://docs.red-dove.com/python-gnupg/) to encrypt and
    decrypt an application data archive
  * [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/en/master/index.html)
    to complete possible values or a previous value in configuring

Install each package as needed.  For example:

``` powershell
winget install Google.Chrome
winget install GnuPG.GnuPG
python -m pip install -r requirements.txt -U
```

## Usage ##

If you are using Chrome as your default web browser, create a separate profile
that stores your credentials and specify it as the value of the
`profile_directory` option as follows:

``` powershell
python trading_peripheral.py -G
```

A `%LOCALAPPDATA%\trading-peripheral\trading_peripheral.ini` configuration file
stores these configurations.

### Options ###

  * `-P BROKERAGE PROCESS`: set the brokerage and the process [defaults: `SBI
    Securities` and `HYPERSBI2`]
  * `-w`: backup the Hyper SBI 2 watchlists
  * `-s`: replace the watchlists on the SBI Securities website with the Hyper
    SBI 2 watchlists
  * `-y`: export the Hyper SBI 2 watchlists to My Portfolio on Yahoo Finance
  * `-o`: extract the order status from the SBI Securities web page and copy it
    to the clipboard
  * `-m`: insert maintenance schedules into Google Calendar
  * `-d`: take a snapshot of the Hyper SBI 2 application data
  * `-D`: restore the Hyper SBI 2 application data from a snapshot
  * `-G`: configure general options and exit
  * `-O`: configure order state formats and exit
  * `-M`: configure maintenance schedules and exit
  * `-A`: configure actions and exit

## Known Issues ##

  * Yahoo Finance does not seem to have stocks listed solely on the Nagoya
    Stock Exchange.
  * Extracting the order status assumes day trading on margin.

## License ##

[MIT](LICENSE.md)

## Link ##

  * [*Python Scripting to Export Hyper SBI 2 Watchlists to Yahoo
    Finance*](https://carmine560.blogspot.com/2023/02/python-scripting-to-export-hyper-sbi-2.html):
    a blog post about serializing WebDriver commands
