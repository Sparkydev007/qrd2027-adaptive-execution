"""Visualisation and publication figure generation module.

Generates high-resolution publication-ready figures for A0 portrait academic poster:
- Intraday U-shaped volume profile curves
- Rolling realized volatility regime distribution
- Policy-performance implementation shortfall comparison (06_policy_performance_is.png)
- Market impact & spread breakdown (07_market_impact_breakdown.png)
- Inventory risk & liquidation trajectories (08_inventory_trajectories.png)
- Regime-stratified execution performance (09_regime_performance.png)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.backtester import ExecutionTrajectory
from src.evaluation import PerformanceMetrics

logger = logging.getLogger(__name__)


def set_publication_style():
    """Apply clean, academic styling to Matplotlib figures."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.titlesize": 13,
        "figure.dpi": 300,
    })


def plot_intraday_volume_profile(
    buckets_30m: Dict[int, float],
    ticker: str = "RELIANCE",
    save_path: Optional[Path] = None,
) -> plt.Figure:
    """Plot empirical 30-minute intraday volume smile."""
    set_publication_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    x = list(buckets_30m.keys())
    y = [buckets_30m[k] * 100 for k in x]
    labels = [f"B{k}" for k in x]

    ax.bar(labels, y, color="#1f77b4", alpha=0.8, edgecolor="black")
    ax.set_title(f"Empirical Intraday Volume Profile: {ticker} (NSE)")
    ax.set_xlabel("30-Minute Intraday Session Buckets (09:15 to 15:29 IST)")
    ax.set_ylabel("Volume Percentage of Day (%)")

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig


def plot_policy_performance(
    comparison_df: pd.DataFrame,
    save_path: Optional[Path] = None,
) -> plt.Figure:
    """Plot Implementation Shortfall comparison across policies and order sizes.

    Figure 06 for QRD 2027 poster.
    """
    set_publication_style()
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    # Pivot by Policy and Order Size
    policies = comparison_df["Policy"].unique()
    sizes = sorted(comparison_df["Order Size"].unique())
    x = np.arange(len(sizes))
    width = 0.16

    colors = {
        "TWAPPolicy": "#4c72b0",
        "VWAPPolicy": "#55a868",
        "NaiveAggressivePolicy": "#c44e52",
        "PercentageOfVolumePolicy": "#8172b3",
        "LiquidityAdaptivePolicy": "#ccb974",
    }
    labels_map = {
        "TWAPPolicy": "TWAP",
        "VWAPPolicy": "VWAP",
        "NaiveAggressivePolicy": "Naive Aggressive",
        "PercentageOfVolumePolicy": "POV (10%)",
        "LiquidityAdaptivePolicy": "Adaptive (Proposed)",
    }

    for i, p in enumerate(policies):
        p_df = comparison_df[comparison_df["Policy"] == p].sort_values("Order Size")
        # Average across paths if multiple
        grouped = p_df.groupby("Order Size")["IS (bps)"].mean()
        y_vals = [grouped.get(s, 0.0) for s in sizes]
        offset = (i - len(policies) / 2 + 0.5) * width
        ax.bar(
            x + offset,
            y_vals,
            width=width,
            label=labels_map.get(p, p),
            color=colors.get(p, "#999999"),
            edgecolor="black",
            alpha=0.85,
        )

    ax.set_title("Implementation Shortfall Across Execution Policies (Indian Equities — QRD 2027)", fontweight="bold")
    ax.set_xlabel("Parent Order Size (Fraction of ADV)")
    ax.set_ylabel("Implementation Shortfall (Basis Points)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s*100:.1f}% ADV" for s in sizes])
    ax.legend(loc="upper left", frameon=True)
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig


def plot_market_impact_breakdown(
    metrics_list: List[PerformanceMetrics],
    save_path: Optional[Path] = None,
) -> plt.Figure:
    """Plot breakdown of execution costs: Spread, Temporary Impact, Permanent Impact, and Taxes.

    Figure 07 for QRD 2027 poster.
    """
    set_publication_style()
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    policies = [m.policy_name.replace("Policy", "") for m in metrics_list]
    spreads = [max(0.0, m.average_spread_paid_bps) for m in metrics_list]
    temps = [max(0.0, m.temporary_impact_bps) for m in metrics_list]
    perms = [max(0.0, m.permanent_impact_bps) for m in metrics_list]
    tx_costs = [m.transaction_cost_bps for m in metrics_list]

    x = np.arange(len(policies))
    width = 0.55

    p1 = ax.bar(x, spreads, width, label="Spread Cost", color="#3b528b", edgecolor="black")
    p2 = ax.bar(x, temps, width, bottom=spreads, label="Temporary Impact", color="#440154", edgecolor="black")
    p3 = ax.bar(x, perms, width, bottom=np.array(spreads) + np.array(temps), label="Permanent Impact", color="#21918c", edgecolor="black")
    p4 = ax.bar(x, tx_costs, width, bottom=np.array(spreads) + np.array(temps) + np.array(perms), label="Statutory Taxes (STT/GST)", color="#fde725", edgecolor="black")

    ax.set_title("Execution Cost Decomposition Across Policies (1.0% ADV Order)", fontweight="bold")
    ax.set_xlabel("Execution Policy")
    ax.set_ylabel("Execution Drag (Basis Points)")
    ax.set_xticks(x)
    ax.set_xticklabels(policies)
    ax.legend(loc="upper right", frameon=True)

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig


def plot_inventory_trajectories(
    trajectories: List[ExecutionTrajectory],
    save_path: Optional[Path] = None,
) -> plt.Figure:
    """Plot inventory liquidation paths over the 375-minute execution horizon.

    Figure 08 for QRD 2027 poster.
    """
    set_publication_style()
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    colors = {
        "TWAPPolicy": "#4c72b0",
        "VWAPPolicy": "#55a868",
        "NaiveAggressivePolicy": "#c44e52",
        "PercentageOfVolumePolicy": "#8172b3",
        "LiquidityAdaptivePolicy": "#ccb974",
    }
    labels_map = {
        "TWAPPolicy": "TWAP (Deterministic)",
        "VWAPPolicy": "VWAP (Volume Smile)",
        "NaiveAggressivePolicy": "Naive Aggressive",
        "PercentageOfVolumePolicy": "POV (10%)",
        "LiquidityAdaptivePolicy": "Adaptive Policy",
    }

    for traj in trajectories:
        df = traj.to_dataframe()
        label = labels_map.get(traj.policy_name, traj.policy_name)
        color = colors.get(traj.policy_name, "#999999")
        ax.plot(
            df["step"],
            df["remaining_inventory"] / traj.parent_order_size * 100,
            label=label,
            color=color,
            linewidth=1.8,
        )

    ax.set_title("Parent Order Inventory Liquidation Trajectories (375-Minute Horizon)", fontweight="bold")
    ax.set_xlabel("Session Elapsed Minutes (09:15 to 15:29 IST)")
    ax.set_ylabel("Remaining Inventory (% of Parent Order)")
    ax.set_xlim(0, 375)
    ax.set_ylim(-2, 105)
    ax.legend(loc="upper right", frameon=True)

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig


def plot_regime_performance(
    regime_results: pd.DataFrame,
    save_path: Optional[Path] = None,
) -> plt.Figure:
    """Plot policy performance across volatility regimes (Calm, Normal, Stressed).

    Figure 09 for QRD 2027 poster.
    """
    set_publication_style()
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    regimes = ["calm", "normal", "stressed"]
    policies = regime_results["Policy"].unique()
    x = np.arange(len(regimes))
    width = 0.16

    colors = {
        "TWAPPolicy": "#4c72b0",
        "VWAPPolicy": "#55a868",
        "NaiveAggressivePolicy": "#c44e52",
        "PercentageOfVolumePolicy": "#8172b3",
        "LiquidityAdaptivePolicy": "#ccb974",
    }
    labels_map = {
        "TWAPPolicy": "TWAP",
        "VWAPPolicy": "VWAP",
        "NaiveAggressivePolicy": "Naive Aggressive",
        "PercentageOfVolumePolicy": "POV",
        "LiquidityAdaptivePolicy": "Adaptive",
    }

    for i, p in enumerate(policies):
        p_df = regime_results[regime_results["Policy"] == p]
        y_vals = [p_df[p_df["Regime"] == r]["IS (bps)"].mean() for r in regimes]
        offset = (i - len(policies) / 2 + 0.5) * width
        ax.bar(
            x + offset,
            y_vals,
            width=width,
            label=labels_map.get(p, p),
            color=colors.get(p, "#999999"),
            edgecolor="black",
            alpha=0.85,
        )

    ax.set_title("Execution Performance Stratified by Realized Volatility Regime", fontweight="bold")
    ax.set_xlabel("Market Volatility Regime")
    ax.set_ylabel("Implementation Shortfall (Basis Points)")
    ax.set_xticks(x)
    ax.set_xticklabels(["Calm (≤p40)", "Normal (p40–p80)", "Stressed (>p80)"])
    ax.legend(loc="upper left", frameon=True)
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig
