import datetime

import pandas as pd
import piecash

# TODO: Find out whether we can actually alter prices via piecash...

CURRENCY_ISO = {
    '€': 'EUR',
    '£': 'GBP'
}

def _add_price(book: piecash.Book, security: piecash.Commodity, currency: piecash.Commodity, value: float,
               date: datetime.date = None):
    if date is None:
        date = datetime.date.today()
    latest_price = security.prices.filter(piecash.Price.date <= date).order_by(piecash.Price.date.desc).first()
    if latest_price.date == date:
        # Price already exists for date; don't do anything
        return None
    new_price = piecash.Price(security, currency, date, value)

def add_prices(data: pd.DataFrame, book: piecash.Book) -> dict[str, tuple[float, float]]:
    """Add the given prices to the given GnuCash book, only if they are different to the most recent price already
    in the book.

    :param data: A :class:`pandas.DataFrame` build from the CSV exported from Seedrs.
    :param book: A :class:`piecash.Book` to which to add the prices.
    :return: A dict with information about price changes. Each key is the name of a security whose price has changed;
        the corresponding value is a tuple containing the old price and the new price.
    """
    CURRENCIES = {k: book.commodities(mnemonic=CURRENCY_ISO[k]) for k in CURRENCY_ISO}

    data['currency'] = data['Current price'].str[0].replace(CURRENCIES)
    data['value'] = data['Current price'].str[1:].astype(float)
    data['security'] = data['Business'].apply(lambda n: book.commodities(mnemonic=n))

