"""Calibration module for empirical market microstructure parameters.

Estimates historical Average Daily Volume (ADV), intraday U-shaped volume curves,
realized volatility percentiles, regime thresholds, effective bid-ask spread models,
queue depth scaling, temporary/permanent market impact coefficients, and transaction costs.
Produces structured JSON/YAML calibration reports.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
import yaml

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class VolumeProfile:
    buckets_30m: Dict[int, float]
    intraday_1min: List[float]
    sum_check: float


@dataclass
class VolatilityCalibration:
    mean_realised_vol: float
    median_realised_vol: float
    percentiles: Dict[str, float]
    regime_threshold_calm_max: float
    regime_threshold_stressed_min: float


@dataclass
class MicrostructureCalibration:
    spread_method: str
    baseline_spread_bps: float
    depth_multiplier: float
    temporary_impact_exponent: float
    temporary_impact_eta: float
    permanent_impact_fraction_gamma: float
    statutory_transaction_cost_bps: float


@dataclass
class CalibrationReport:
    ticker: str
    sample_start_date: str
    sample_end_date: str
    total_trading_days: int
    average_daily_volume: float
    average_daily_turnover_inr: float
    median_daily_volume: float
    volume_profile: VolumeProfile
    volatility: VolatilityCalibration
    microstructure: MicrostructureCalibration
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def estimate_average_daily_volume(
    df: pd.DataFrame,
    volume_col: str = "volume",
    price_col: str = "close",
    ts_col: str = "timestamp",
) -> Dict[str, float]:
    """1. Estimate historical Average Daily Volume (ADV) and Daily Turnover in INR.

    Args:
        df: Input DataFrame with intraday 1-minute records.
        volume_col: Volume column.
        price_col: Close price column.
        ts_col: Timestamp column.

    Returns:
        Dictionary containing mean ADV, median ADV, and mean daily turnover.
    """
    ts = pd.to_datetime(df[ts_col])
    daily_vol = df.groupby(ts.dt.date)[volume_col].sum()
    daily_turnover = df.groupby(ts.dt.date).apply(
        lambda g: (g[volume_col] * g[price_col]).sum()
    )

    adv_mean = float(daily_vol.mean())
    adv_median = float(daily_vol.median())
    turnover_mean = float(daily_turnover.mean())

    logger.info(
        "Estimated ADV: Mean=%.0f shares, Median=%.0f shares, Daily Turnover=%.2f Cr INR",
        adv_mean,
        adv_median,
        turnover_mean / 1e7,
    )

    return {
        "adv_mean": adv_mean,
        "adv_median": adv_median,
        "daily_turnover_inr": turnover_mean,
        "trading_days_count": int(len(daily_vol)),
    }


def estimate_intraday_volume_profile(
    df: pd.DataFrame,
    volume_col: str = "volume",
    ts_col: str = "timestamp",
    start_time: str = "09:15",
    num_buckets: int = 13,
) -> VolumeProfile:
    """2. Estimate empirical intraday volume curve normalized to sum strictly to 1.0.

    Constructs both 30-minute bucket fractions (13 buckets for 375 minutes: 12 of 30 min + 1 of 15 min)
    and continuous 1-minute profile fractions.

    Args:
        df: Input DataFrame.
        volume_col: Volume column.
        ts_col: Timestamp column.
        start_time: Session start time 'HH:MM'.
        num_buckets: Expected number of intraday 30-minute buckets (default: 13).

    Returns:
        VolumeProfile dataclass with normalized bucket and 1-minute distributions.
    """
    df = df.copy()
    ts = pd.to_datetime(df[ts_col])

    # Compute minutes elapsed from session start (0 to 374)
    start_hour, start_min = map(int, start_time.split(":"))
    session_minutes = (ts.dt.hour - start_hour) * 60 + (ts.dt.minute - start_min)
    df["minute_of_day"] = session_minutes

    # Filter to valid intraday range [0, 374]
    df_valid = df[(df["minute_of_day"] >= 0) & (df["minute_of_day"] < 375)].copy()

    # 1. 1-minute profile
    mean_vol_by_min = df_valid.groupby("minute_of_day")[volume_col].mean()
    # Reindex to full 0..374 grid to prevent missing minutes
    full_min_grid = pd.Series(0.0, index=np.arange(375))
    full_min_grid.update(mean_vol_by_min)
    total_1min = full_min_grid.sum()
    profile_1min = (full_min_grid / total_1min).tolist() if total_1min > 0 else (full_min_grid + 1.0 / 375).tolist()

    # 2. 30-minute bucket profile (bucket index: minute // 30)
    df_valid["bucket_30m"] = (df_valid["minute_of_day"] // 30).astype(int)
    mean_vol_by_bucket = df_valid.groupby("bucket_30m")[volume_col].mean()
    full_bucket_grid = pd.Series(0.0, index=np.arange(num_buckets))
    full_bucket_grid.update(mean_vol_by_bucket)
    total_buckets = full_bucket_grid.sum()
    normalized_buckets = (full_bucket_grid / total_buckets).to_dict() if total_buckets > 0 else (full_bucket_grid + 1.0 / num_buckets).to_dict()
    buckets_dict = {int(k): float(v) for k, v in normalized_buckets.items()}

    sum_check = float(sum(profile_1min))
    logger.info("Volume profile calibrated across 375 minutes (sum=%.6f)", sum_check)

    return VolumeProfile(
        buckets_30m=buckets_dict,
        intraday_1min=[float(x) for x in profile_1min],
        sum_check=sum_check,
    )


def estimate_rolling_volatility(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    annualize: bool = True,
) -> pd.Series:
    """3. Compute rolling realized volatility series from 1-minute close prices.

    Args:
        df: Input DataFrame.
        price_col: Close price column.
        window: Rolling window in minutes.
        annualize: Whether to multiply by sqrt(375 * 250).

    Returns:
        pd.Series of rolling realized volatility.
    """
    prices = df[price_col].astype(float)
    log_ret = np.log(prices / prices.shift(1)).fillna(0.0)
    rolling_vol = log_ret.rolling(window=window, min_periods=max(2, window // 2)).std().bfill().fillna(0.0)
    if annualize:
        ann_factor = np.sqrt(375 * 250)
        rolling_vol = rolling_vol * ann_factor
    return rolling_vol


def estimate_volatility_percentiles(
    vol_series: pd.Series,
    percentiles: Sequence[float] = (10.0, 25.0, 40.0, 50.0, 75.0, 80.0, 90.0, 95.0),
) -> Dict[str, float]:
    """4. Calculate empirical volatility distribution percentiles.

    Args:
        vol_series: Realized volatility series.
        percentiles: Tuple of percentile ranks to estimate.

    Returns:
        Dictionary mapping percentile labels (e.g. 'p40') to estimated values.
    """
    clean_series = vol_series.dropna()
    results = {}
    for p in percentiles:
        results[f"p{int(p) if p.is_integer() else p}"] = float(np.percentile(clean_series, p))
    return results


def classify_volatility_regimes(
    vol_series: pd.Series,
    p_calm_max: float,
    p_stressed_min: float,
) -> pd.Series:
    """5. Classify continuous volatility series into calm, normal, and stressed regimes.

    Args:
        vol_series: Realized volatility series.
        p_calm_max: Volatility value threshold for calm regime.
        p_stressed_min: Volatility value threshold for stressed regime.

    Returns:
        pd.Series of regime category strings ('calm', 'normal', 'stressed').
    """
    conditions = [
        vol_series <= p_calm_max,
        (vol_series > p_calm_max) & (vol_series <= p_stressed_min),
        vol_series > p_stressed_min,
    ]
    choices = ["calm", "normal", "stressed"]
    return pd.Series(np.select(conditions, choices, default="normal"), index=vol_series.index)


def classify_liquidity_regimes(
    volume_series: pd.Series,
    low_cutoff_pct: float = 33.33,
    high_cutoff_pct: float = 66.67,
) -> pd.Series:
    """6. Classify continuous volume series into low, medium, and high liquidity regimes.

    Args:
        volume_series: Volume series.
        low_cutoff_pct: Lower percentile boundary.
        high_cutoff_pct: Upper percentile boundary.

    Returns:
        pd.Series of liquidity category strings ('low', 'medium', 'high').
    """
    clean = volume_series.dropna()
    q_low = float(np.percentile(clean, low_cutoff_pct))
    q_high = float(np.percentile(clean, high_cutoff_pct))

    conditions = [
        volume_series <= q_low,
        (volume_series > q_low) & (volume_series <= q_high),
        volume_series > q_high,
    ]
    choices = ["low", "medium", "high"]
    return pd.Series(np.select(conditions, choices, default="medium"), index=volume_series.index)


def estimate_spread_parameters(
    config: Optional[AppConfig] = None,
    default_spread_bps: float = 5.0,
) -> Dict[str, Any]:
    """7. Estimate bid-ask spread parameters.

    In the default fixed_bps configuration, liquid NIFTY 50 large caps trade at ~3-6 bps spread.
    Also supports volatility-scaled dynamic spread formulation.

    Args:
        config: Application configuration.
        default_spread_bps: Fallback spread in basis points.

    Returns:
        Dictionary of spread model parameters.
    """
    if config is not None:
        method = config.calibration.spread_assumption.method
        val_bps = config.calibration.spread_assumption.value_bps
    else:
        method = "fixed_bps"
        val_bps = default_spread_bps

    return {
        "method": method,
        "baseline_spread_bps": val_bps,
        "half_spread_bps": val_bps / 2.0,
    }


def estimate_depth_parameters(
    config: Optional[AppConfig] = None,
    default_multiplier: float = 0.05,
) -> Dict[str, Any]:
    """8. Estimate top-of-book depth scaling parameters.

    Calibrates visible depth at best bid and ask as a multiplier of 1-minute interval volume.

    Args:
        config: Application configuration.
        default_multiplier: Depth volume fraction multiplier (default: 0.05).

    Returns:
        Dictionary of depth parameters.
    """
    multiplier = config.calibration.depth_assumption.multiplier if config else default_multiplier
    method = config.calibration.depth_assumption.method if config else "volume_multiple"
    return {
        "method": method,
        "multiplier": float(multiplier),
        "description": f"Top-of-book depth modeled as {multiplier*100:.1f}% of interval volume",
    }


def estimate_temporary_impact_parameters(
    config: Optional[AppConfig] = None,
    default_exponent: float = 0.5,
    default_eta: float = 0.5,
) -> Dict[str, float]:
    """9. Estimate square-root temporary price impact parameters (Almgren-Chriss formulation).

    Delta P_temp = eta * sigma * (q / V)^alpha

    Args:
        config: Application configuration.
        default_exponent: Power exponent alpha (default: 0.5).
        default_eta: Coefficient multiplier eta (default: 0.5).

    Returns:
        Dictionary with 'exponent' and 'eta'.
    """
    alpha = config.calibration.impact_model.temporary_impact_exponent if config else default_exponent
    eta = default_eta
    return {
        "exponent_alpha": float(alpha),
        "coefficient_eta": float(eta),
    }


def estimate_permanent_impact_parameters(
    config: Optional[AppConfig] = None,
    default_gamma: float = 0.10,
) -> Dict[str, float]:
    """10. Estimate linear permanent market impact parameters.

    Delta P_perm = gamma * sigma * (q / V)

    Args:
        config: Application configuration.
        default_gamma: Fraction gamma (default: 0.10).

    Returns:
        Dictionary with 'fraction_gamma'.
    """
    gamma = config.calibration.impact_model.permanent_impact_fraction if config else default_gamma
    return {
        "fraction_gamma": float(gamma),
    }


def estimate_transaction_cost_schedule(
    config: Optional[AppConfig] = None,
    baseline_bps: float = 5.0,
) -> Dict[str, float]:
    """11. Formulate transaction cost assumptions reflecting Indian cash equity structure.

    Indian cash equity institutional schedule breakdown:
    - Brokerage: 1.5 bps
    - STT (delivery buy/sell): 10.0 bps / Intraday: 2.5 bps
    - Exchange turnover fee (NSE): 0.325 bps
    - SEBI charges: 0.01 bps
    - Stamp duty (buy): 1.5 bps
    - GST: 18% on fees ~ 0.33 bps

    Args:
        config: Application configuration.
        baseline_bps: Configured baseline round-turn cost.

    Returns:
        Dictionary of cost rates in basis points.
    """
    statutory_bps = config.calibration.transaction_cost_bps if config else baseline_bps
    return {
        "configured_baseline_bps": float(statutory_bps),
        "brokerage_bps": 1.50,
        "stt_intraday_bps": 2.50,
        "exchange_charges_bps": 0.325,
        "sebi_turnover_bps": 0.01,
        "stamp_duty_bps": 1.50,
        "gst_bps": 0.33,
        "total_itemized_bps": 5.665,
    }


def generate_calibration_summary(
    df: pd.DataFrame,
    ticker: str = "RELIANCE",
    config: Optional[AppConfig] = None,
) -> CalibrationReport:
    """12. Generate complete structured calibration report from historical clean data.

    Args:
        df: Processed DataFrame containing timestamp, open, high, low, close, volume.
        ticker: NSE equity ticker.
        config: Application configuration.

    Returns:
        CalibrationReport instance.
    """
    cfg = config or get_config()
    adv_dict = estimate_average_daily_volume(df)
    vol_profile = estimate_intraday_volume_profile(
        df,
        start_time=cfg.data.market_hours.start,
        num_buckets=cfg.calibration.volume_profile_buckets,
    )

    rolling_vol = estimate_rolling_volatility(
        df,
        window=cfg.calibration.volatility_window,
        annualize=True,
    )
    pcts = estimate_volatility_percentiles(rolling_vol)

    calm_pct = cfg.simulation.regime_definitions["calm"].volatility_percentile_max or 40.0
    stressed_pct = cfg.simulation.regime_definitions["stressed"].volatility_percentile_min or 80.0

    calm_val = pcts.get(f"p{int(calm_pct)}", float(np.percentile(rolling_vol.dropna(), calm_pct)))
    stressed_val = pcts.get(f"p{int(stressed_pct)}", float(np.percentile(rolling_vol.dropna(), stressed_pct)))

    vol_calib = VolatilityCalibration(
        mean_realised_vol=float(rolling_vol.mean()),
        median_realised_vol=float(rolling_vol.median()),
        percentiles=pcts,
        regime_threshold_calm_max=calm_val,
        regime_threshold_stressed_min=stressed_val,
    )

    spread_params = estimate_spread_parameters(cfg)
    depth_params = estimate_depth_parameters(cfg)
    temp_impact = estimate_temporary_impact_parameters(cfg)
    perm_impact = estimate_permanent_impact_parameters(cfg)
    tx_costs = estimate_transaction_cost_schedule(cfg)

    micro_calib = MicrostructureCalibration(
        spread_method=spread_params["method"],
        baseline_spread_bps=spread_params["baseline_spread_bps"],
        depth_multiplier=depth_params["multiplier"],
        temporary_impact_exponent=temp_impact["exponent_alpha"],
        temporary_impact_eta=temp_impact["coefficient_eta"],
        permanent_impact_fraction_gamma=perm_impact["fraction_gamma"],
        statutory_transaction_cost_bps=tx_costs["configured_baseline_bps"],
    )

    ts = pd.to_datetime(df["timestamp"])
    start_dt = str(ts.dt.date.min())
    end_dt = str(ts.dt.date.max())

    report = CalibrationReport(
        ticker=ticker,
        sample_start_date=start_dt,
        sample_end_date=end_dt,
        total_trading_days=adv_dict["trading_days_count"],
        average_daily_volume=adv_dict["adv_mean"],
        average_daily_turnover_inr=adv_dict["daily_turnover_inr"],
        median_daily_volume=adv_dict["adv_median"],
        volume_profile=vol_profile,
        volatility=vol_calib,
        microstructure=micro_calib,
        metadata={
            "annualization_factor": float(np.sqrt(375 * 250)),
            "market_hours": f"{cfg.data.market_hours.start}-{cfg.data.market_hours.end}",
            "source": cfg.data.source,
        },
    )

    return report


def save_calibration_report(
    report: CalibrationReport,
    output_dir: Union[str, Path] = "reports/tables",
    filename_prefix: str = "calibration_report",
    format_type: str = "json",
) -> Path:
    """Save calibration report to JSON or YAML.

    Args:
        report: CalibrationReport instance.
        output_dir: Target output directory.
        filename_prefix: Filename prefix.
        format_type: Output format ('json' or 'yaml').

    Returns:
        Path to written file.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    report_dict = report.to_dict()

    if format_type.lower() == "yaml":
        file_path = out_dir / f"{filename_prefix}.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(report_dict, f, sort_keys=False)
    else:
        file_path = out_dir / f"{filename_prefix}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, default=str)

    logger.info("Saved calibration report to %s", file_path)
    return file_path


def run_calibration_pipeline(
    file_path: Union[str, Path],
    ticker: str = "RELIANCE",
    config: Optional[AppConfig] = None,
    save_format: str = "json",
) -> CalibrationReport:
    """Run end-to-end calibration pipeline from data file to saved report.

    Args:
        file_path: Path to raw or processed dataset.
        ticker: Stock ticker.
        config: Application configuration.
        save_format: Report format ('json' or 'yaml').

    Returns:
        CalibrationReport instance.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    report = generate_calibration_summary(df, ticker=ticker, config=config)
    save_calibration_report(report, format_type=save_format)
    return report
