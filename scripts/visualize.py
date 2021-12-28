#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import date, timedelta
from sys import argv

import matplotlib.pyplot as plt
import matplotlib.dates as dates
import pandas as pd
import numpy as np

import piecash

from account_data import ALL_ASSETS, CASH_ASSETS, NON_CASH_ASSETS, get_expenses
from src.analysis import BookAnalysis
from src.utils import top_and_other

DATA_FILE = argv[1]

# Charts:
# - Total net assets over time (line chart)
# - Current cash by currency (pie chart)
# - Cash assets over time (area chart)
# - Non-cash assets over time (area chart)
# - Expenses by category over time (stacked bar chart)
# - Expenses by category (pie chart)

START = date(2021, 9, 1)
END = date.today()
STEP = timedelta(weeks=1)
CURRENCY = 'EUR'
#TOP_N = 10  #: For datasets with many categories, display largest TOP_N categories separately + "Other" category


def generate_plots(book: piecash.Book):

    analysis = BookAnalysis(book)
    EXPENSES = get_expenses(analysis.root_account)

    print('Setting up grid.')
    fig = plt.figure(figsize=(20, 10))
    totals_ax = plt.subplot2grid(shape=(2, 2), loc=(0, 0), colspan=1)
    currencies_ax = plt.subplot2grid((2, 2), (0, 1), colspan=1)
    expenses_time_ax = plt.subplot2grid((2, 2), (1, 0), colspan=1)
    expenses_pie_ax = plt.subplot2grid((2, 2), (1, 1), colspan=1)

    time_plots = [totals_ax, expenses_time_ax]

    print('Generating "Totals" figure.')
    # Totals: Total assets, separated into cash and non-cash assets as a stacked area chart, plus a line indicating net
    # assets.
    totals_df = pd.DataFrame({
        'Net': analysis.agg_balance_over_time(ALL_ASSETS + ['Liabilities'], START, END, STEP, CURRENCY),
        'Cash': analysis.agg_balance_over_time(CASH_ASSETS, START, END, STEP, CURRENCY),
        'Non-cash': analysis.agg_balance_over_time(NON_CASH_ASSETS, START, END, STEP, CURRENCY)
    })
    totals_ax.set_title('Totals')
    totals_ax.stackplot(
        totals_df.index,
        [totals_df['Cash'], totals_df['Non-cash']],
        labels=['Total cash', 'Total non-cash']
    )
    totals_ax.plot(
        totals_df.index,
        totals_df['Net'],
        label='Net'
    )
    totals_ax.legend()
    #totals_ax.xaxis_date()

    print('Generating "Currencies" figure.')
    # Currencies: Cash assets by currency, as a pie chart.
    currencies_series = analysis.agg_balance_by_currency(CASH_ASSETS, currency=CURRENCY)
    currencies_ax.set_title('Cash currencies')
    currencies_ax.pie(currencies_series, labels=currencies_series.index)

    print('Generating "Expenses over time" figure.')
    # Expenses over time: Expenses each week separated by category, as a stacked bar chart.
    expenses_time_df = top_and_other(analysis.diff_balances_over_time(EXPENSES, START, END, STEP, CURRENCY), 5)
    #print(expenses_time_df.index)
    expenses_time_ax.set_title('Expenses over time')
    bottom = np.zeros(expenses_time_df.shape[0],)
    for category in expenses_time_df.columns:
        values = expenses_time_df[category]
        expenses_time_ax.bar(expenses_time_df.index, values, bottom=bottom, label=category)
        bottom += values
    #expenses_time_df.plot.bar(ax=expenses_time_ax, stacked=True)
    expenses_time_ax.legend()
    expenses_time_ax.xaxis_date()

    print('Generating "Expenses by category" figure.')
    # Expense categories: Main categories of expenses, as a pie chart.
    expenses_category_series = top_and_other(analysis.balances(EXPENSES, currency=CURRENCY), 15)
    expenses_pie_ax.set_title('Expenses by category')
    expenses_pie_ax.pie(expenses_category_series, labels=expenses_category_series.index)

    print('Doing some magic to the axis labels.')
    for a in time_plots:
        a.xaxis.set_major_locator(dates.MonthLocator())
        a.xaxis.set_major_formatter(dates.DateFormatter('%b-%y'))

    # automft_xdate turns off x labels on the top plots so don't call
    #fig.autofmt_xdate()

    for a in time_plots:
        plt.setp(a.get_xticklabels(), rotation='vertical',
                 horizontalalignment='center', visible=True)

    print('Showing figures.')
    fig_mgr = plt.get_current_fig_manager()
    fig_mgr.show()
    # plt.subplots_adjust(#top=0.948,
    #                    bottom=0.102,
    #                    left=0.051,
    #                    right=0.985,
    #                    hspace=0.266)
    #                    wspace=0.471)
    plt.tight_layout()
    plt.show()
    # plt.savefig('finances.png')


if __name__ == '__main__':
    from sys import argv
    with piecash.open_book(argv[1]) as b:
        generate_plots(b)
