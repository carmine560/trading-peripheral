# watchlists #

<!-- Python script that exports Hyper SBI 2 Watchlists to SBI
Securities and Yahoo Finance -->

<!-- hypersbi2 python chrome selenium webdrivermanager -->

`watchlists.py` replaces watchlists on the SBI Securities website with
[Hyper SBI 2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html)
watchlists and exports Hyper SBI 2 watchlists to My Portfolio on Yahoo
Finance.

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

``` powershell
pip install selenium
pip install webdriver-manager
```

## Usage ##

If you are using Chrome as your default web browser, create a separate
profile that stores your credentials and specify it as the value of
the option `profile_directory` as follows:

``` powershell
py watchlists.py -C
```

Note that when exporting the Hyper SBI 2 watchlists to My Portfolio,
this script loads the watchlist file `%APPDATA%\SBI
Securities\HYPERSBI2\IDENTIFIER\portfolio.json`.

### Options ###

  * `-p` backup Hyper SBI 2 `portfolio.json`
  * `-s` replace watchlists on the SBI Securities website with Hyper
    SBI 2 watchlists
  * `-y` export Hyper SBI 2 `portfolio.json` to My Portfolio on Yahoo
    Finance
  * `-C` configure common options and exit
  * `-A` configure actions and exit

## Known Issue ##

Yahoo Finance does not seem to have any stocks listed solely on the
Nagoya Stock Exchange.

## License ##

[MIT](LICENSE.md)

## Links ##

  * [*Python Scripting to Export Hyper SBI 2 Watchlists to SBI
    Securities and Yahoo Finance*](): a blog post for more details.
