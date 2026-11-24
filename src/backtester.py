"""Backtesting and simulation orchestration module.

Runs discrete-time execution trajectories over historical market paths,
orchestrating limit order book state, policy decisions, fills, and cost accounting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd

from src.execution_policies import BaseExecutionPolicy
from src.order_book import LimitOrderBookSimulator

logger = logging.getLogger(__name__)


@dataclass
class ExecutionTrajectory:
    """Historical record of an executed parent-order simulation path."""
    policy_name: str
    parent_order_size: float
    arrival_price: float
    timestamps: List[pd.Timestamp]
    inventory_path: List[float]
    executed_slices: List[float]
    execution_prices: List[float]
    spread_costs: List[float]
    impact_costs: List[float]
    passive_flags: List[bool]


class ExecutionBacktester:
    """Simulation engine running an execution policy over an empirical market day."""

    def __init__(self, lob_simulator: LimitOrderBookSimulator):
        self.lob_simulator = lob_simulator

    def run_session(
        self,
        market_data: pd.DataFrame,
        policy: BaseExecutionPolicy,
    ) -> ExecutionTrajectory:
        """Execute a full parent-order simulation across one trading session.

        Day 1 skeleton: defines the operational interface for Day 5/6 simulation runs.
        """
        arrival_price = float(market_data["close"].iloc[0])
        trajectory = ExecutionTrajectory(
            policy_name=type(policy).__name__,
            parent_order_size=policy.parent_order_size,
            arrival_price=arrival_price,
            timestamps=[],
            inventory_path=[],
            executed_slices=[],
            execution_prices=[],
            spread_costs=[],
            impact_costs=[],
            passive_flags=[],
        )
        logger.debug("Initialized backtest session for %s", trajectory.policy_name)
        return trajectory
