#!/usr/bin/env python3
from datetime import date, timedelta
from typing import Optional, Union

import pandas as pd

from account_data import *
from src.utils import date_range, get_historical_balance, currency_conversion_on_date

"""
Functions to represent data about finances in useful ways (primarily for visualisation).
"""


# TODO:
# - Graphs:
#   - Total net assets over time
#   - Cash vs non-cash assets over time
#   - Amount (cash + non-cash) with each institution (pie chart)
#   - Amounts in different bank accounts over time
#   - Expenses by category over time (exclude reimbursable)

class BookAnalysis:
    """A class for representing data about a GnuCash book in useful ways.

    A general naming convention guide for methods:

    - methods beginning with "agg_balance" give the aggregate balance of a list of specified accounts.
    - methods beginning with "balances" give the balance of each specified account, separately.
    - methods beginning with "balance" give the balance of a single specified account.

    """

    def __init__(self, book: piecash.Book):
        #: A :class:`piecash.Book` object representing the GnuCash book we are analysing.
        self.book = book
        #: A :class:`piecash.Account` object representing the root account of the book.
        self.root_account = book.root_account

    def get_account(self, full_name: str) -> piecash.Account:
        """Get the :class:`piecash.Account` object corresponding to the given full name.

        :param full_name: The full name of the account, including any parent accounts separated by colons
            (eg, "Assets:Bank Accounts:Current Account").

        """
        tokens = full_name.split(':')
        account = self.root_account
        for t in tokens:
            account = account.children(name=t)
        return account

    def balances(self, account_names: list[str], at_date: date = None,
                 currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.Series:
        """Get a :class:`pandas.Series` containing the balance of each specified account, in the relevant currency,
        as at the relevant date.

        :param account_names: A list of full names of the accounts (see docs for :method:`get_account`).
        :param at_date: The date on which to get the balances.
        :param currency: Currency in which to express balances. If not provided, each balance is expressed in the
            relevant currency.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        balances: dict[str, float] = {}
        for name in account_names:
            acct = self.get_account(name)
            balances[acct.name] = get_historical_balance(acct, commodity=currency, at_date=at_date)
        return pd.Series(balances)

    def agg_balance(self, account_names: list[str], currency: piecash.Commodity, via: piecash.Commodity = None,
                    at_date: date = None) -> float:
        """Get the total aggregate balance of all given accounts, in the specified currency, as at the given date (or
        today's date if no date specified).
        """
        return sum(get_historical_balance(
            self.get_account(a), commodity=currency, at_date=at_date, via=via, natural_sign=False
        ) for a in account_names)

    def diff_balance(self, account: piecash.Account, start: date, end: date,
                     currency: Optional[Union[str, piecash.Commodity]] = None) -> float:
        """Get the change in balance of the specified account between the given dates, expressed in the given currency.
        If no currency is specified, the currency of the specified account is used.

        Where the account has sub-accounts in different currencies, this works by calculating the difference for each
        sub-account in its native currency, then converting everything to `currency` at the end, using the exchange
        rate closest to `end`. This way, changes to the account balance resulting solely from FX movements are not
        reflected.

        :param account: The account to examine.
        :param start: First reference date.
        :param end: Final reference date.
        :param currency: The currency in which to express the difference.
        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        if currency is None:
            currency = account.commodity
        start_bal = self.balance_by_currency(account, start)
        end_bal = self.balance_by_currency(account, end)
        diff = end_bal.subtract(start_bal, fill_value=0)
        total = 0
        for i in diff.index:
            from_currency = self.book.commodities(mnemonic=i)
            total += currency_conversion_on_date(from_currency, currency, end) * diff[i]
        return total

    def diff_balance_over_time(self, account: piecash.Account, start: date, end: date, step: timedelta,
                               currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.Series:
        """Get the change in balance of the specified account between `start` and `end`, reported at intervals of `step`
        and expressed in the given currency. If no currency is specified, the currency of the specified account is used.

        See docs for :method:`diff_balance` for docs on most parameters.
        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        series = pd.Series()
        for _end in date_range(start + step, end, step):
            _start = _end - step
            series[_end] = self.diff_balance(account, _start, _end, currency)
        return series

    def diff_balances_over_time(self, account_names: list[str], start: date, end: date, step: timedelta,
                                currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.DataFrame:
        """Returns a :class:`pandas.DataFrame` containing the changes in each account's balance over time.

        :param account_names: A list of full names of the accounts (see docs for :method:`get_account`).
        :param start: First date in period.
        :param end: Final date in period.
        :param step: Frequency of reported values.
        :param currency: The currency in which to express all values. as a :class:`piecash.Commodity` or an ISO 4217
            string.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        data: dict[str, pd.Series] = {}
        for name in account_names:
            acct = self.get_account(name)
            data[acct.name] = self.diff_balance_over_time(acct, start, end, step, currency)
        return pd.DataFrame(data)

    def agg_balance_over_time(self, account_names: list[str], start: date, end: date, step: timedelta,
                              currency: Optional[Union[str, piecash.Commodity]],
                              via: Optional[list[piecash.Commodity]] = None) -> pd.Series:
        """Returns a :class:`pandas.Series` containing the aggregate balance of the specified accounts over time.

        :param account_names: A list of full names of the accounts (see docs for :method:`get_account`).
        :param start: First date in period.
        :param end: Final date in period.
        :param step: Frequency of reported values.
        :param currency: The currency in which to express all values. as a :class:`piecash.Commodity` or an ISO 4217
            string.
        :param via: A list of currency to try converting to as an intermediate step, if a direct conversion is not
            available.
        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        index = []
        data = []
        for d in date_range(start, end, step):
            index.append(d)
            data.append(self.agg_balance(account_names, currency, via, d))
        return pd.Series(data, index)

    def balance_over_time(self, account_name: str, start: date, end: date, step: timedelta,
                          currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.Series:
        """Returns a :class:`pandas.Series` containing the balance of the specified account over time.

        :param account_name: The full names of the accounts (see docs for :method:`get_account`).
        :param start: First date in period.
        :param end: Final date in period.
        :param step: Frequency of reported values.
        :param currency: The currency in which to express all values, as a :class:`piecash.Commodity` or an ISO 4217
            string.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        index = []
        data = []
        for d in date_range(start, end, step):
            index.append(d)
            data.append(get_historical_balance(self.get_account(account_name), at_date=d, commodity=currency))
        return pd.Series(data, index)

    def balances_over_time(self, account_names: list[str], start: date, end: date, step: timedelta,
                           currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.DataFrame:
        """Returns a :class:`pandas.DataFrame` containing the balance of each specified account over time.

        :param account_names: A list of full names of the accounts (see docs for :method:`get_account`).
        :param start: First date in period.
        :param end: Final date in period.
        :param step: Frequency of reported values.
        :param currency: The currency in which to express all values, as a :class:`piecash.Commodity` or an ISO 4217
            string.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        data: dict[str, pd.Series] = {}
        for name in account_names:
            data[name] = self.balance_over_time(name, start, end, step, currency)
        return pd.DataFrame(data)

    def balance_by_currency(self, account: piecash.Account, at_date: date,
                            currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.Series:
        """Get the balance of a single account (including its sub-accounts) broken down by currency.

        :param account: Account to query.
        :param at_date: Date as of which to report balances.
        :param currency: Currency in which to express balance, as a :class:`piecash.Commodity` or an ISO 4217
            string. If not provided, each balance is expressed in the relevant currency.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        total_balances: dict[str, float] = {}
        balance = get_historical_balance(account, recurse=False, at_date=at_date, commodity=currency)
        if balance:
            currency_code = account.commodity.mnemonic
            total_balances[currency_code] = total_balances.get(currency_code, 0) + balance
        series = pd.Series(total_balances)
        for child in account.children:
            series = series.add(self.balance_by_currency(child, at_date, currency), fill_value=0)
            #child_balances = self.balance_by_currency(child, at_date, currency)
            #for currency_code in child_balances:
            #    total_balances[currency_code] = total_balances.get(currency_code, 0) + child_balances[currency_code]

        return series

    def agg_balance_by_currency(self, account_names: list[str], at_date: date = None,
                                currency: Optional[Union[str, piecash.Commodity]] = None) -> pd.Series:
        """Get a :class:`pandas.Series` containing the aggregate balance of the accounts, broken down by currency.

        :param account_names: A list of full names of the accounts (see docs for :method:`get_account`).
        :param at_date: The date on which to get the balances.
        :param currency: Currency in which to express balance, as a :class:`piecash.Commodity` or an ISO 4217
            string. If not provided, each balance is expressed in the relevant currency.

        """
        if (currency is not None) and (not isinstance(currency, piecash.Commodity)):
            currency = self.book.commodities(mnemonic=currency)
        total_balances: dict[str, float] = {}
        for acct_name in account_names:
            acct = self.get_account(acct_name)
            acct_balances = self.balance_by_currency(acct, at_date, currency)
            for currency_code in acct_balances.index:
                total_balances[currency_code] = total_balances.get(currency_code, 0) + acct_balances[currency_code]
        return pd.Series(total_balances)




def get_account_balance(root: piecash.Account, full_acct_name: str, currency: piecash.Commodity,
                        at_date: Optional[date] = None) -> float:
    """Get the balance of the given account, in the specified currency, as at the given date (or today's date if no
    date specified).
    """
    tokens = full_acct_name.split(':')
    account = root
    for t in tokens:
        account = account.children(name=t)
    return float(get_historical_balance(account, commodity=currency, at_date=at_date))


def get_aggregate_balance(root: piecash.Account, accounts: list[str], currency: piecash.Commodity,
                          at_date: Optional[date] = None) -> float:
    """Get the total aggregate balance of all given accounts, in the specified currency, as at the given date (or
    today's date if no date specified).
    """
    return sum(get_account_balance(root, a, currency, at_date) for a in accounts)


def net_asset_value_over_time(root: piecash.Account, start: date, end: date, step: timedelta,
                              currency: piecash.Commodity) -> pd.Series:
    """Returns a pd.Series containing net asset value (assets - liabilities) over time."""
    index = []
    data = []
    # By default, I think the balance Liabilities account has a negative sign, so it should be okay to simply add its
    # balance to the total balance of the Assets account to get the net value.
    accounts = ALL_ASSETS + ['Liabilities']
    for d in date_range(start, end, step):
        index.append(d)
        data.append(get_aggregate_balance(root, accounts, currency, d))
    return pd.Series(data, index)


def cash_vs_non_cash_over_time(root: piecash.Account, start: date, end: date, step: timedelta,
                               currency: piecash.Commodity) -> pd.DataFrame:
    """Returns a pd.DataFrame containing total cash and non-cash assets over time."""
    # NOTE: It seems that piecash always uses the latest price to convert commodities to cash, so it's not currently
    # possible to measure change in value of non-cash assets over time. Considering filing a bug report. In the
    # meantime, we could do this as a pie chart as of today
    index = []
    cash = []
    non_cash = []
    for d in date_range(start, end, step):
        index.append(d)
        cash.append(get_aggregate_balance(root, CASH_ASSETS, currency, d))
        non_cash.append(get_aggregate_balance(root, NON_CASH_ASSETS, currency, d))
    data = {'Cash': cash, 'Non-Cash': non_cash}
    return pd.DataFrame(data, index=index)


def amount_per_institution(root: piecash.Account, institutions: dict[str, list[str]],
                           currency: piecash.Commodity) -> dict[str, float]:
    """Returns a dict containing the total value of assets held with each institution (as at today's date)."""
    return {i: get_aggregate_balance(root, institutions[i], currency) for i in institutions}


def balances_over_time(root: piecash.Account, accounts: list[str], start: date, end: date, step: timedelta,
                       currency: piecash.Commodity) -> pd.DataFrame:
    data = []
    for d in date_range(start, end, step):
        row_dict = {'date': d}
        for acct in accounts:
            row_dict[acct] = get_account_balance(root, acct, currency, d)
        data.append(row_dict)
    return pd.DataFrame(data).set_index('date')
