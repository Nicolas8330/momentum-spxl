"""Signal rules for a trend-following strategy on a leveraged equity ETF.

The strategy is deliberately simple: hold the ETF when the short moving average
is above the long one, stay in cash otherwise, and step aside entirely when
realised volatility spikes. The point of the volatility filter is that SPXL is
3x leveraged, so a drawdown in the underlying is amplified and the daily
rebalancing of the ETF bleeds value when the market chops around.

Every signal is computed on information available strictly before the trade is
placed. `positions()` shifts the signal by one day for exactly that reason.
"""

import numpy as np
import pandas as pd


def moving_averages(prices, short_window=50, long_window=200):
    """Simple moving averages of the close.

    `min_periods` is left at the window length, so the averages are NaN until
    there is enough history. That keeps the first months out of the backtest
    rather than trading on a half-filled window.
    """
    short = prices.rolling(short_window, min_periods=short_window).mean()
    long = prices.rolling(long_window, min_periods=long_window).mean()
    return short, long


def realised_volatility(prices, window=21, annualise=True):
    """Annualised standard deviation of daily log returns."""
    returns = np.log(prices).diff()
    vol = returns.rolling(window, min_periods=window).std()
    if annualise:
        vol = vol * np.sqrt(252)
    return vol


def signal(prices, short_window=50, long_window=200, vol_window=21,
           vol_cap=0.45):
    """Return 1 when the strategy wants to be long, 0 when it wants cash.

    Two conditions have to hold at the same time:
      - the short moving average is above the long one (the trend is up),
      - realised volatility is at or below `vol_cap`.

    The default cap of 45% annualised is high because this is a 3x ETF: its
    own realised volatility runs around three times the index's. The filter is
    meant to catch crisis regimes, not ordinary noise.
    """
    short, long = moving_averages(prices, short_window, long_window)
    vol = realised_volatility(prices, vol_window)

    trend_up = short > long
    calm = vol <= vol_cap

    raw = (trend_up & calm).astype(float)
    # Before the long window is filled there is no signal at all, and an
    # unfilled window must not be read as "flat".
    raw[short.isna() | long.isna() | vol.isna()] = np.nan
    return raw


def positions(prices, **kwargs):
    """Position actually held, lagged by one day.

    The signal on day t is built from the close of day t, so the earliest it
    can be traded is the close of day t+1. Without this shift the backtest
    would be reading tomorrow's information, which is the single most common
    way to produce a backtest that cannot be traded.
    """
    return signal(prices, **kwargs).shift(1)


def turnover(positions):
    """Fraction of capital traded on each day."""
    return positions.diff().abs().fillna(0.0)
