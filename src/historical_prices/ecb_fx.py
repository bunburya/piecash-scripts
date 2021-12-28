from datetime import date, datetime
from urllib.request import urlopen
from warnings import warn
from xml.etree.ElementTree import Element, ElementTree

import pandas as pd

from ..exceptions import PriceNotFoundError, BadDataError

XML_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'

ECB_NS = {
    'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
    'ecb': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
}


def get_xml(url: str = XML_URL) -> ElementTree:
    """Get an ElementTree representing historical ECB exchange rate data from the given URL."""
    return ElementTree(file=urlopen(url))


def ecb_fx_rate_from_eur(xml_cube: Element, currency: str) -> float:
    """Search the given XML element and return the conversion rate from EUR to the given currency.

    :param xml_cube: An ecb:Cube element for a given date, containing exchange rates.
    :param currency: The currency to search for, as an ISO 4217 string.
    :return: The exchange rate from EUR to the given currency.
    :raise PriceNotFoundError if the relevant exchange rate cannot be found.
    """
    for c in xml_cube.findall('.//ecb:Cube', namespaces=ECB_NS):
        attrib = c.attrib
        if attrib['currency'] == currency:
            return float(attrib['rate'])

    raise PriceNotFoundError(f'Could not find exchange rate from EUR to {currency} on {xml_cube.attrib["time"]}.')


def ecb_fx_rate(xml_cube: Element, to_currency: str, from_currency: str = 'EUR') -> float:
    """Calculate the exchange rate between the given currencies based on the given XML element.

    If both currencies are the same, 1 is returned. If the `to_currency` is EUR, the exchange rate from EUR to
    `from_currency` is found, and then the reciprocal of that rate is returned. If neither currency is EUR, the exchange
    from EUR to each currency is found, and rate for `to_currency` is divided by the rate for `from_currency`.

    :param xml_cube: An ecb:Cube element for a given date, containing exchange rates.
    :param to_currency: The currency to convert to, as an ISO 4217 string.
    :param from_currency: The currency to convert from, as an ISO 4217 string.
    """

    if to_currency == from_currency:
        return 1

    if from_currency == 'EUR':
        return ecb_fx_rate_from_eur(xml_cube, to_currency)
    elif to_currency == 'EUR':
        return 1 / ecb_fx_rate_from_eur(xml_cube, from_currency)
    else:
        return ecb_fx_rate_from_eur(xml_cube, to_currency) / ecb_fx_rate_from_eur(xml_cube, from_currency)


def ecb_fx_rate_range(xml_root: Element, start_date: date, end_date: date, to_currency: str,
                      from_currency: str = 'EUR', exclude_dates: set = None) -> dict[date, float]:
    """Get the exchange rate for the given currencies on each date between `start_date` and `end_date` (inclusive),
    based on the given XML root element.

    Will warn non-fatally if the relevant rates cannot be obtained on any relevant date.

    :param xml_root: The root XML element in the XML file of historical exchange rates published by the ECB.
    :param start_date: The beginning of the date range to search.
    :param end_date: The end of the date range to search.
    :param to_currency: The currency to convert to, as an ISO 4217 string.
    :param from_currency: The currency to convert from, as an ISO 4217 string.
    :param exclude_dates: A set of specific dates to exclude from the results.
    """
    if exclude_dates is None:
        exclude_dates = set()
    results = {}
    top_cube = xml_root.find('ecb:Cube', namespaces=ECB_NS)
    if top_cube is None:
        raise BadDataError('Could not find top-level "Cube" element within XML root.')
    for date_cube in top_cube.findall('ecb:Cube', namespaces=ECB_NS):
        attr = date_cube.attrib
        _date = datetime.strptime(attr['time'], '%Y-%m-%d').date()
        if (start_date < _date <= end_date) and not (_date in exclude_dates):
            try:
                results[_date] = ecb_fx_rate(date_cube, to_currency, from_currency)
            except PriceNotFoundError as e:
                warn(e.args[0])
    return results


def get_data_ecb(pair: str, start: date, end: date) -> pd.Series:
    """Get the exchange rate for the given currency pair on each date between `start` and `end` (inclusive).

    :param pair: The currency pay to look up in the format 'TO/FROM', eg, 'EUR/GBP'.
    :param start: The beginning of the date range to search.
    :param end: The end of the date range to search.
    """
    xml_root = get_xml().getroot()
    to_currency, from_currency = pair.split('/')
    return pd.Series(ecb_fx_rate_range(xml_root, start, end, to_currency, from_currency))


if __name__ == '__main__':
    # Test
    from sys import argv

    etree = ElementTree(file=argv[1])
    root = etree.getroot()
    # print(ecb_fx_rate_range(root, date(2019, 1, 1), date(2020, 1, 1), 'GBP'))
    print(ecb_fx_rate_range(root, date(2019, 1, 1), date(2020, 1, 1), 'USD', 'GBP'))
