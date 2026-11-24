"""Evaluation, Transaction Cost Analysis (TCA), and statistical metrics module.

Calculates all 18 execution performance and microstructure metrics:
1. Arrival price
2. Interval VWAP
3. Implementation shortfall (currency & bps)
4. Slippage versus arrival price (bps)
5. Slippage versus interval VWAP (bps)
6. Temporary market impact
7. Permanent market impact
8. Average spread paid
9. Fill rate
10. Turnover
11. Inventory metrics
12. Inventory variance
13. Maximum inventory
14. Execution completion rate
15. Participation rate
16. Transaction-cost-adjusted execution cost
17. Performance by volatility regime
18. Performance by liquidity regime
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.backtester import ExecutionTrajectory

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Consolidated 18 execution performance metrics for a parent order trajectory."""
    policy_name: str
    ticker: str
    parent_order_size: float
    arrival_price: float
    interval_vwap: float
    average_execution_price: float
    implementation_shortfall_inr: float
    implementation_shortfall_bps: float
    slippage_vs_arrival_bps: float
    slippage_vs_vwap_bps: float
    temporary_impact_inr: float
    temporary_impact_bps: float
    permanent_impact_bps: float
    average_spread_paid_bps: float
    fill_rate_pct: float
    turnover_inr: float
    mean_inventory: float
    inventory_variance: float
    max_inventory: float
    execution_completion_rate: float
    participation_rate_pct: float
    transaction_cost_inr: float
    transaction_cost_bps: float
    net_execution_cost_bps: float
    is_by_volatility_regime: Dict[str, float] = field(default_factory=dict)
    is_by_liquidity_regime: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def evaluate_trajectory(
    trajectory: ExecutionTrajectory,
) -> PerformanceMetrics:
    """Calculate all 18 execution metrics from an ExecutionTrajectory.

    Args:
        trajectory: Completed ExecutionTrajectory.

    Returns:
        PerformanceMetrics dataclass containing all 18 metrics.
    """
    p0 = trajectory.arrival_price
    p_vwap = trajectory.interval_vwap
    q0 = trajectory.parent_order_size
    p_bar = trajectory.average_execution_price
    turnover = trajectory.total_turnover
    benchmark_turnover = q0 * p0

    # 1. Implementation Shortfall (IS): Perold (1988)
    is_inr = turnover - benchmark_turnover
    is_bps = (is_inr / benchmark_turnover) * 10000.0 if benchmark_turnover > 0 else 0.0

    # 2. Slippage vs Arrival Price
    slip_arrival_bps = ((p_bar - p0) / p0) * 10000.0 if p0 > 0 else 0.0

    # 3. Slippage vs Interval VWAP
    slip_vwap_bps = ((p_bar - p_vwap) / p_vwap) * 10000.0 if p_vwap > 0 else 0.0

    # 4. Market Impact
    temp_impact_inr = trajectory.total_temporary_impact
    temp_impact_bps = (temp_impact_inr / benchmark_turnover) * 10000.0 if benchmark_turnover > 0 else 0.0
    perm_impact_bps = (trajectory.terminal_permanent_impact / p0) * 10000.0 if p0 > 0 else 0.0

    # 5. Average Spread Paid
    spread_paid_bps = (trajectory.total_spread_cost / benchmark_turnover) * 10000.0 if benchmark_turnover > 0 else 0.0

    # 6. Fill Rate & Completion
    fill_rate_pct = (trajectory.total_executed_shares / q0) * 100.0 if q0 > 0 else 0.0
    completion_rate = 1.0 if trajectory.terminal_unexecuted_shares <= 0.001 else 0.0

    # 7. Inventory & Trajectory Variance
    df_rec = trajectory.to_dataframe()
    if not df_rec.empty and "remaining_inventory" in df_rec.columns:
        inv_path = df_rec["remaining_inventory"].to_numpy()
        mean_inv = float(np.mean(inv_path))
        t_steps = len(inv_path)
        # Ideal linear liquidation path: Q_t^ideal = Q_0 * (1 - t/T)
        ideal_path = q0 * (1.0 - np.arange(t_steps) / t_steps)
        inv_variance = float(np.mean((inv_path - ideal_path) ** 2))
        max_inv = float(max(q0, np.max(inv_path)))
    else:
        mean_inv = q0 / 2.0
        inv_variance = 0.0
        max_inv = q0

    # 8. Participation Rate
    participation_pct = (
        (trajectory.total_executed_shares / trajectory.total_market_volume) * 100.0
        if trajectory.total_market_volume > 0
        else 0.0
    )

    # 9. Transaction Costs (Statutory Indian Cash Equity Schedule)
    tx_cost_inr = trajectory.total_transaction_costs
    tx_cost_bps = (tx_cost_inr / turnover) * 10000.0 if turnover > 0 else 0.0
    net_cost_bps = is_bps + tx_cost_bps

    # 10. Regime-Stratified Performance
    vol_regimes: Dict[str, float] = {}
    liq_regimes: Dict[str, float] = {}

    if not df_rec.empty:
        # Group child fills by regime
        for v_regime, g in df_rec.groupby("volatility_regime"):
            g_turnover = (g["filled_shares"] * g["fill_price"]).sum()
            g_shares = g["filled_shares"].sum()
            if g_shares > 0:
                g_p_bar = g_turnover / g_shares
                vol_regimes[str(v_regime)] = float(((g_p_bar - p0) / p0) * 10000.0)

        for l_regime, g in df_rec.groupby("liquidity_regime"):
            g_turnover = (g["filled_shares"] * g["fill_price"]).sum()
            g_shares = g["filled_shares"].sum()
            if g_shares > 0:
                g_p_bar = g_turnover / g_shares
                liq_regimes[str(l_regime)] = float(((g_p_bar - p0) / p0) * 10000.0)

    return PerformanceMetrics(
        policy_name=trajectory.policy_name,
        ticker=trajectory.ticker,
        parent_order_size=q0,
        arrival_price=p0,
        interval_vwap=p_vwap,
        average_execution_price=p_bar,
        implementation_shortfall_inr=is_inr,
        implementation_shortfall_bps=is_bps,
        slippage_vs_arrival_bps=slip_arrival_bps,
        slippage_vs_vwap_bps=slip_vwap_bps,
        temporary_impact_inr=temp_impact_inr,
        temporary_impact_bps=temp_impact_bps,
        permanent_impact_bps=perm_impact_bps,
        average_spread_paid_bps=spread_paid_bps,
        fill_rate_pct=fill_rate_pct,
        turnover_inr=turnover,
        mean_inventory=mean_inv,
        inventory_variance=inv_variance,
        max_inventory=max_inv,
        execution_completion_rate=completion_rate,
        participation_rate_pct=participation_pct,
        transaction_cost_inr=tx_cost_inr,
        transaction_cost_bps=tx_cost_bps,
        net_execution_cost_bps=net_cost_bps,
        is_by_volatility_regime=vol_regimes,
        is_by_liquidity_regime=liq_regimes,
    )


def compare_policies(
    trajectories: List[ExecutionTrajectory],
) -> pd.DataFrame:
    """Generate comparative summary DataFrame across all evaluated policies and paths.

    Args:
        trajectories: List of executed trajectories.

    Returns:
        Structured comparative DataFrame.
    """
    rows = []
    for traj in trajectories:
        m = evaluate_trajectory(traj)
        rows.append({
            "Policy": m.policy_name,
            "Ticker": m.ticker,
            "Order Size": m.parent_order_size,
            "Arrival Price": m.arrival_price,
            "Exec Price": m.average_execution_price,
            "IS (bps)": round(m.implementation_shortfall_bps, 2),
            "Slip vs VWAP (bps)": round(m.slippage_vs_vwap_bps, 2),
            "Temp Impact (bps)": round(m.temporary_impact_bps, 2),
            "Perm Impact (bps)": round(m.permanent_impact_bps, 2),
            "Spread Paid (bps)": round(m.average_spread_paid_bps, 2),
            "Fill Rate (%)": round(m.fill_rate_pct, 1),
            "Inv Variance": round(m.inventory_variance, 0),
            "Net Cost (bps)": round(m.net_execution_cost_bps, 2),
            "Tx Cost (bps)": round(m.transaction_cost_bps, 2),
            "Seed": traj.path_seed,
        })
    return pd.DataFrame(rows)
