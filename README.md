# watchlists #

> **Warning** This script is currently under heavy development.
> Changes in functionality can occur at any time.

## Prerequisites ##

``` powershell
pip install selenium
pip install webdriver-manager
```

## Usage ##

The Hyper SBI 2 watchlists file `%APPDATA%\SBI
Securities\HYPERSBI2\IDENTIFIER\portfolio.json`.

Change the value of the option `profile_directory`.

``` powershell
py watchlists.py -C
```

### Options ###

  * `-p` backup Hyper SBI 2 `portfolio.json`
  * `-s` replace watchlists on the SBI Securities website with Hyper
    SBI 2 watchlists
  * `-y` export Hyper SBI 2 watchlists to My Portfolio on Yahoo
    Finance
  * `-C` configure common options and return
  * `-M [ACTION]` modify an action and return

## Known Issue ##

Yahoo Finance does not seem to have any stocks listed solely on the
Nagoya Stock Exchange.

## License ##

[MIT](LICENSE.md)

## Links ##

  * [*Python Scripting to Export Hyper SBI 2 Watchlists to SBI
    Securities and Yahoo Finance*](): a blog post for more details.
