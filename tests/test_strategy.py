"""Tests focused on the two ways a backtest like this usually lies to you:
reading information from the future, and leaving out costs.
"""

import numpy as np
import pandas as pd
import pytest

from momentum import backtest, statistics
from momentum.strategy import positions, realised_volatility, signal


def make_prices(values, start="2015-01-01"):
    index = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=index, dtype=float)


def trending_prices(n=600, drift=0.0008, seed=0):
    rng = np.random.default_rng(seed)
    returns = drift + 0.01 * rng.standard_normal(n)
    return make_prices(100.0 * np.exp(np.cumsum(returns)))


def test_position_is_lagged_by_one_day():
    """Today's position must be built from yesterday's signal, never today's."""
    prices = trending_prices()
    raw = signal(prices)
    held = positions(prices)
    pd.testing.assert_series_equal(held, raw.shift(1), check_names=False)


def test_no_lookahead_when_future_is_changed():
    """Rewriting the tail of the series must leave earlier positions untouched.

    If any indicator were centred or forward-filled from the future, changing
    the last part of the price history would move earlier signals. This is the
    test that catches look-ahead bias directly rather than by inspection.
    """
    prices = trending_prices()
    cut = len(prices) - 50

    original = positions(prices).iloc[:cut]
    tampered = prices.copy()
    tampered.iloc[cut:] *= 3.0
    after = positions(tampered).iloc[:cut]

    pd.testing.assert_series_equal(original, after)


def test_signal_is_nan_before_windows_are_filled():
    prices = trending_prices(n=300)
    raw = signal(prices, short_window=50, long_window=200)
    assert raw.iloc[:199].isna().all()
    assert raw.iloc[200:].notna().all()


def test_costs_reduce_returns():
    prices = trending_prices()
    free = backtest.run(prices, cost_bps=0.0)
    charged = backtest.run(prices, cost_bps=50.0)
    assert charged["strategy_wealth"].iloc[-1] < free["strategy_wealth"].iloc[-1]


def test_no_trade_means_no_cost():
    """A series that never generates a signal must not be charged anything."""
    flat = make_prices(np.full(400, 100.0))
    frame = backtest.run(flat, cost_bps=50.0)
    assert frame["cost"].sum() == pytest.approx(0.0)


def test_strategy_matches_buy_and_hold_when_always_invested():
    """With the filters disabled the strategy must reproduce the asset itself."""
    prices = trending_prices()
    frame = backtest.run(prices, cost_bps=0.0, short_window=1, long_window=2,
                         vol_cap=1e9)
    invested = frame[frame["position"] == 1.0]
    pd.testing.assert_series_equal(
        invested["net_return"], invested["asset_return"], check_names=False
    )


def test_volatility_filter_forces_flat():
    """A violent series must be filtered out whatever the trend is doing."""
    rng = np.random.default_rng(3)
    returns = 0.002 + 0.09 * rng.standard_normal(500)   # ~140% annualised
    prices = make_prices(100.0 * np.exp(np.cumsum(returns)))
    held = positions(prices, vol_cap=0.30).dropna()
    assert held.sum() == 0


def test_realised_volatility_recovers_a_known_sigma():
    """Simulated returns with a known sigma must be measured back correctly."""
    sigma = 0.25
    rng = np.random.default_rng(11)
    daily = sigma / np.sqrt(252)
    returns = daily * rng.standard_normal(4000)
    prices = make_prices(100.0 * np.exp(np.cumsum(returns)))

    measured = realised_volatility(prices, window=252).dropna().mean()
    assert measured == pytest.approx(sigma, rel=0.06)


def test_statistics_on_a_known_series():
    """A constant 1% daily gain has a known CAGR and a zero drawdown."""
    returns = pd.Series([0.01] * 252)
    stats = statistics(returns)
    assert stats["cagr"] == pytest.approx(1.01 ** 252 - 1, rel=1e-9)
    assert stats["max_drawdown"] == pytest.approx(0.0)
    assert stats["hit_rate"] == pytest.approx(1.0)


def test_max_drawdown_is_measured_correctly():
    returns = pd.Series([0.5, -0.5, 0.0])   # 1.5 then 0.75, a 50% drawdown
    assert statistics(returns)["max_drawdown"] == pytest.approx(-0.5)
