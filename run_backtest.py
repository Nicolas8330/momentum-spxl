"""Backtest the strategy on SPXL, print the results and draw the equity curve.

Run with:  python run_backtest.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from momentum import compare, round_trips, run, statistics, time_in_market
from momentum.data import load

START, END = "2010-01-01", "2026-09-01"
COST_BPS = 5.0

prices = load("SPXL", start=START, end=END)
frame = run(prices, cost_bps=COST_BPS)

print(f"SPXL, {frame.index[0].date()} to {frame.index[-1].date()}, "
      f"{COST_BPS:.0f}bp per trade")
print(f"50/200 day moving average crossover, flat above 45% realised vol")
print()

table = compare(frame)
labels = {
    "years": ("Years", "{:.1f}"),
    "total_return": ("Total return", "{:.1%}"),
    "cagr": ("CAGR", "{:.2%}"),
    "volatility": ("Volatility", "{:.1%}"),
    "sharpe": ("Sharpe", "{:.3f}"),
    "sortino": ("Sortino", "{:.3f}"),
    "max_drawdown": ("Max drawdown", "{:.1%}"),
    "calmar": ("Calmar", "{:.3f}"),
    "hit_rate": ("Positive days", "{:.1%}"),
    "worst_day": ("Worst day", "{:.1%}"),
}

print(f"{'':<16}{'Strategy':>12}{'Buy & hold':>13}")
print("-" * 41)
for key, (label, fmt) in labels.items():
    s = fmt.format(table.loc[key, "strategy"])
    b = fmt.format(table.loc[key, "buy_and_hold"])
    print(f"{label:<16}{s:>12}{b:>13}")

print()
print(f"Time invested      {time_in_market(frame):.1%}")
print(f"Entries            {round_trips(frame)}")
print(f"Total cost drag    {frame['cost'].sum():.2%}")

# --- does the result survive changing the parameters? ---------------------
print()
print("Sharpe across parameter pairs (cost included)")
shorts = [20, 50, 100]
longs = [150, 200, 250]
print(f"{'short/long':<12}" + "".join(f"{l:>8}" for l in longs))
for s in shorts:
    row = f"{s:<12}"
    for l in longs:
        if s >= l:
            row += f"{'-':>8}"
            continue
        f = run(prices, cost_bps=COST_BPS, short_window=s, long_window=l)
        row += f"{statistics(f['net_return'])['sharpe']:>8.2f}"
    print(row)

print()
print("Sharpe against the volatility cap")
for cap in (0.30, 0.40, 0.45, 0.60, 10.0):
    f = run(prices, cost_bps=COST_BPS, vol_cap=cap)
    stats = statistics(f["net_return"])
    label = "no filter" if cap > 1 else f"{cap:.0%}"
    print(f"  {label:<10} Sharpe {stats['sharpe']:5.2f}   "
          f"max DD {stats['max_drawdown']:7.1%}   "
          f"invested {time_in_market(f):5.1%}")

# --- equity curve ---------------------------------------------------------
fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(11, 7), sharex=True,
    gridspec_kw={"height_ratios": [3, 1]})

ax.plot(frame.index, frame["strategy_wealth"], color="#1f3a5f", linewidth=1.8,
        label="Strategy")
ax.plot(frame.index, frame["buy_hold_wealth"], color="#b5651d", linewidth=1.2,
        alpha=0.8, label="Buy and hold SPXL")
ax.set_yscale("log")
ax.set_ylabel("Growth of 1 (log scale)")
ax.set_title("50/200 crossover with a volatility filter on SPXL")
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)

wealth = frame["strategy_wealth"]
bh = frame["buy_hold_wealth"]
ax2.fill_between(frame.index, wealth / wealth.cummax() - 1.0, 0,
                 color="#1f3a5f", alpha=0.7, label="Strategy")
ax2.fill_between(frame.index, bh / bh.cummax() - 1.0, 0,
                 color="#b5651d", alpha=0.35, label="Buy and hold")
ax2.set_ylabel("Drawdown")
ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax2.legend(frameon=False, loc="lower right")
ax2.spines[["top", "right"]].set_visible(False)

fig.tight_layout()
fig.savefig("figures/equity_curve.png", dpi=140)
print()
print("Equity curve written to figures/equity_curve.png")
