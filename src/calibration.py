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
class MicrostructureSimulationAssumptions:
    """Simulation assumptions for market microstructure parameters.

    NOTE: Spread, depth, and impact parameters are simulation assumptions based on theoretical
    models (e.g. Almgren-Chriss square-root impact law) and market conventions, NOT directly
    fitted from proprietary Level-2/Level-3 order book tick feeds.
    """
    assumed_spread_method: str
    assumed_baseline_spread_bps: float
    assumed_depth_multiplier: float
    assumed_temporary_impact_exponent: float
    assumed_temporary_impact_eta: float
    assumed_permanent_impact_fraction_gamma: float
    statutory_transaction_cost_bps: float
    transaction_cost_schedule: Dict[str, float] = field(default_factory=dict)
    assumption_note: str = (
        "Microstructure parameters are calibrated simulation assumptions based on theoretical "
        "formulations (Almgren-Chriss) and empirical baseline values, not fitted Level-2 tick logs."
    )


# Alias for backwards compatibility
MicrostructureCalibration = MicrostructureSimulationAssumptions


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
    simulation_assumptions: MicrostructureSimulationAssumptions
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def microstructure(self) -> MicrostructureSimulationAssumptions:
        """Convenience alias for simulation assumptions."""
        return self.simulation_assumptions

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["microstructure"] = asdict(self.simulation_assumptions)
        return d


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
    baseline_bps: float = 2.4653,
    brokerage_bps: Optional[float] = None,
    exchange_charges_bps: Optional[float] = None,
    sebi_turnover_bps: Optional[float] = None,
    stamp_duty_bps: Optional[float] = None,
    stt_sell_bps: Optional[float] = None,
    gst_rate: float = 0.18,
) -> Dict[str, float]:
    """11. Formulate transaction cost assumptions reflecting Indian cash equity structure.

    Separates buy-side and sell-side intraday statutory costs and calculates all totals programmatically:
    - Brokerage: 1.50 bps
    - Exchange turnover fee (NSE Cash): 0.325 bps
    - SEBI turnover charges: 0.01 bps
    - GST (18% applied strictly to taxable services: brokerage + exchange + SEBI charges):
        gst_bps = round(gst_rate * (brokerage + exchange + sebi), 4) = 0.3303 bps
    - Stamp duty (buy-side intraday statutory assumption): 0.30 bps (0.003%)
    - Securities Transaction Tax (STT, sell-side intraday statutory): 2.50 bps (0.025%)

    Programmatic buy-side total (applicable to parent buy orders):
        buy_side_total_bps = brokerage + exchange + sebi + gst + stamp_duty = 2.4653 bps

    Programmatic sell-side total:
        sell_side_total_bps = brokerage + exchange + sebi + gst + stt = 4.6653 bps

    Programmatic round-turn total:
        round_turn_total_bps = buy_side_total_bps + sell_side_total_bps = 7.1306 bps

    Args:
        config: Application configuration.
        baseline_bps: Configured baseline round-turn cost.
        brokerage_bps: Brokerage execution fee in bps.
        exchange_charges_bps: NSE exchange turnover charge in bps.
        sebi_turnover_bps: SEBI turnover charge in bps.
        stamp_duty_bps: Statutory buy-side intraday stamp duty in bps (default: 0.30).
        stt_sell_bps: Statutory sell-side intraday STT in bps (default: 2.50).
        gst_rate: Goods and Services Tax rate (default: 0.18).

    Returns:
        Dictionary of cost rates in basis points with programmatically calculated buy, sell, and round-turn totals.
    """
    if config is not None:
        tc = config.calibration.transaction_costs
        brok = brokerage_bps if brokerage_bps is not None else tc.brokerage_bps
        exch = exchange_charges_bps if exchange_charges_bps is not None else tc.exchange_charges_bps
        sebi = sebi_turnover_bps if sebi_turnover_bps is not None else tc.sebi_charges_bps
        stamp = stamp_duty_bps if stamp_duty_bps is not None else tc.intraday_stamp_duty_bps
        stt = stt_sell_bps if stt_sell_bps is not None else tc.intraday_stt_sell_bps
        gst_r = gst_rate if gst_rate is not None else tc.gst_rate
        statutory_bps = config.calibration.transaction_cost_bps
    else:
        brok = brokerage_bps if brokerage_bps is not None else 1.50
        exch = exchange_charges_bps if exchange_charges_bps is not None else 0.325
        sebi = sebi_turnover_bps if sebi_turnover_bps is not None else 0.01
        stamp = stamp_duty_bps if stamp_duty_bps is not None else 0.30
        stt = stt_sell_bps if stt_sell_bps is not None else 2.50
        gst_r = gst_rate
        statutory_bps = baseline_bps

    # Programmatic GST calculation (18% on taxable services only, exempting STT and Stamp Duty)
    taxable_services_bps = brok + exch + sebi
    gst_bps = round(gst_r * taxable_services_bps, 4)

    # Buy-side intraday components (STT is 0 on intraday buy)
    buy_components = [brok, exch, sebi, gst_bps, stamp]
    buy_side_total_bps = round(float(sum(buy_components)), 4)

    # Sell-side intraday components (Stamp duty is 0 on sell side)
    sell_components = [brok, exch, sebi, gst_bps, stt]
    sell_side_total_bps = round(float(sum(sell_components)), 4)

    # Round-turn total
    round_turn_total_bps = round(buy_side_total_bps + sell_side_total_bps, 4)

    return {
        "configured_baseline_bps": float(statutory_bps),
        "brokerage_bps": float(brok),
        "exchange_charges_bps": float(exch),
        "sebi_turnover_bps": float(sebi),
        "taxable_services_bps": float(round(taxable_services_bps, 4)),
        "gst_bps": float(gst_bps),
        "stamp_duty_bps": float(stamp),
        "stt_bps": float(stt),
        "buy_side_stamp_duty_bps": float(stamp),
        "sell_side_stt_bps": float(stt),
        "buy_side_total_bps": float(buy_side_total_bps),
        "sell_side_total_bps": float(sell_side_total_bps),
        "round_turn_total_bps": float(round_turn_total_bps),
        # Default applicable for parent buy order execution
        "total_itemized_bps": float(buy_side_total_bps),
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

    micro_assumptions = MicrostructureSimulationAssumptions(
        assumed_spread_method=spread_params["method"],
        assumed_baseline_spread_bps=spread_params["baseline_spread_bps"],
        assumed_depth_multiplier=depth_params["multiplier"],
        assumed_temporary_impact_exponent=temp_impact["exponent_alpha"],
        assumed_temporary_impact_eta=temp_impact["coefficient_eta"],
        assumed_permanent_impact_fraction_gamma=perm_impact["fraction_gamma"],
        statutory_transaction_cost_bps=tx_costs["configured_baseline_bps"],
        transaction_cost_schedule=tx_costs,
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
        simulation_assumptions=micro_assumptions,
        metadata={
            "annualization_factor": float(np.sqrt(375 * 250)),
            "market_hours": f"{cfg.data.market_hours.start}-{cfg.data.market_hours.end}",
            "execution_horizon_minutes": 375,
            "continuous_interval": "09:15-15:29",
            "source": cfg.data.source,
            "simulation_assumptions_relabeled": True,
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
