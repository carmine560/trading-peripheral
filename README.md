# trading-peripheral #

<!-- Python script that exports Hyper SBI 2 watchlists to Yahoo
Finance and extracts order status from SBI Securities web page -->

<!-- hypersbi2 python chrome selenium webdrivermanager -->

`trading_peripheral.py`:

  * replaces watchlists on the SBI Securities website with [Hyper SBI
    2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html)
    watchlists
  * exports them from the file `%APPDATA%\SBI
    Securities\HYPERSBI2\IDENTIFIER\portfolio.json` to [My
    Portfolio](https://finance.yahoo.com/portfolios) on Yahoo Finance
  * extracts order status from the SBI Securities web page and copy
    them to the clipboard

> **Warning** This script is currently under heavy development.
> Changes in functionality can occur at any time.

## Prerequisites ##

This script has been tested in [Python for
Windows](https://www.python.org/downloads/windows/) with Hyper SBI 2
and uses the following web browser and packages:

  * [Chrome](https://www.google.com/chrome/) authenticates to the
    website and loads the page
  * [Selenium
    WebDriver](https://www.selenium.dev/documentation/webdriver/)
    drives a browser
  * [Webdriver Manager for
    Python](https://github.com/SergeyPirogov/webdriver_manager)
    automatically updates the driver

Install each package as needed.  For example:

``` powershell
winget install Google.Chrome
pip install selenium
pip install webdriver-manager
```

## Usage ##

If you are using Chrome as your default web browser, create a separate
profile that stores your credentials and specify it as the value of
the option `profile_directory` as follows:

``` powershell
py trading_peripheral.py -C
```

These configurations are saved in the configuration file
`%LOCALAPPDATA%\trading-peripheral\trading_peripheral.ini`.

### Options ###

  * `-p`: backup Hyper SBI 2 `portfolio.json`
  * `-s`: replace watchlists on the SBI Securities website with Hyper
    SBI 2 watchlists
  * `-y`: export Hyper SBI 2 `portfolio.json` to My Portfolio on Yahoo
    Finance
  * `-o`: extract order status from the SBI Securities web page and
    copy them to the clipboard
  * `-C`: configure common options and exit
  * `-A`: configure actions and exit

## Known Issues ##

  * Yahoo Finance does not seem to have any stocks listed solely on
    the Nagoya Stock Exchange.
  * Extracting order status assumes day trading on margin.

## License ##

[MIT](LICENSE.md)

<!-- ## Links ## -->
## Link ##

  * [*Python Scripting to Export Hyper SBI 2 Watchlists to Yahoo
    Finance*](https://carmine560.blogspot.com/2023/02/python-scripting-to-export-hyper-sbi-2.html):
    a blog post for more details.
  <!-- * [*Python Scripting to Extract Order Status from SBI Securities Web -->
  <!--   Page*](): a blog post for more details. -->
