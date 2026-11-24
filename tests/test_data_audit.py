"""Unit tests for src.data_audit module."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_audit import (
    check_corporate_action_anomalies,
    check_duplicate_timestamps,
    check_extreme_returns,
    check_high_low_violation,
    check_missing_candles_in_session,
    check_missing_columns,
    check_monotonic_timestamps,
    check_open_close_within_high_low,
    check_zero_or_negative_prices,
    check_zero_or_negative_volume,
    run_comprehensive_audit,
)


@pytest.fixture
def clean_audit_df() -> pd.DataFrame:
    """Fixture providing clean audit DataFrame for 375 continuous execution intervals."""
    times = pd.date_range("2024-01-01 09:15:00", periods=375, freq="1min", tz="Asia/Kolkata")
    n = len(times)
    df = pd.DataFrame({
        "timestamp": times,
        "open": [2500.0] * n,
        "high": [2505.0] * n,
        "low": [2495.0] * n,
        "close": [2501.0] * n,
        "volume": [1000] * n,
    })
    return df


def test_check_missing_columns(clean_audit_df):
    """Test detection of missing OHLCV columns."""
    res_ok = check_missing_columns(clean_audit_df)
    assert res_ok.passed is True

    bad = clean_audit_df.drop(columns=["volume"])
    res_bad = check_missing_columns(bad)
    assert res_bad.passed is False
    assert "volume" in res_bad.details["missing_columns"]


def test_check_duplicate_timestamps(clean_audit_df):
    """Test duplicate timestamp detection."""
    res_ok = check_duplicate_timestamps(clean_audit_df)
    assert res_ok.passed is True

    # Duplicate first row
    dup_df = pd.concat([clean_audit_df.iloc[[0]], clean_audit_df], ignore_index=True)
    res_bad = check_duplicate_timestamps(dup_df)
    assert res_bad.passed is False
    assert res_bad.issue_count == 1


def test_check_non_monotonic_timestamps(clean_audit_df):
    """Test detection of non-monotonic timestamps."""
    res_ok = check_monotonic_timestamps(clean_audit_df)
    assert res_ok.passed is True

    # Swap first two rows
    scrambled = clean_audit_df.copy()
    scrambled.iloc[0], scrambled.iloc[1] = scrambled.iloc[1].copy(), scrambled.iloc[0].copy()
    res_bad = check_monotonic_timestamps(scrambled)
    assert res_bad.passed is False
    assert res_bad.issue_count >= 1


def test_check_zero_or_negative_prices(clean_audit_df):
    """Test detection of zero or negative prices."""
    res_ok = check_zero_or_negative_prices(clean_audit_df)
    assert res_ok.passed is True

    corrupt = clean_audit_df.copy()
    corrupt.loc[10, "close"] = -5.0
    corrupt.loc[20, "low"] = 0.0
    res_bad = check_zero_or_negative_prices(corrupt)
    assert res_bad.passed is False
    assert res_bad.issue_count == 2


def test_check_negative_volume(clean_audit_df):
    """Test detection of negative volume."""
    res_ok = check_zero_or_negative_volume(clean_audit_df)
    assert res_ok.passed is True

    corrupt = clean_audit_df.copy()
    corrupt.loc[5, "volume"] = -100
    res_bad = check_zero_or_negative_volume(corrupt)
    assert res_bad.passed is False
    assert res_bad.issue_count == 1


def test_check_high_low_violation(clean_audit_df):
    """Test detection of High < Low violations."""
    res_ok = check_high_low_violation(clean_audit_df)
    assert res_ok.passed is True

    corrupt = clean_audit_df.copy()
    corrupt.loc[3, "high"] = 2400.0  # low is 2495.0
    res_bad = check_high_low_violation(corrupt)
    assert res_bad.passed is False
    assert res_bad.issue_count == 1


def test_check_open_close_outside_high_low(clean_audit_df):
    """Test Open/Close outside [Low, High] bounds."""
    res_ok = check_open_close_within_high_low(clean_audit_df)
    assert res_ok.passed is True

    corrupt = clean_audit_df.copy()
    corrupt.loc[7, "close"] = 2510.0  # high is 2505.0
    res_bad = check_open_close_within_high_low(corrupt)
    assert res_bad.passed is False
    assert res_bad.issue_count == 1


def test_check_extreme_returns(clean_audit_df):
    """Test detection of extreme 1-minute price jumps (>10%)."""
    res_ok = check_extreme_returns(clean_audit_df)
    assert res_ok.passed is True

    jump_df = clean_audit_df.copy()
    jump_df.loc[15, "close"] = 3500.0  # ~40% jump from 2500
    res_bad = check_extreme_returns(jump_df, extreme_threshold=0.10)
    assert res_bad.passed is False
    assert res_bad.issue_count >= 1


def test_run_comprehensive_audit_structure(clean_audit_df):
    """Test that comprehensive audit returns a complete structured report."""
    report = run_comprehensive_audit(clean_audit_df, file_path="test_synthetic")
    assert report.total_records == len(clean_audit_df)
    assert len(report.checks) == 14
    report_dict = report.to_dict()
    assert "summary" in report_dict
    assert "checks" in report_dict
    assert report_dict["summary"]["total_checks"] == 14
