"""Evaluation, Transaction Cost Analysis (TCA), and statistical metrics module.

Computes 20 execution evaluation metrics: Implementation Shortfall, VWAP slippage,
temporary/permanent market impact, passive fill ratio, inventory variance,
and regime-stratified statistical significance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    """Consolidated execution performance results for a parent order trajectory."""
    implementation_shortfall_bps: float
    slippage_vs_arrival_bps: float
    slippage_vs_vwap_bps: float
    fill_rate_pct: float
    passive_fill_rate_pct: float
    average_spread_paid_bps: float
    temporary_impact_bps: float
    permanent_impact_bps: float
    inventory_variance: float
    turnover_inr: float
    total_transaction_cost_bps: float


def compute_implementation_shortfall(
    executed_shares: np.ndarray,
    execution_prices: np.ndarray,
    arrival_price: float,
    parent_order_size: float,
) -> float:
    """Calculate Implementation Shortfall in basis points.

    IS_bps = ((Sum(q_t * P_exec) - Q_0 * P_0) / (Q_0 * P_0)) * 10,000
    """
    total_cost = np.sum(executed_shares * execution_prices)
    benchmark_cost = parent_order_size * arrival_price
    shortfall_bps = ((total_cost - benchmark_cost) / benchmark_cost) * 10000.0
    return float(shortfall_bps)


def compute_interval_vwap_slippage(
    executed_shares: np.ndarray,
    execution_prices: np.ndarray,
    interval_vwap: float,
) -> float:
    """Calculate execution slippage relative to market interval VWAP in basis points."""
    total_shares = np.sum(executed_shares)
    if total_shares <= 0 or interval_vwap <= 0:
        return 0.0
    avg_price = np.sum(executed_shares * execution_prices) / total_shares
    slippage_bps = ((avg_price - interval_vwap) / interval_vwap) * 10000.0
    return float(slippage_bps)
