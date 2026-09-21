"""The same rules as the local backtest, written for the QuantConnect engine.

Paste this into a QuantConnect Python project. The signal logic is identical to
`momentum/strategy.py`: long when the 50 day average is above the 200 day one
and 21 day realised volatility is at or below the cap, flat otherwise.

QuantConnect's indicators are updated by the engine on each bar, so unlike the
local backtest there is no need to shift anything: at the moment the scheduled
event fires, the indicators hold only information from bars that have already
closed.
"""

from AlgorithmImports import *
import numpy as np


class TrendFollowingSPXL(QCAlgorithm):

    SHORT_WINDOW = 50
    LONG_WINDOW = 200
    VOL_WINDOW = 21
    VOL_CAP = 0.45           # annualised
    TRADING_DAYS = 252

    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2026, 8, 31)
        self.SetCash(1_000_000)

        equity = self.AddEquity("SPXL", Resolution.Daily)
        equity.SetDataNormalizationMode(DataNormalizationMode.Adjusted)
        self.symbol = equity.Symbol

        self.short_ma = self.SMA(self.symbol, self.SHORT_WINDOW, Resolution.Daily)
        self.long_ma = self.SMA(self.symbol, self.LONG_WINDOW, Resolution.Daily)

        # StandardDeviation of daily log returns, annualised when we read it.
        self.returns = self.LOGR(self.symbol, 1, Resolution.Daily)
        self.vol = IndicatorExtensions.Of(
            StandardDeviation(self.VOL_WINDOW), self.returns
        )

        # Warm the indicators up so the first trade is not taken on a
        # half-filled window.
        self.SetWarmUp(self.LONG_WINDOW + self.VOL_WINDOW, Resolution.Daily)

        self.Schedule.On(
            self.DateRules.EveryDay(self.symbol),
            self.TimeRules.BeforeMarketClose(self.symbol, 10),
            self.Rebalance,
        )

        self.invested_flag = False

    def Rebalance(self):
        if self.IsWarmingUp:
            return
        if not (self.short_ma.IsReady and self.long_ma.IsReady
                and self.vol.IsReady):
            return

        annualised_vol = self.vol.Current.Value * np.sqrt(self.TRADING_DAYS)
        trend_up = self.short_ma.Current.Value > self.long_ma.Current.Value
        calm = annualised_vol <= self.VOL_CAP

        want_long = trend_up and calm

        if want_long and not self.invested_flag:
            self.SetHoldings(self.symbol, 1.0)
            self.invested_flag = True
            self.Debug(f"{self.Time.date()} long, vol {annualised_vol:.1%}")
        elif not want_long and self.invested_flag:
            self.Liquidate(self.symbol)
            self.invested_flag = False
            reason = "trend" if not trend_up else "volatility"
            self.Debug(f"{self.Time.date()} flat on {reason}, "
                       f"vol {annualised_vol:.1%}")

        self.Plot("Signal", "Short MA", self.short_ma.Current.Value)
        self.Plot("Signal", "Long MA", self.long_ma.Current.Value)
        self.Plot("Risk", "Realised vol", annualised_vol)
        self.Plot("Risk", "Cap", self.VOL_CAP)
