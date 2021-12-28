from datetime import date, timedelta
from typing import Generator, Union

import pandas as pd

import piecash
from piecash import Price
from piecash._common import GncConversionError

from src.exceptions import PriceNotFoundError


def top_and_other(in_data: Union[pd.Series, pd.DataFrame], top_n: int) -> Union[pd.Series, pd.DataFrame]:
    """Take a :class:`pandas.Series` or :class:`pandas.DataFrame` with numeric data and return an object of the same
    type containing the top columns (ie, those with the highest values), plus an "Other" category which contains a sum
    of all other categories.

    If `in_data` is a `pandas.DataFrame`, the columns are sorted based on their sums, and the "Other" column is obtained
    by aggregating the remaining columns along the x-axis (so that the index is preserved).

    :param in_data: The input data.
    :param top_n: How many separate categories to display.

    """
    if isinstance(in_data, pd.DataFrame):
        axis = 1
        totals = in_data.sum()
    else:
        axis = 0
        totals = in_data
    sorted_col_names = totals.sort_values(ascending=False).index
    top_col_names = sorted_col_names[:top_n]
    other_col_names = sorted_col_names[top_n:]
    top_cols = in_data[top_col_names]
    top_cols['Other'] = in_data[other_col_names].sum(axis=axis)
    return top_cols

def date_range(start: date, end: date, step: timedelta) -> Generator[date, None, None]:
    d = start
    while d < end:
        yield d
        d += step

# The following two functions are based on modified versions of piecash's `Account.get_balance` and
# `Commodity.currency_conversion` methods. They are modified to use past commodity prices to do currency conversions
# on past dates. I have an outstanding pull request to incorporate these features into piecash:
# https://github.com/sdementen/piecash/pull/192
# Another change I have made in the below functions is to return floats rather than Decimals.

def currency_conversion_on_date(commodity: piecash.Commodity, currency: piecash.Commodity, on_date: date,
                                closest_conv_cache: dict[tuple, dict[date, float]] = None) -> float:
    """
    Return the conversion factor to convert self to currency, as of a given date in the past. If no price is stored
    for the specified date, the stored price that is closest in time to the specified date will be used.

    :param commodity: The commodity to convert from.
    :param currency: The commodity to convert to.
    :param on_date: The date for getting the relevant price.
    :param closest_conv_cache: An internal cache of closest-in-time commodity prices. Keys are commodity pairs
        (as tuples); values are dicts mapping dates to prices. This is used internally when this method is called as
        part of a recursive function.
    """
    pair = (commodity, currency)
    if commodity == currency:
        return 1
    #print(f'converting {commodity.mnemonic} to {currency.mnemonic}')
    if (closest_conv_cache is not None) and (on_date in closest_conv_cache.get(pair, {})):
        return closest_conv_cache[pair][on_date]
    # get all "forward" (self-to-other) rates
    forward_rates = commodity.prices.filter_by(currency=currency).order_by(Price.date.asc())
    # get all "reverse" (other-to-self) rates
    reverse_rates = currency.prices.filter_by(currency=commodity).order_by(Price.date.asc())
    if forward_rates.count():
        closest_forward = min(forward_rates, key=lambda p: abs(p.date - on_date))
    else:
        closest_forward = None
    #print(f'Closest forward rate: {closest_forward}')
    if reverse_rates.count():
        closest_reverse = min(reverse_rates, key=lambda p: abs(p.date - on_date))
    else:
        closest_reverse = None
    #print(f'Closest reverse rate: {closest_reverse}')
    if closest_forward is None and closest_reverse is None:
        # no prices found
        raise PriceNotFoundError("Cannot convert {} to {}".format(commodity, currency))
    elif closest_reverse is None:
        # only forward prices found
        closest = closest_forward.value
    elif closest_forward is None:
        # only backwards prices found
        closest = 1 / closest_reverse.value
    else:
        # both forwards and backwards prices found
        if abs(closest_forward.date - on_date) <= abs(closest_reverse.date - on_date):
            closest = closest_forward.value
        else:
            closest = 1 / closest_reverse.value
    #print(f'Closest: {closest}')
    closest = float(closest)
    if closest_conv_cache is not None:
        if pair not in closest_conv_cache:
            closest_conv_cache[pair] = {}
        closest_conv_cache[pair][on_date] = closest
    return closest


def get_historical_balance(account: piecash.Account, recurse: bool = True, commodity: piecash.Commodity = None,
                           natural_sign: bool = True, at_date: date = None,
                           closest_conv_cache: dict[tuple, dict[date, float]] = None) -> float:
    """
    Returns the balance of the account (including its children accounts if recurse=True) expressed in account's
    commodity/currency.

    :param account: The account whose balance we want to find.
    :param recurse: True if the balance should include children accounts (default to True)
    :param commodity: The currency into which to get the balance (default to None, i.e. the currency of the account)
    :param natural_sign: True if the balance sign is reversed for accounts of type {'LIABILITY', 'PAYABLE', 'CREDIT',
        'INCOME', 'EQUITY'} (default to True)
    :param at_date: The sum() balance of the account at a given date based on transaction post date
    :param closest_conv_cache: An internal cache of closest-in-time commodity prices. Keys are commodities; values are
        dicts mapping dates to prices. Used internally where recurse and use_historical are both True. Should not
        generally be explicitly provided in external calls.
    """
    if commodity is None:
        commodity = account.commodity

    if at_date is None:
        balance = sum([sp.quantity for sp in account.splits])
    else:
        balance = sum(
            [
                sp.quantity
                for sp in account.splits
                if sp.transaction.post_date <= at_date
            ]
        )
    balance = float(balance)
    if commodity != account.commodity:
        try:
            # conversion is done directly from self.commodity to commodity (if possible)
            if at_date is not None:
                if closest_conv_cache is None:
                    closest_conv_cache = {}
                factor = currency_conversion_on_date(account.commodity, commodity, at_date, closest_conv_cache)
            else:
                factor = float(account.commodity.currency_conversion(commodity))
            balance = balance * factor
        except (PriceNotFoundError, GncConversionError):
            # conversion is done from self.commodity to self.parent.commodity and then to commodity
            if at_date is not None:
                factor1 = currency_conversion_on_date(account.commodity, account.parent.commodity, at_date,
                                                      closest_conv_cache)
                factor2 = currency_conversion_on_date(account.parent.commodity, commodity, at_date, closest_conv_cache)
            else:
                factor1 = float(account.commodity.currency_conversion(account.parent.commodity))
                factor2 = float(account.parent.commodity.currency_conversion(commodity))
            factor = factor1 * factor2
            balance = balance * factor

    if recurse and account.children:
        balance += sum(
            get_historical_balance(
                account=acc,
                recurse=recurse,
                commodity=commodity,
                natural_sign=False,
                at_date=at_date,
                closest_conv_cache=closest_conv_cache
            )
            for acc in account.children
        )
    balance = float(balance)
    if natural_sign:
        return balance * account.sign
    else:
        return balance
