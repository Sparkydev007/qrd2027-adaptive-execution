"""Day 2 simulation runner script: multi-stock execution study across 5 policies.

Calibrates RELIANCE, HDFCBANK, and TCS, runs simulation across 3 parent order sizes,
evaluates all 18 metrics, exports results, and generates 300 DPI publication charts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from src.config import get_config
from src.data_loader import process_ohlcv_pipeline
from src.calibration import run_calibration_pipeline
from src.order_book import LimitOrderBookSimulator
from src.execution_policies import (
    TWAPPolicy,
    VWAPPolicy,
    NaiveAggressivePolicy,
    PercentageOfVolumePolicy,
    LiquidityAdaptivePolicy,
)
from src.backtester import ExecutionBacktester
from src.evaluation import compare_policies, evaluate_trajectory
from src.visualisation import (
    plot_policy_performance,
    plot_market_impact_breakdown,
    plot_inventory_trajectories,
    plot_regime_performance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    config = get_config(reload=True)
    stocks = ["RELIANCE", "HDFCBANK", "TCS"]
    processed_dfs = {}
    calibration_reports = {}

    tables_dir = Path("reports/tables")
    figures_dir = Path("reports/figures")
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Process and Calibrate each stock
    for ticker in stocks:
        raw_path = f"data/raw/sample_{ticker}_1min.csv"
        proc_path = f"data/processed/{ticker}_1min.parquet"
        df_p = process_ohlcv_pipeline(raw_path, config=config, output_path=proc_path)
        processed_dfs[ticker] = df_p
        calib = run_calibration_pipeline(proc_path, ticker=ticker, config=config, save_format="json")
        calibration_reports[ticker] = calib
        logger.info(f"Calibrated {ticker}: ADV={calib.average_daily_volume:,.0f} shares")

    # 2. Simulation Setup
    order_fractions = config.execution.parent_order_sizes_adv  # [0.005, 0.01, 0.02]
    all_trajectories = []
    representative_1pct_trajectories = []
    all_metrics = []

    simulator = LimitOrderBookSimulator(
        baseline_spread_bps=config.calibration.spread_assumption.value_bps,
        depth_multiplier=config.calibration.depth_assumption.multiplier,
        temp_impact_alpha=config.calibration.impact_model.temporary_impact_exponent,
        temp_impact_eta=0.50,
        perm_impact_gamma=config.calibration.impact_model.permanent_impact_fraction,
        transaction_cost_bps=config.calibration.transaction_costs.buy_side_intraday_bps,
        random_seed=config.simulation.random_seed,
    )

    backtester = ExecutionBacktester(simulator, max_participation=config.execution.max_participation_rate)

    # Run simulation on representative sessions
    for ticker in stocks:
        df_stock = processed_dfs[ticker]
        first_date = df_stock["timestamp"].dt.date.iloc[0]
        session_df = df_stock[df_stock["timestamp"].dt.date == first_date].reset_index(drop=True)
        assert len(session_df) == 375, f"Session length is {len(session_df)} != 375"

        calib = calibration_reports[ticker]
        adv = calib.average_daily_volume
        vol_profile = calib.volume_profile.intraday_1min

        for frac in order_fractions:
            order_size = adv * frac

            policies = [
                TWAPPolicy(parent_order_size=order_size, horizon_steps=375),
                VWAPPolicy(parent_order_size=order_size, horizon_steps=375, volume_profile=vol_profile),
                NaiveAggressivePolicy(parent_order_size=order_size, horizon_steps=375),
                PercentageOfVolumePolicy(parent_order_size=order_size, horizon_steps=375, target_participation_rate=0.10),
                LiquidityAdaptivePolicy(parent_order_size=order_size, horizon_steps=375, volume_profile=vol_profile),
            ]

            for pol in policies:
                traj = backtester.run_session(session_df, pol, ticker=ticker, seed=config.simulation.random_seed)
                all_trajectories.append(traj)
                met = evaluate_trajectory(traj)
                all_metrics.append(met)

                if ticker == "RELIANCE" and abs(frac - 0.01) < 1e-4:
                    representative_1pct_trajectories.append(traj)

    # 3. Export Simulation Results & Summary Tables
    comp_df = compare_policies(all_trajectories)

    sim_results_path = tables_dir / "simulation_results.csv"
    comp_df.to_csv(sim_results_path, index=False)
    comp_df.to_parquet(tables_dir / "simulation_results.parquet", index=False)

    summary_agg = (
        comp_df.groupby(["Policy", "Order Size"])[
            ["IS (bps)", "Slip vs VWAP (bps)", "Temp Impact (bps)", "Perm Impact (bps)", "Spread Paid (bps)", "Inv Variance", "Net Cost (bps)"]
        ]
        .mean()
        .reset_index()
    )
    summary_agg.to_csv(tables_dir / "policy_comparison_summary.csv", index=False)
    with open(tables_dir / "policy_comparison_summary.json", "w") as f:
        json.dump(summary_agg.to_dict(orient="records"), f, indent=2)

    logger.info("Saved simulation_results.csv and policy_comparison_summary.csv")

    # 4. Generate Simulation Configuration Report
    sim_config_report = {
        "project": config.project.name,
        "execution_horizon_minutes": config.execution.execution_horizon_minutes,
        "continuous_hours": f"{config.data.market_hours.start} to 15:29 IST",
        "parent_order_sizes_adv": config.execution.parent_order_sizes_adv,
        "max_participation_rate": config.execution.max_participation_rate,
        "universe_calibrated": stocks,
        "simulation_assumptions": {
            "spread_method": config.calibration.spread_assumption.method,
            "baseline_spread_bps": config.calibration.spread_assumption.value_bps,
            "depth_multiplier": config.calibration.depth_assumption.multiplier,
            "temporary_impact_exponent": config.calibration.impact_model.temporary_impact_exponent,
            "temporary_impact_eta": 0.50,
            "permanent_impact_fraction": config.calibration.impact_model.permanent_impact_fraction,
            "buy_side_intraday_transaction_cost_bps": config.calibration.transaction_costs.buy_side_intraday_bps,
            "itemized_transaction_costs": {
                "brokerage_bps": config.calibration.transaction_costs.brokerage_bps,
                "exchange_charges_bps": config.calibration.transaction_costs.exchange_charges_bps,
                "sebi_charges_bps": config.calibration.transaction_costs.sebi_charges_bps,
                "gst_bps": config.calibration.transaction_costs.gst_bps,
                "stamp_duty_bps": config.calibration.transaction_costs.intraday_stamp_duty_bps,
                "stt_buy_bps": 0.0,
            },
        },
        "total_simulations_executed": len(all_trajectories),
        "random_seed": config.simulation.random_seed,
    }
    with open(tables_dir / "simulation_configuration_report.json", "w") as f:
        json.dump(sim_config_report, f, indent=2)

    # 5. Generate Publication Figures at 300 DPI
    fig06_path = figures_dir / "06_policy_performance_is.png"
    plot_policy_performance(comp_df[comp_df["Ticker"] == "RELIANCE"], save_path=fig06_path)

    fig07_path = figures_dir / "07_market_impact_breakdown.png"
    rel_1pct_metrics = [evaluate_trajectory(t) for t in representative_1pct_trajectories]
    plot_market_impact_breakdown(rel_1pct_metrics, save_path=fig07_path)

    fig08_path = figures_dir / "08_inventory_trajectories.png"
    plot_inventory_trajectories(representative_1pct_trajectories, save_path=fig08_path)

    fig09_path = figures_dir / "09_regime_performance.png"
    regime_rows = []
    rel_adv = calibration_reports["RELIANCE"].average_daily_volume
    for met in all_metrics:
        if met.ticker == "RELIANCE" and abs(met.parent_order_size - rel_adv * 0.01) < 1.0:
            for reg, val in met.is_by_volatility_regime.items():
                regime_rows.append({"Policy": met.policy_name, "Regime": reg, "IS (bps)": val})
    regime_df = pd.DataFrame(regime_rows)
    if not regime_df.empty:
        plot_regime_performance(regime_df, save_path=fig09_path)

    logger.info("Generated all 4 publication figures at 300 DPI in reports/figures/")


if __name__ == "__main__":
    main()
