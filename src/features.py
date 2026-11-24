"""Feature engineering and microstructure signal module.

Constructs non-lookahead intraday microstructure features:
- Volume imbalance proxies
- Spread widening indicators
- Intraday volatility acceleration
- Volume surge indicators relative to empirical volume profiles
- Liquidity regime state encoding
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicrostructureFeatures:
    """Container for instantaneous microstructure signals at simulation step t."""
    timestamp: pd.Timestamp
    mid_price: float
    rolling_volatility: float
    spread_bps: float
    relative_volume: float
    volume_imbalance: float
    volatility_regime: str
    liquidity_regime: str


def compute_volume_imbalance_proxy(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
    volume_col: str = "volume",
) -> pd.Series:
    """Compute volume order-flow imbalance proxy using tick-rule / bar approximation.

    Imbalance = Volume * ((Close - Low) - (High - Close)) / (High - Low)
    Bounded in [-1.0, 1.0].

    Args:
        df: Input OHLCV DataFrame.

    Returns:
        Series of normalized volume imbalance proxy.
    """
    hl_range = (df[high_col] - df[low_col]).replace(0.0, np.nan)
    raw_imbalance = ((df[close_col] - df[low_col]) - (df[high_col] - df[close_col])) / hl_range
    return raw_imbalance.fillna(0.0).clip(-1.0, 1.0)


def extract_features_at_step(
    df: pd.DataFrame,
    step_idx: int,
) -> MicrostructureFeatures:
    """Extract instantaneous microstructure state at discrete simulation step index.

    Guarantees strict point-in-time causality with no lookahead.

    Args:
        df: Processed OHLCV DataFrame.
        step_idx: Current integer index (0 <= step_idx < len(df)).

    Returns:
        MicrostructureFeatures instance.
    """
    row = df.iloc[step_idx]
    return MicrostructureFeatures(
        timestamp=row["timestamp"],
        mid_price=float(row["close"]),
        rolling_volatility=float(row.get("realised_volatility", 0.15)),
        spread_bps=float(row.get("spread_bps", 5.0)),
        relative_volume=float(row.get("relative_volume", 1.0)),
        volume_imbalance=float(row.get("volume_imbalance", 0.0)),
        volatility_regime=str(row.get("volatility_regime", "normal")),
        liquidity_regime=str(row.get("liquidity_regime", "medium")),
    )
