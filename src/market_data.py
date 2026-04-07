from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class MarketDataConfig:
    period: str = "1y"
    min_rows: int = 90


def _compute_rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def _safe_float(value: Any, digits: int = 4) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (np.floating, float, int, np.integer)):
        if np.isnan(value):
            return 0.0
        return round(float(value), digits)
    return 0.0


def fetch_market_data_summary(ticker: str, config: MarketDataConfig | None = None) -> Dict[str, Any]:
    """Fetch and compute all indicators needed by both strategies."""
    cfg = config or MarketDataConfig()
    history = yf.Ticker(ticker).history(period=cfg.period, interval="1d", auto_adjust=False)
    if history.empty or len(history) < cfg.min_rows:
        raise ValueError(f"Not enough historical data for {ticker}. Need >= {cfg.min_rows} rows.")

    df = history.copy()
    df = df.dropna(subset=["Close", "Volume"])
    close = df["Close"]
    volume = df["Volume"]
    returns = close.pct_change()

    current_price = float(close.iloc[-1])
    idx_30 = -31 if len(close) >= 31 else 0
    price_30d_ago = float(close.iloc[idx_30])
    pct_change_30d = ((current_price / price_30d_ago) - 1) * 100 if price_30d_ago else 0.0
    avg_daily_volume_30d = float(volume.tail(30).mean())
    volatility_30d = float(returns.tail(30).std())
    moving_avg_20d = float(close.rolling(window=20).mean().iloc[-1])
    moving_avg_50d = float(close.rolling(window=50).mean().iloc[-1])

    recent_volume = volume.tail(10).mean()
    prior_volume = volume.tail(30).head(20).mean()
    volume_trend_ratio = float(recent_volume / prior_volume) if prior_volume else 0.0

    trailing_window = close.tail(min(252, len(close)))
    high_52w = float(trailing_window.max())
    low_52w = float(trailing_window.min())
    distance_from_52w_high_pct = ((current_price / high_52w) - 1) * 100 if high_52w else 0.0
    distance_from_52w_low_pct = ((current_price / low_52w) - 1) * 100 if low_52w else 0.0

    lookback_90 = close.tail(90)
    peak_90 = float(lookback_90.max())
    recent_drawdown_90d_pct = ((current_price / peak_90) - 1) * 100 if peak_90 else 0.0
    rsi_14 = _compute_rsi(close, window=14)

    summary = {
        "ticker": ticker.upper(),
        "run_date": date.today().isoformat(),
        "current_price": _safe_float(current_price, 2),
        "price_30d_ago": _safe_float(price_30d_ago, 2),
        "pct_change_30d": _safe_float(pct_change_30d, 2),
        "avg_daily_volume": int(round(avg_daily_volume_30d)),
        "volatility_30d": _safe_float(volatility_30d, 4),
        "moving_avg_20d": _safe_float(moving_avg_20d, 2),
        "moving_avg_50d": _safe_float(moving_avg_50d, 2),
        "volume_trend_ratio_10d_over_prev20d": _safe_float(volume_trend_ratio, 3),
        "high_52w": _safe_float(high_52w, 2),
        "low_52w": _safe_float(low_52w, 2),
        "distance_from_52w_high_pct": _safe_float(distance_from_52w_high_pct, 2),
        "distance_from_52w_low_pct": _safe_float(distance_from_52w_low_pct, 2),
        "recent_drawdown_90d_pct": _safe_float(recent_drawdown_90d_pct, 2),
        "rsi_14": _safe_float(rsi_14, 2),
    }
    return summary
