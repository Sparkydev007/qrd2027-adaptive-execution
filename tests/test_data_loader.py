"""Unit tests for src.data_loader module."""

from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data_loader import (
    assign_liquidity_regimes,
    assign_volatility_regimes,
    calculate_dollar_volume,
    calculate_log_returns,
    calculate_relative_volume,
    calculate_rolling_realised_volatility,
    filter_market_hours,
    handle_missing_candles,
    load_raw_data,
    parse_timestamps,
    remove_duplicate_timestamps,
    save_processed_data,
    sort_by_timestamp,
    validate_required_columns,
)


@pytest.fixture
def synthetic_ohlcv_df() -> pd.DataFrame:
    """Fixture providing clean synthetic 1-minute OHLCV data."""
    times = pd.date_range("2024-01-01 09:15:00", "2024-01-01 15:30:00", freq="1min", tz="Asia/Kolkata")
    n = len(times)
    np.random.seed(123)
    closes = 2500.0 + np.cumsum(np.random.normal(0, 1.0, n))
    df = pd.DataFrame({
        "timestamp": [str(t) for t in times],
        "open": closes + np.random.normal(0, 0.5, n),
        "high": closes + np.abs(np.random.normal(1.0, 0.5, n)),
        "low": closes - np.abs(np.random.normal(1.0, 0.5, n)),
        "close": closes,
        "volume": np.random.randint(100, 5000, n),
    })
    return df


def test_validate_required_columns_success(synthetic_ohlcv_df):
    """Test 1: Required columns exist."""
    assert validate_required_columns(synthetic_ohlcv_df) is True


def test_validate_required_columns_missing():
    """Test 1b: Missing required column raises ValueError."""
    bad_df = pd.DataFrame({"open": [100], "close": [101]})
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_required_columns(bad_df)


def test_parse_timestamps_timezone(synthetic_ohlcv_df):
    """Test 2: Timestamps parsed correctly and localized to Asia/Kolkata."""
    parsed = parse_timestamps(synthetic_ohlcv_df, target_timezone="Asia/Kolkata")
    ts = parsed["timestamp"]
    assert pd.api.types.is_datetime64_any_dtype(ts)
    assert str(ts.dt.tz) == "Asia/Kolkata"


def test_remove_duplicate_timestamps():
    """Test 3: Duplicate timestamps are removed."""
    df = pd.DataFrame({
        "timestamp": ["2024-01-01 09:15:00", "2024-01-01 09:15:00", "2024-01-01 09:16:00"],
        "close": [100.0, 100.5, 101.0],
    })
    dedup = remove_duplicate_timestamps(df, keep="last")
    assert len(dedup) == 2
    assert dedup.iloc[0]["close"] == 100.5


def test_sort_by_timestamp():
    """Test 4: Data is strictly sorted by timestamp ascending."""
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01 09:20:00", "2024-01-01 09:15:00"]),
        "close": [200.0, 199.0],
    })
    sorted_df = sort_by_timestamp(df)
    assert sorted_df["timestamp"].iloc[0] < sorted_df["timestamp"].iloc[1]
    assert sorted_df.index.tolist() == [0, 1]


def test_filter_market_hours(synthetic_ohlcv_df):
    """Test 5: Market-hours filtering retains only 09:15 to 15:30 IST."""
    parsed = parse_timestamps(synthetic_ohlcv_df, target_timezone="Asia/Kolkata")
    # Add pre-market and post-market rows
    pre_row = parsed.iloc[[0]].copy()
    pre_row["timestamp"] = pd.to_datetime("2024-01-01 09:00:00").tz_localize("Asia/Kolkata")
    post_row = parsed.iloc[[0]].copy()
    post_row["timestamp"] = pd.to_datetime("2024-01-01 15:45:00").tz_localize("Asia/Kolkata")
    extended = pd.concat([pre_row, parsed, post_row], ignore_index=True)

    filtered = filter_market_hours(extended, start_time="09:15", end_time="15:30")
    assert len(filtered) == len(parsed)
    times = filtered["timestamp"].dt.time
    assert (times >= pd.to_datetime("09:15").time()).all()
    assert (times <= pd.to_datetime("15:30").time()).all()


def test_calculate_log_returns(synthetic_ohlcv_df):
    """Test 6: Log returns calculated correctly and first element is 0.0."""
    df = calculate_log_returns(synthetic_ohlcv_df, price_col="close")
    assert "returns" in df.columns
    assert df["returns"].iloc[0] == 0.0
    expected_r1 = np.log(synthetic_ohlcv_df["close"].iloc[1] / synthetic_ohlcv_df["close"].iloc[0])
    assert np.isclose(df["returns"].iloc[1], expected_r1)


def test_calculate_realised_volatility_non_negative(synthetic_ohlcv_df):
    """Test 7: Realised volatility is strictly non-negative."""
    df_ret = calculate_log_returns(synthetic_ohlcv_df)
    df_vol = calculate_rolling_realised_volatility(df_ret, window=10)
    assert "realised_volatility" in df_vol.columns
    assert (df_vol["realised_volatility"] >= 0.0).all()
    assert not df_vol["realised_volatility"].isna().any()


def test_assign_volatility_regimes():
    """Test 8: Volatility regimes are assigned correctly based on percentiles."""
    vols = np.linspace(0.10, 0.50, 100)
    df = pd.DataFrame({"realised_volatility": vols})
    df_regime = assign_volatility_regimes(df, calm_max_pct=40.0, stressed_min_pct=80.0)
    assert "volatility_regime" in df_regime.columns
    regimes = set(df_regime["volatility_regime"].unique())
    assert regimes.issubset({"calm", "normal", "stressed"})
    assert df_regime["volatility_regime"].iloc[0] == "calm"
    assert df_regime["volatility_regime"].iloc[-1] == "stressed"


def test_assign_liquidity_regimes():
    """Test 9: Liquidity regimes assigned correctly into low, medium, high."""
    vols = np.arange(100, 200)
    df = pd.DataFrame({"volume": vols})
    df_liq = assign_liquidity_regimes(df, low_max_pct=33.33, high_min_pct=66.67)
    assert "liquidity_regime" in df_liq.columns
    regimes = set(df_liq["liquidity_regime"].unique())
    assert regimes == {"low", "medium", "high"}


def test_save_and_load_processed_data(synthetic_ohlcv_df):
    """Test 10: Saving to and loading from Parquet maintains integrity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pq_path = Path(tmp_dir) / "test_out.parquet"
        save_processed_data(synthetic_ohlcv_df, pq_path)
        assert pq_path.exists()
        loaded = load_raw_data(pq_path)
        assert len(loaded) == len(synthetic_ohlcv_df)
        assert set(loaded.columns) == set(synthetic_ohlcv_df.columns)
