"""Backtesting and Monte Carlo simulation orchestration module.

Runs discrete-time execution trajectories over empirical market sessions,
orchestrating limit order book state, policy decisions, fills, persistent impact,
and transaction cost accounting across multiple stochastic paths.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.execution_policies import BaseExecutionPolicy
from src.order_book import ChildOrderFill, LimitOrderBookSimulator, OrderBookState

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryRecord:
    """Historical point-in-time record for a single execution step."""
    step: int
    timestamp: Optional[pd.Timestamp]
    mid_price: float
    market_volume: float
    volatility: float
    spread: float
    target_shares: float
    filled_shares: float
    fill_price: float
    remaining_inventory: float
    is_passive: bool
    spread_cost_paid: float
    temporary_impact_paid: float
    permanent_impact_generated: float
    transaction_cost_paid: float
    volatility_regime: str
    liquidity_regime: str


@dataclass
class ExecutionTrajectory:
    """Consolidated record of a completed parent order simulation path."""
    policy_name: str
    ticker: str
    date: str
    parent_order_size: float
    arrival_price: float
    interval_vwap: float
    total_market_volume: float
    records: List[TrajectoryRecord]
    total_executed_shares: float
    average_execution_price: float
    terminal_unexecuted_shares: float
    total_turnover: float
    total_transaction_costs: float
    total_spread_cost: float
    total_temporary_impact: float
    terminal_permanent_impact: float
    path_seed: int

    def to_dataframe(self) -> pd.DataFrame:
        """Export step records as a pandas DataFrame."""
        return pd.DataFrame([r.__dict__ for r in self.records])


class ExecutionBacktester:
    """Event-driven discrete-time execution simulation orchestrator."""

    def __init__(
        self,
        lob_simulator: LimitOrderBookSimulator,
        max_participation: float = 0.20,
    ):
        self.lob = lob_simulator
        self.max_participation = max_participation

    def run_session(
        self,
        session_df: pd.DataFrame,
        policy: BaseExecutionPolicy,
        ticker: str = "RELIANCE",
        seed: Optional[int] = None,
    ) -> ExecutionTrajectory:
        """Execute a full parent-order simulation across one trading session (375 minutes).

        Args:
            session_df: 1-minute OHLCV data for one session (375 bars: 09:15 to 15:29).
            policy: Execution policy instance.
            ticker: Stock symbol.
            seed: Optional path seed for reproducibility.

        Returns:
            ExecutionTrajectory instance.
        """
        if seed is not None:
            self.lob.reset(random_seed=seed)
        else:
            self.lob.reset()

        policy.reset()

        num_steps = len(session_df)
        arrival_price = float(session_df["close"].iloc[0])
        total_market_vol = float(session_df["volume"].sum())
        interval_vwap = float(
            (session_df["close"] * session_df["volume"]).sum() / max(1.0, total_market_vol)
        )
        session_date = str(pd.to_datetime(session_df["timestamp"].iloc[0]).date())

        records: List[TrajectoryRecord] = []
        total_turnover = 0.0
        total_tx_costs = 0.0
        total_spread_cost = 0.0
        total_temp_impact = 0.0

        for t in range(num_steps):
            row = session_df.iloc[t]
            ts = row.get("timestamp")
            raw_mid = float(row["close"])
            interval_vol = float(max(10.0, row["volume"]))
            interval_volat = float(row.get("realised_volatility", 0.18))
            vol_imbalance = float(row.get("volume_imbalance", 0.0))
            vol_regime = str(row.get("volatility_regime", "normal"))
            liq_regime = str(row.get("liquidity_regime", "medium"))

            # 1. Construct simulated OrderBookState
            state = self.lob.create_state(
                step=t,
                mid_price=raw_mid,
                interval_volume=interval_vol,
                interval_volatility=interval_volat,
                timestamp=ts,
                volume_imbalance=vol_imbalance,
                volatility_regime=vol_regime,
                liquidity_regime=liq_regime,
            )

            # 2. Query execution policy for child slice action
            decision = policy.compute_action(current_step=t, state=state)

            # 3. Execute order in LOB simulator
            fill: ChildOrderFill = self.lob.execute_order(
                state=state,
                requested_shares=decision.target_shares,
                is_passive=decision.is_passive,
                max_participation=self.max_participation,
            )

            # 4. Update policy inventory state
            policy.update_fill(fill.shares_filled)

            # Accumulate turnover and costs
            turnover_t = fill.shares_filled * fill.fill_price
            total_turnover += turnover_t
            total_tx_costs += fill.transaction_cost_paid
            total_spread_cost += fill.spread_cost_paid
            total_temp_impact += fill.temporary_impact_paid

            records.append(
                TrajectoryRecord(
                    step=t,
                    timestamp=ts,
                    mid_price=state.mid_price,
                    market_volume=interval_vol,
                    volatility=interval_volat,
                    spread=state.spread,
                    target_shares=decision.target_shares,
                    filled_shares=fill.shares_filled,
                    fill_price=fill.fill_price,
                    remaining_inventory=policy.remaining_inventory,
                    is_passive=decision.is_passive,
                    spread_cost_paid=fill.spread_cost_paid,
                    temporary_impact_paid=fill.temporary_impact_paid,
                    permanent_impact_generated=fill.permanent_impact_generated,
                    transaction_cost_paid=fill.transaction_cost_paid,
                    volatility_regime=vol_regime,
                    liquidity_regime=liq_regime,
                )
            )

        # Mandatory Terminal Sweep: Guarantee 100% completion (Q_T = 0)
        terminal_unexecuted = policy.remaining_inventory
        if terminal_unexecuted > 0:
            final_row = session_df.iloc[-1]
            last_mid = float(final_row["close"]) + self.lob.cumulative_permanent_impact
            last_vol = float(final_row["volume"])
            last_volat = float(final_row.get("realised_volatility", 0.18))

            # Terminal sweep executes remaining shares aggressively
            sweep_fill = self.lob.execute_order(
                state=self.lob.create_state(
                    step=num_steps,
                    mid_price=last_mid,
                    interval_volume=last_vol,
                    interval_volatility=last_volat,
                ),
                requested_shares=terminal_unexecuted,
                is_passive=False,
                max_participation=1.0,  # Terminal sweep ignores normal participation caps
            )
            policy.update_fill(sweep_fill.shares_filled)
            sweep_turnover = sweep_fill.shares_filled * sweep_fill.fill_price
            total_turnover += sweep_turnover
            total_tx_costs += sweep_fill.transaction_cost_paid
            total_spread_cost += sweep_fill.spread_cost_paid
            total_temp_impact += sweep_fill.temporary_impact_paid

        total_exec_shares = policy.executed_shares
        avg_price = total_turnover / total_exec_shares if total_exec_shares > 0 else arrival_price

        return ExecutionTrajectory(
            policy_name=type(policy).__name__,
            ticker=ticker,
            date=session_date,
            parent_order_size=policy.parent_order_size,
            arrival_price=arrival_price,
            interval_vwap=interval_vwap,
            total_market_volume=total_market_vol,
            records=records,
            total_executed_shares=total_exec_shares,
            average_execution_price=avg_price,
            terminal_unexecuted_shares=policy.remaining_inventory,
            total_turnover=total_turnover,
            total_transaction_costs=total_tx_costs,
            total_spread_cost=total_spread_cost,
            total_temporary_impact=total_temp_impact,
            terminal_permanent_impact=self.lob.cumulative_permanent_impact,
            path_seed=seed or self.lob.random_seed,
        )
