"""Data audit, anomaly detection, and validation module.

Executes a 14-point microstructure data verification suite to detect
corrupt prices, invalid intervals, out-of-sequence timestamps, extreme returns,
corporate action splits, and liquidity constraints. Outputs structured JSON/CSV reports.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


@dataclass
class AuditCheckResult:
    check_name: str
    passed: bool
    description: str
    issue_count: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    file_path: str
    total_records: int
    unique_trading_days: int
    all_passed: bool
    checks: List[AuditCheckResult]
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_missing_columns(df: pd.DataFrame, required: List[str] = REQUIRED_COLUMNS) -> AuditCheckResult:
    """1. Check if all required OHLCV columns exist."""
    missing = [c for c in required if c not in df.columns]
    passed = len(missing) == 0
    return AuditCheckResult(
        check_name="missing_required_columns",
        passed=passed,
        description="Verify presence of mandatory OHLCV columns",
        issue_count=len(missing),
        details={"missing_columns": missing},
    )


def check_duplicate_timestamps(df: pd.DataFrame, ts_col: str = "timestamp") -> AuditCheckResult:
    """2. Check for duplicate timestamps."""
    if ts_col not in df.columns:
        return AuditCheckResult("duplicate_timestamps", False, "Timestamp column missing", 1)
    duplicates = df[df.duplicated(subset=[ts_col], keep=False)]
    dup_count = int(df.duplicated(subset=[ts_col]).sum())
    sample_dups = [str(x) for x in duplicates[ts_col].head(5).tolist()]
    return AuditCheckResult(
        check_name="duplicate_timestamps",
        passed=dup_count == 0,
        description="Detect duplicate timestamps",
        issue_count=dup_count,
        details={"duplicate_count": dup_count, "sample_duplicates": sample_dups},
    )


def check_monotonic_timestamps(df: pd.DataFrame, ts_col: str = "timestamp") -> AuditCheckResult:
    """3. Check that timestamps are strictly non-decreasing."""
    if ts_col not in df.columns:
        return AuditCheckResult("monotonic_timestamps", False, "Timestamp column missing", 1)
    ts = pd.to_datetime(df[ts_col])
    diffs = ts.diff().dropna()
    negative_diffs = int((diffs < pd.Timedelta(0)).sum())
    return AuditCheckResult(
        check_name="non_monotonic_timestamps",
        passed=negative_diffs == 0,
        description="Ensure timestamps are strictly ascending",
        issue_count=negative_diffs,
        details={"negative_step_count": negative_diffs},
    )


def check_missing_candles_in_session(
    df: pd.DataFrame,
    ts_col: str = "timestamp",
    start_time: str = "09:15",
    end_time: str = "15:30",
    freq: str = "1min",
    expected_candles_per_day: int = 375,
) -> AuditCheckResult:
    """4. Check for missing 1-minute bars during official NSE continuous trading hours.

    Continuous execution spans exactly 375 minutes: 09:15:00 to 15:29:59 IST (375 candles).
    The 15:30:00 candle represents the post-market closing boundary / auction and is excluded.

    Args:
        df: Input DataFrame.
        ts_col: Name of timestamp column.
        start_time: Session start 'HH:MM'.
        end_time: Session closing boundary 'HH:MM'.
        freq: Bar frequency (default: 1min).
        expected_candles_per_day: Expected continuous trading bars (default: 375).

    Returns:
        AuditCheckResult instance.
    """
    if ts_col not in df.columns:
        return AuditCheckResult("missing_candles", False, "Timestamp column missing", 1)
    ts = pd.to_datetime(df[ts_col])
    days = ts.dt.date.unique()
    missing_by_day = {}
    total_missing = 0

    for day in days:
        day_ts = ts[ts.dt.date == day]
        # Filter to continuous execution horizon: 09:15 to 15:29
        t_start = pd.to_datetime(start_time, format="%H:%M").time()
        t_end = pd.to_datetime(end_time, format="%H:%M").time()
        continuous_bars = day_ts[(day_ts.dt.time >= t_start) & (day_ts.dt.time < t_end)]
        actual_count = len(continuous_bars)
        # Expected count in continuous market hours (375 bars)
        if actual_count < expected_candles_per_day - 5:  # Tolerance for special holiday truncated sessions
            diff = expected_candles_per_day - actual_count
            missing_by_day[str(day)] = diff
            total_missing += diff

    return AuditCheckResult(
        check_name="missing_candles_in_session",
        passed=total_missing == 0,
        description=f"Detect missing continuous 1-minute intervals (expected {expected_candles_per_day} bars/day, 09:15-15:29)",
        issue_count=total_missing,
        details={"total_missing_candles": total_missing, "expected_per_day": expected_candles_per_day, "days_with_gaps": missing_by_day},
    )


def check_zero_or_negative_prices(df: pd.DataFrame) -> AuditCheckResult:
    """5. Check for zero or negative values in open, high, low, close."""
    price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    invalid_mask = pd.Series(False, index=df.index)
    col_counts = {}
    for col in price_cols:
        col_invalid = (df[col] <= 0) | df[col].isna()
        col_counts[col] = int(col_invalid.sum())
        invalid_mask = invalid_mask | col_invalid

    total_invalid = int(invalid_mask.sum())
    return AuditCheckResult(
        check_name="zero_or_negative_prices",
        passed=total_invalid == 0,
        description="Verify all price records are strictly positive (> 0.0)",
        issue_count=total_invalid,
        details=col_counts,
    )


def check_zero_or_negative_volume(df: pd.DataFrame, vol_col: str = "volume") -> AuditCheckResult:
    """6. Check for negative volume."""
    if vol_col not in df.columns:
        return AuditCheckResult("negative_volume", False, "Volume column missing", 1)
    neg_vol = int((df[vol_col] < 0).sum())
    zero_vol = int((df[vol_col] == 0).sum())
    return AuditCheckResult(
        check_name="negative_or_zero_volume",
        passed=neg_vol == 0,
        description="Verify volume is non-negative and track zero-volume bars",
        issue_count=neg_vol,
        details={"negative_volume_count": neg_vol, "zero_volume_bars": zero_vol},
    )


def check_high_low_violation(df: pd.DataFrame) -> AuditCheckResult:
    """7. Check for High < Low structural errors."""
    if "high" not in df.columns or "low" not in df.columns:
        return AuditCheckResult("high_low_violation", False, "High or Low missing", 1)
    invalid = (df["high"] < df["low"]) | (df["high"].isna()) | (df["low"].isna())
    count = int(invalid.sum())
    return AuditCheckResult(
        check_name="high_less_than_low",
        passed=count == 0,
        description="Verify High >= Low for every candle",
        issue_count=count,
        details={"violations_count": count},
    )


def check_open_close_within_high_low(df: pd.DataFrame) -> AuditCheckResult:
    """8. Check that Open and Close fall strictly within [Low, High]."""
    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return AuditCheckResult("open_close_range_violation", False, "OHLC columns missing", 1)
    out_of_range = (
        (df["open"] > df["high"])
        | (df["open"] < df["low"])
        | (df["close"] > df["high"])
        | (df["close"] < df["low"])
    )
    count = int(out_of_range.sum())
    return AuditCheckResult(
        check_name="open_close_outside_high_low",
        passed=count == 0,
        description="Verify Open and Close are bounded within [Low, High]",
        issue_count=count,
        details={"out_of_range_count": count},
    )


def check_extreme_returns(
    df: pd.DataFrame,
    price_col: str = "close",
    extreme_threshold: float = 0.10,  # 10% in 1 minute
) -> AuditCheckResult:
    """9. Check for abnormal 1-minute price jumps (>10%)."""
    if price_col not in df.columns:
        return AuditCheckResult("extreme_returns", False, f"Price column {price_col} missing", 1)
    prices = df[price_col].astype(float)
    ret = np.abs(np.log(prices / prices.shift(1))).fillna(0.0)
    extreme_mask = ret > extreme_threshold
    count = int(extreme_mask.sum())
    max_return = float(ret.max()) if len(ret) > 0 else 0.0
    return AuditCheckResult(
        check_name="extreme_returns",
        passed=count == 0,
        description=f"Flag 1-minute returns exceeding {extreme_threshold*100:.1f}% threshold",
        issue_count=count,
        details={"extreme_count": count, "max_1min_abs_log_return": max_return},
    )


def check_trading_history_length(
    df: pd.DataFrame,
    ts_col: str = "timestamp",
    min_days: int = 120,
) -> AuditCheckResult:
    """10. Check that the dataset satisfies minimum trading days requirement."""
    if ts_col not in df.columns:
        return AuditCheckResult("trading_history_length", False, "Timestamp column missing", 1)
    ts = pd.to_datetime(df[ts_col])
    unique_days = int(ts.dt.date.nunique())
    passed = unique_days >= min_days
    return AuditCheckResult(
        check_name="insufficient_trading_history",
        passed=passed,
        description=f"Verify historical length meets minimum threshold of {min_days} days",
        issue_count=0 if passed else (min_days - unique_days),
        details={"unique_days": unique_days, "required_min_days": min_days},
    )


def check_liquidity_threshold(
    df: pd.DataFrame,
    vol_col: str = "volume",
    min_adv: int = 100000,
    ts_col: str = "timestamp",
) -> AuditCheckResult:
    """11. Check that average daily volume meets minimum liquidity filter."""
    if vol_col not in df.columns or ts_col not in df.columns:
        return AuditCheckResult("low_liquidity", False, "Volume or timestamp missing", 1)
    ts = pd.to_datetime(df[ts_col])
    daily_vol = df.groupby(ts.dt.date)[vol_col].sum()
    adv = float(daily_vol.mean()) if len(daily_vol) > 0 else 0.0
    passed = adv >= min_adv
    return AuditCheckResult(
        check_name="low_liquidity_stock",
        passed=passed,
        description=f"Ensure Average Daily Volume >= {min_adv:,} shares",
        issue_count=0 if passed else 1,
        details={"estimated_adv": adv, "min_adv_threshold": min_adv},
    )


def check_corporate_action_anomalies(
    df: pd.DataFrame,
    price_col: str = "close",
    ts_col: str = "timestamp",
    overnight_jump_threshold: float = 0.15,  # 15% overnight gap
) -> AuditCheckResult:
    """12. Detect potential unadjusted stock splits or dividend anomalies across sessions."""
    if price_col not in df.columns or ts_col not in df.columns:
        return AuditCheckResult("corporate_actions", False, "Required columns missing", 1)
    ts = pd.to_datetime(df[ts_col])
    # Compare first close of today with last close of yesterday
    daily_closes = df.groupby(ts.dt.date)[price_col].agg(["first", "last"])
    overnight_rets = np.abs(np.log(daily_closes["first"] / daily_closes["last"].shift(1))).dropna()
    anomalies = overnight_rets[overnight_rets > overnight_jump_threshold]
    count = int(len(anomalies))
    return AuditCheckResult(
        check_name="corporate_action_anomalies",
        passed=count == 0,
        description="Detect unadjusted overnight price gaps indicating splits or bonus issues",
        issue_count=count,
        details={"anomaly_dates": [str(d) for d in anomalies.index.tolist()]},
    )


def check_timezone_consistency(
    df: pd.DataFrame,
    ts_col: str = "timestamp",
    expected_tz: str = "Asia/Kolkata",
) -> AuditCheckResult:
    """13. Verify timezone consistency and lack of offset drift."""
    if ts_col not in df.columns:
        return AuditCheckResult("timezone_consistency", False, "Timestamp missing", 1)
    ts = pd.to_datetime(df[ts_col])
    has_tz = ts.dt.tz is not None
    tz_str = str(ts.dt.tz) if has_tz else "None"
    passed = has_tz and (expected_tz.lower() in tz_str.lower() or "+05:30" in tz_str)
    return AuditCheckResult(
        check_name="timezone_inconsistency",
        passed=passed,
        description=f"Verify timestamps are localized to {expected_tz}",
        issue_count=0 if passed else 1,
        details={"detected_timezone": tz_str, "expected_timezone": expected_tz},
    )


def check_intraday_data_gaps(
    df: pd.DataFrame,
    ts_col: str = "timestamp",
    max_consecutive_gap_minutes: int = 5,
) -> AuditCheckResult:
    """14. Detect long consecutive intraday data blackouts during trading hours."""
    if ts_col not in df.columns:
        return AuditCheckResult("data_gaps", False, "Timestamp missing", 1)
    ts = pd.to_datetime(df[ts_col])
    # Group by date and check consecutive timestamp intervals
    large_gaps = 0
    gap_samples = []
    for day, day_ts in df.groupby(ts.dt.date)[ts_col]:
        d_ts = pd.to_datetime(day_ts).sort_values()
        step_minutes = (d_ts.diff().dt.total_seconds() / 60.0).dropna()
        exceeds = step_minutes[step_minutes > max_consecutive_gap_minutes]
        if len(exceeds) > 0:
            large_gaps += len(exceeds)
            gap_samples.append(f"{day}: max gap {exceeds.max():.1f}m")

    return AuditCheckResult(
        check_name="data_gaps_during_market_hours",
        passed=large_gaps == 0,
        description=f"Detect consecutive intraday gaps exceeding {max_consecutive_gap_minutes} minutes",
        issue_count=large_gaps,
        details={"gap_instances": large_gaps, "sample_gaps": gap_samples[:5]},
    )


def run_comprehensive_audit(
    df: pd.DataFrame,
    file_path: str = "in_memory",
    config: Optional[AppConfig] = None,
) -> AuditReport:
    """Run all 14 microstructure validation checks against a dataset.

    Args:
        df: Input DataFrame.
        file_path: Origin file identifier.
        config: Optional AppConfig for universe and parameter thresholds.

    Returns:
        Structured AuditReport object.
    """
    cfg = config or get_config()
    min_days = cfg.universe.min_history_days
    min_adv = cfg.universe.min_average_daily_volume
    expected_tz = cfg.data.timezone
    start_time = cfg.data.market_hours.start
    end_time = cfg.data.market_hours.end

    ts_col = "timestamp"
    has_ts = ts_col in df.columns
    total_records = len(df)
    unique_days = int(pd.to_datetime(df[ts_col]).dt.date.nunique()) if has_ts else 0

    checks: List[AuditCheckResult] = [
        check_missing_columns(df),
        check_duplicate_timestamps(df, ts_col),
        check_monotonic_timestamps(df, ts_col),
        check_missing_candles_in_session(df, ts_col, start_time, end_time),
        check_zero_or_negative_prices(df),
        check_zero_or_negative_volume(df),
        check_high_low_violation(df),
        check_open_close_within_high_low(df),
        check_extreme_returns(df),
        check_trading_history_length(df, ts_col, min_days),
        check_liquidity_threshold(df, "volume", min_adv, ts_col),
        check_corporate_action_anomalies(df, "close", ts_col),
        check_timezone_consistency(df, ts_col, expected_tz),
        check_intraday_data_gaps(df, ts_col, max_consecutive_gap_minutes=5),
    ]

    all_passed = all(c.passed for c in checks)
    failed_checks = [c.check_name for c in checks if not c.passed]

    summary = {
        "total_records": total_records,
        "unique_days": unique_days,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.passed),
        "failed_checks_count": len(failed_checks),
        "failed_checks": failed_checks,
        "overall_status": "PASSED" if all_passed else "FLAGGED",
    }

    report = AuditReport(
        file_path=str(file_path),
        total_records=total_records,
        unique_trading_days=unique_days,
        all_passed=all_passed,
        checks=checks,
        summary=summary,
    )

    logger.info(
        "Data audit for '%s': %s (%d/%d checks passed)",
        file_path,
        summary["overall_status"],
        summary["passed_checks"],
        summary["total_checks"],
    )
    return report


def save_audit_report(
    report: AuditReport,
    output_dir: Union[str, Path] = "reports/tables",
    filename_prefix: str = "data_audit_report",
) -> Path:
    """Save the audit report to JSON and CSV summaries.

    Args:
        report: AuditReport instance.
        output_dir: Destination directory.
        filename_prefix: Filename prefix.

    Returns:
        Path to JSON report file.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{filename_prefix}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)

    # Also export tabular check results as CSV
    csv_path = out_dir / f"{filename_prefix}_checks.csv"
    check_rows = []
    for c in report.checks:
        check_rows.append({
            "check_name": c.check_name,
            "passed": c.passed,
            "description": c.description,
            "issue_count": c.issue_count,
            "details": str(c.details),
        })
    pd.DataFrame(check_rows).to_csv(csv_path, index=False)

    logger.info("Saved data audit report to %s and %s", json_path, csv_path)
    return json_path


def run_audit_pipeline(
    file_path: Union[str, Path],
    config: Optional[AppConfig] = None,
    save_reports: bool = True,
) -> AuditReport:
    """Load a raw or processed dataset, execute audit suite, and write reports.

    Args:
        file_path: Path to dataset.
        config: Optional AppConfig.
        save_reports: Whether to serialize report to disk.

    Returns:
        AuditReport instance.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in [".parquet", ".pq"]:
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported extension: {path.suffix}")

    report = run_comprehensive_audit(df, file_path=str(path), config=config)
    if save_reports:
        save_audit_report(report)
    return report
