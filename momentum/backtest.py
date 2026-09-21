"""Vectorised backtest with transaction costs, and the usual performance stats."""

import numpy as np
import pandas as pd

from .strategy import positions, turnover

TRADING_DAYS = 252


def run(prices, cost_bps=5.0, **strategy_kwargs):
    """Backtest the strategy on a price series.

    `cost_bps` is charged on the notional traded each time the position
    changes, which for a one-in one-out signal means it is paid twice per round
    trip. Five basis points is a reasonable retail assumption on a liquid ETF.

    Returns a DataFrame indexed by date with the position held, the strategy
    return net of costs, and the cumulative wealth of the strategy against
    buy and hold.
    """
    prices = prices.dropna()
    asset_returns = prices.pct_change()

    pos = positions(prices, **strategy_kwargs)
    traded = turnover(pos)
    costs = traded * (cost_bps / 10_000.0)

    gross = pos * asset_returns
    net = gross - costs

    frame = pd.DataFrame({
        "price": prices,
        "position": pos,
        "asset_return": asset_returns,
        "gross_return": gross,
        "cost": costs,
        "net_return": net,
    })
    frame = frame.dropna(subset=["position", "net_return"])

    frame["strategy_wealth"] = (1.0 + frame["net_return"]).cumprod()
    frame["buy_hold_wealth"] = (1.0 + frame["asset_return"]).cumprod()
    return frame


def statistics(returns, risk_free=0.0):
    """Standard performance summary for a series of daily returns."""
    returns = returns.dropna()
    if returns.empty:
        return {}

    n_years = len(returns) / TRADING_DAYS
    total_growth = float((1.0 + returns).prod())
    cagr = total_growth ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan

    vol = float(returns.std() * np.sqrt(TRADING_DAYS))
    excess = returns - risk_free / TRADING_DAYS
    sharpe = float(excess.mean() / returns.std() * np.sqrt(TRADING_DAYS)) \
        if returns.std() > 0 else np.nan

    downside = returns[returns < 0]
    sortino = float(returns.mean() / downside.std() * np.sqrt(TRADING_DAYS)) \
        if not downside.empty and downside.std() > 0 else np.nan

    wealth = (1.0 + returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    max_dd = float(drawdown.min())

    return {
        "years": n_years,
        "total_return": total_growth - 1.0,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": cagr / abs(max_dd) if max_dd < 0 else np.nan,
        # Days flat are not days lost, so the hit rate is measured only over
        # the days the strategy actually had a position on.
        "hit_rate": (float((returns > 0).sum() / (returns != 0).sum())
                     if (returns != 0).any() else np.nan),
        "best_day": float(returns.max()),
        "worst_day": float(returns.min()),
    }


def compare(frame):
    """Statistics for the strategy and for buy and hold, side by side."""
    return pd.DataFrame({
        "strategy": statistics(frame["net_return"]),
        "buy_and_hold": statistics(frame["asset_return"]),
    })


def time_in_market(frame):
    return float(frame["position"].mean())


def round_trips(frame):
    """Number of times the strategy went from flat to invested."""
    pos = frame["position"]
    entries = (pos.diff() > 0).sum()
    return int(entries)
