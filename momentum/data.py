"""Price history download, cached on disk so backtests are reproducible."""

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE = Path(__file__).resolve().parents[1] / "data"


def load(ticker="SPXL", start="2010-01-01", end=None, refresh=False):
    """Return the adjusted close series, downloading it once and caching it.

    Adjusted prices are used so that dividends are reinvested, which matters
    for the buy and hold comparison.
    """
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{ticker}_{start}_{end or 'latest'}.csv"

    if path.exists() and not refresh:
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        return frame["close"]

    raw = yf.download(ticker, start=start, end=end, auto_adjust=True,
                      progress=False)
    if raw.empty:
        raise RuntimeError(f"no price history returned for {ticker}")

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):   # yfinance returns a frame for one ticker
        close = close.iloc[:, 0]
    close.name = "close"
    close.to_frame().to_csv(path)
    return close
