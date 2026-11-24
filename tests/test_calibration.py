"""Unit tests for src.calibration module."""

from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.calibration import (
    estimate_average_daily_volume,
    estimate_depth_parameters,
    estimate_intraday_volume_profile,
    estimate_permanent_impact_parameters,
    estimate_rolling_volatility,
    estimate_spread_parameters,
    estimate_temporary_impact_parameters,
    estimate_transaction_cost_schedule,
    estimate_volatility_percentiles,
    generate_calibration_summary,
    save_calibration_report,
)
from src.config import get_config


@pytest.fixture
def multi_day_ohlcv_df() -> pd.DataFrame:
    """Fixture with 5 consecutive trading days of 1-minute OHLCV data."""
    days = pd.bdate_range("2024-01-01", periods=5)
    records = []
    np.random.seed(42)
    base_price = 2500.0

    for day in days:
        day_str = day.strftime("%Y-%m-%d")
        times = pd.date_range(f"{day_str} 09:15:00", f"{day_str} 15:30:00", freq="1min", tz="Asia/Kolkata")
        n = len(times)
        # U-shaped volume
        u = 1.0 + 2.0 * ((np.arange(n) - n / 2) / (n / 2)) ** 2
        vols = np.random.poisson(lam=500 * u)
        rets = np.random.normal(0, 0.001, n)
        prices = base_price * np.exp(np.cumsum(rets))

        for i in range(n):
            records.append({
                "timestamp": times[i],
                "open": prices[i],
                "high": prices[i] + 1.0,
                "low": prices[i] - 1.0,
                "close": prices[i],
                "volume": max(10, int(vols[i])),
            })
        base_price = prices[-1]

    return pd.DataFrame(records)


def test_estimate_average_daily_volume(multi_day_ohlcv_df):
    """Test ADV estimation across multiple sessions."""
    res = estimate_average_daily_volume(multi_day_ohlcv_df)
    assert res["trading_days_count"] == 5
    assert res["adv_mean"] > 0
    assert res["adv_median"] > 0
    assert res["daily_turnover_inr"] > 0


def test_estimate_intraday_volume_profile(multi_day_ohlcv_df):
    """Test that intraday volume profile buckets sum strictly to 1.0."""
    profile = estimate_intraday_volume_profile(multi_day_ohlcv_df, num_buckets=13)
    assert len(profile.buckets_30m) == 13
    assert len(profile.intraday_1min) == 375
    # Sum of 1-minute fractions must be 1.0 within float precision
    assert np.isclose(sum(profile.intraday_1min), 1.0, atol=1e-5)
    assert np.isclose(sum(profile.buckets_30m.values()), 1.0, atol=1e-5)


def test_estimate_volatility_percentiles(multi_day_ohlcv_df):
    """Test volatility percentiles are monotonic and positive."""
    vol_series = estimate_rolling_volatility(multi_day_ohlcv_df, window=20)
    pcts = estimate_volatility_percentiles(vol_series, percentiles=(10.0, 40.0, 80.0, 95.0))
    assert "p40" in pcts
    assert "p80" in pcts
    assert pcts["p10"] <= pcts["p40"] <= pcts["p80"] <= pcts["p95"]
    assert pcts["p40"] > 0.0


def test_estimate_microstructure_parameters():
    """Test spread, depth, impact, and cost parameters match configuration."""
    cfg = get_config()
    spread_p = estimate_spread_parameters(cfg)
    depth_p = estimate_depth_parameters(cfg)
    temp_p = estimate_temporary_impact_parameters(cfg)
    perm_p = estimate_permanent_impact_parameters(cfg)
    costs = estimate_transaction_cost_schedule(cfg)

    assert spread_p["baseline_spread_bps"] == 5.0
    assert depth_p["multiplier"] == 0.05
    assert temp_p["exponent_alpha"] == 0.5
    assert perm_p["fraction_gamma"] == 0.10
    assert costs["configured_baseline_bps"] == 5.0


def test_generate_and_save_calibration_report(multi_day_ohlcv_df):
    """Test full calibration summary generation and serialization."""
    report = generate_calibration_summary(multi_day_ohlcv_df, ticker="RELIANCE")
    assert report.ticker == "RELIANCE"
    assert report.total_trading_days == 5
    assert report.volume_profile.sum_check > 0.99

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = save_calibration_report(report, output_dir=tmp_dir, format_type="json")
        yaml_path = save_calibration_report(report, output_dir=tmp_dir, format_type="yaml")
        assert json_path.exists()
        assert yaml_path.exists()
