"""Data ingestion, normalization, and feature augmentation module.

Loads 1-minute OHLCV market data, validates schema, localizes timezone to Asia/Kolkata,
filters regular market trading hours (09:15-15:30 IST), cleans discontinuities,
and augments data with non-lookahead return, volatility, volume, and regime indicators.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union, Sequence
import numpy as np
import pandas as pd

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)

REQUIRED_OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def load_raw_data(
    file_path: Union[str, Path],
    columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Load raw OHLCV market data from a CSV or Parquet file.

    Args:
        file_path: Path to the raw CSV or Parquet data file.
        columns: Optional sequence of columns to read.

    Returns:
        pd.DataFrame containing the raw tabular data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Raw data file not found: {path}")

    logger.info("Reading raw market data from %s", path)
    suffix = path.suffix.lower()
    if suffix in [".csv", ".txt"]:
        df = pd.read_csv(path, usecols=columns)
    elif suffix in [".parquet", ".pq"]:
        df = pd.read_parquet(path, columns=columns)
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Expected .csv or .parquet")

    # Normalize column names to lowercase stripped strings
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def validate_required_columns(
    df: pd.DataFrame,
    required_cols: Sequence[str] = REQUIRED_OHLCV_COLUMNS,
) -> bool:
    """Validate that all mandatory OHLCV columns exist in the DataFrame.

    Args:
        df: Input DataFrame.
        required_cols: Required column names.

    Returns:
        True if all required columns are present.

    Raises:
        ValueError: If any required column is missing.
    """
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        error_msg = f"Data validation failed. Missing required columns: {missing}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return True


def parse_timestamps(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    target_timezone: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Parse timestamp column to datetime and localize to target timezone.

    Args:
        df: Input DataFrame.
        timestamp_col: Column name containing timestamps.
        target_timezone: Target timezone string (default: Asia/Kolkata).

    Returns:
        DataFrame with parsed, timezone-aware datetime timestamp.
    """
    df = df.copy()
    if timestamp_col not in df.columns:
        raise ValueError(f"Timestamp column '{timestamp_col}' not found.")

    ts_series = pd.to_datetime(df[timestamp_col], errors="coerce")
    if ts_series.isna().any():
        num_invalid = ts_series.isna().sum()
        logger.warning("Found %d unparseable timestamps; dropping invalid rows.", num_invalid)
        df = df[ts_series.notna()].copy()
        ts_series = ts_series.dropna()

    if ts_series.dt.tz is None:
        # Naive datetime: assume it is already in target timezone or localize directly
        ts_series = ts_series.dt.tz_localize(target_timezone, ambiguous="infer", nonexistent="shift_forward")
    else:
        # Timezone-aware: convert to target timezone
        ts_series = ts_series.dt.tz_convert(target_timezone)

    df[timestamp_col] = ts_series
    return df


def filter_market_hours(
    df: pd.DataFrame,
    start_time: str = "09:15",
    end_time: str = "15:30",
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Filter records to regular trading hours inclusive of start and end.

    In the NSE cash equity market, regular continuous trading runs 09:15 to 15:30 IST.

    Args:
        df: Input DataFrame with parsed timestamp column.
        start_time: Market opening time string 'HH:MM'.
        end_time: Market closing time string 'HH:MM'.
        timestamp_col: Name of timestamp column.

    Returns:
        Filtered DataFrame containing only regular trading hours.
    """
    df = df.copy()
    times = df[timestamp_col].dt.time
    t_start = pd.to_datetime(start_time, format="%H:%M").time()
    t_end = pd.to_datetime(end_time, format="%H:%M").time()

    mask = (times >= t_start) & (times <= t_end)
    initial_len = len(df)
    df_filtered = df[mask].copy()
    logger.debug(
        "Market hours filter (%s-%s): kept %d of %d rows (%d dropped).",
        start_time,
        end_time,
        len(df_filtered),
        initial_len,
        initial_len - len(df_filtered),
    )
    return df_filtered


def remove_duplicate_timestamps(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    keep: str = "last",
) -> pd.DataFrame:
    """Detect and remove duplicate timestamps.

    Args:
        df: Input DataFrame.
        timestamp_col: Name of timestamp column.
        keep: Which duplicate to retain ('first', 'last', False).

    Returns:
        Deduplicated DataFrame.
    """
    initial_len = len(df)
    df_dedup = df.drop_duplicates(subset=[timestamp_col], keep=keep).copy()
    dropped = initial_len - len(df_dedup)
    if dropped > 0:
        logger.warning("Removed %d duplicate timestamp rows (kept %s).", dropped, keep)
    return df_dedup


def sort_by_timestamp(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Sort DataFrame monotonically by timestamp and reset index.

    Args:
        df: Input DataFrame.
        timestamp_col: Name of timestamp column.

    Returns:
        Sorted DataFrame with clean integer index.
    """
    df_sorted = df.sort_values(by=timestamp_col, ascending=True).reset_index(drop=True)
    return df_sorted


def handle_missing_candles(
    df: pd.DataFrame,
    frequency: str = "1min",
    start_time: str = "09:15",
    end_time: str = "15:30",
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Detect and regularize missing 1-minute intraday intervals per trading day.

    Forward-fills closing prices and sets zero volume for non-traded intervals
    to ensure stationary discrete time steps for simulation.

    Args:
        df: Input DataFrame.
        frequency: Expected interval frequency string (default: 1min).
        start_time: Daily session start 'HH:MM'.
        end_time: Daily session end 'HH:MM'.
        timestamp_col: Name of timestamp column.

    Returns:
        Regularized DataFrame with complete intraday time grid per session.
    """
    df = df.copy()
    if df.empty:
        return df

    tz = df[timestamp_col].dt.tz
    days = df[timestamp_col].dt.date.unique()

    full_grids = []
    for day in days:
        day_str = str(day)
        s_ts = pd.to_datetime(f"{day_str} {start_time}:00").tz_localize(tz)
        e_ts = pd.to_datetime(f"{day_str} {end_time}:00").tz_localize(tz)
        day_grid = pd.date_range(start=s_ts, end=e_ts, freq=frequency, tz=tz)
        full_grids.append(pd.DataFrame({timestamp_col: day_grid}))

    complete_grid = pd.concat(full_grids, ignore_index=True)
    merged = pd.merge(complete_grid, df, on=timestamp_col, how="left")

    # Forward fill price fields; fill missing volume with 0
    price_cols = [c for c in ["open", "high", "low", "close"] if c in merged.columns]
    for p_col in price_cols:
        merged[p_col] = merged[p_col].ffill().bfill()

    if "volume" in merged.columns:
        merged["volume"] = merged["volume"].fillna(0).astype(int)

    return merged.sort_values(by=timestamp_col).reset_index(drop=True)


def calculate_log_returns(
    df: pd.DataFrame,
    price_col: str = "close",
    output_col: str = "returns",
) -> pd.DataFrame:
    """Calculate 1-minute logarithmic price returns.

    Args:
        df: Input DataFrame.
        price_col: Price column to calculate returns from.
        output_col: Name of created return column.

    Returns:
        DataFrame with log return column (first value initialized to 0.0).
    """
    df = df.copy()
    prices = df[price_col].astype(float)
    returns = np.log(prices / prices.shift(1)).fillna(0.0)
    df[output_col] = returns
    return df


def calculate_rolling_realised_volatility(
    df: pd.DataFrame,
    return_col: str = "returns",
    window: int = 20,
    annualization_factor: float = np.sqrt(375 * 250),
    output_col: str = "realised_volatility",
) -> pd.DataFrame:
    """Calculate rolling realized volatility of returns.

    Args:
        df: Input DataFrame.
        return_col: Return column name.
        window: Rolling observation window in minutes.
        annualization_factor: Factor to annualize 1-minute volatility.
            Default = sqrt(375 minutes/day * 250 trading days/year) ~ 306.18.
        output_col: Output column name.

    Returns:
        DataFrame with realized volatility column.
    """
    df = df.copy()
    rolling_std = df[return_col].rolling(window=window, min_periods=max(2, window // 2)).std()
    # Backfill earliest window values to avoid NaN propagation in simulator
    rolling_std = rolling_std.bfill().fillna(0.0)
    df[output_col] = (rolling_std * annualization_factor).astype(float)
    return df


def calculate_dollar_volume(
    df: pd.DataFrame,
    price_col: str = "close",
    volume_col: str = "volume",
    output_col: str = "dollar_volume",
) -> pd.DataFrame:
    """Calculate traded turnover in currency units (INR).

    Args:
        df: Input DataFrame.
        price_col: Close price column.
        volume_col: Volume column.
        output_col: Dollar volume output column.

    Returns:
        DataFrame with dollar volume column.
    """
    df = df.copy()
    df[output_col] = (df[price_col].astype(float) * df[volume_col].astype(float)).fillna(0.0)
    return df


def calculate_relative_volume(
    df: pd.DataFrame,
    volume_col: str = "volume",
    window: int = 20,
    output_col: str = "relative_volume",
) -> pd.DataFrame:
    """Calculate relative volume: interval volume divided by rolling average volume.

    Args:
        df: Input DataFrame.
        volume_col: Volume column.
        window: Rolling baseline window.
        output_col: Output column name.

    Returns:
        DataFrame with relative volume ratio.
    """
    df = df.copy()
    rolling_vol = df[volume_col].rolling(window=window, min_periods=1).mean()
    # Avoid zero-division
    rel_vol = np.where(rolling_vol > 0, df[volume_col] / rolling_vol, 1.0)
    df[output_col] = rel_vol.astype(float)
    return df


def assign_volatility_regimes(
    df: pd.DataFrame,
    vol_col: str = "realised_volatility",
    calm_max_pct: float = 40.0,
    stressed_min_pct: float = 80.0,
    output_col: str = "volatility_regime",
) -> pd.DataFrame:
    """Assign discrete volatility regime labels: calm, normal, or stressed.

    Args:
        df: Input DataFrame.
        vol_col: Realized volatility column.
        calm_max_pct: Upper percentile for calm regime.
        stressed_min_pct: Lower percentile for stressed regime.
        output_col: Output column name.

    Returns:
        DataFrame with categorical volatility regime column.
    """
    df = df.copy()
    series = df[vol_col]
    q_low = float(np.percentile(series, calm_max_pct))
    q_high = float(np.percentile(series, stressed_min_pct))

    conditions = [
        series <= q_low,
        (series > q_low) & (series <= q_high),
        series > q_high,
    ]
    choices = ["calm", "normal", "stressed"]
    df[output_col] = np.select(conditions, choices, default="normal")
    return df


def assign_liquidity_regimes(
    df: pd.DataFrame,
    volume_col: str = "volume",
    low_max_pct: float = 33.33,
    high_min_pct: float = 66.67,
    output_col: str = "liquidity_regime",
) -> pd.DataFrame:
    """Assign discrete liquidity regime labels: low, medium, or high.

    Args:
        df: Input DataFrame.
        volume_col: Volume column name.
        low_max_pct: Upper percentile for low liquidity.
        high_min_pct: Lower percentile for high liquidity.
        output_col: Output column name.

    Returns:
        DataFrame with categorical liquidity regime column.
    """
    df = df.copy()
    series = df[volume_col]
    q_low = float(np.percentile(series, low_max_pct))
    q_high = float(np.percentile(series, high_min_pct))

    conditions = [
        series <= q_low,
        (series > q_low) & (series <= q_high),
        series > q_high,
    ]
    choices = ["low", "medium", "high"]
    df[output_col] = np.select(conditions, choices, default="medium")
    return df


def save_processed_data(
    df: pd.DataFrame,
    output_path: Union[str, Path],
) -> Path:
    """Save clean, augmented DataFrame to Parquet format.

    Args:
        df: Processed DataFrame.
        output_path: Target file path.

    Returns:
        Resolved Path of saved Parquet file.
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Saving processed dataset to %s (%d rows)", path, len(df))
    df.to_parquet(path, index=False, engine="pyarrow")
    return path


def process_ohlcv_pipeline(
    raw_path: Union[str, Path],
    config: Optional[AppConfig] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Execute the complete data ingestion and feature generation pipeline.

    Args:
        raw_path: Path to raw input data.
        config: Typed AppConfig. If None, default loaded from config/config.yaml.
        output_path: Optional destination to save processed Parquet.

    Returns:
        Clean, regularized, and augmented DataFrame.
    """
    cfg = config or get_config()

    df_raw = load_raw_data(raw_path)
    validate_required_columns(df_raw)
    df_ts = parse_timestamps(df_raw, target_timezone=cfg.data.timezone)
    df_hours = filter_market_hours(
        df_ts,
        start_time=cfg.data.market_hours.start,
        end_time=cfg.data.market_hours.end,
    )
    df_dedup = remove_duplicate_timestamps(df_hours)
    df_sorted = sort_by_timestamp(df_dedup)
    df_regular = handle_missing_candles(
        df_sorted,
        frequency=cfg.data.frequency,
        start_time=cfg.data.market_hours.start,
        end_time=cfg.data.market_hours.end,
    )
    df_returns = calculate_log_returns(df_regular)
    df_vol = calculate_rolling_realised_volatility(
        df_returns,
        window=cfg.calibration.volatility_window,
    )
    df_dollar = calculate_dollar_volume(df_vol)
    df_rel = calculate_relative_volume(
        df_dollar,
        window=cfg.calibration.volatility_window,
    )

    calm_max = cfg.simulation.regime_definitions["calm"].volatility_percentile_max or 40.0
    stressed_min = cfg.simulation.regime_definitions["stressed"].volatility_percentile_min or 80.0
    df_regime_vol = assign_volatility_regimes(
        df_rel,
        calm_max_pct=calm_max,
        stressed_min_pct=stressed_min,
    )
    df_final = assign_liquidity_regimes(df_regime_vol)

    if output_path is not None:
        save_processed_data(df_final, output_path)

    return df_final
