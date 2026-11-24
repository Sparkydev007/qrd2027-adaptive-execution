"""Limit Order Book (LOB) state representation and event-driven fill simulator.

Maintains point-in-time order book state, effective queue depth,
bid/ask quotes, stochastic arrival, queue-position approximation,
and market/limit order fill mechanics under temporary and permanent price impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np
import pandas as pd

from src.impact_model import AlmgrenChrissImpactModel

logger = logging.getLogger(__name__)


@dataclass
class OrderBookState:
    """Snapshot of simulated top-of-book state at discrete minute t."""
    step: int
    timestamp: Optional[pd.Timestamp]
    mid_price: float
    spread: float
    best_bid: float
    best_ask: float
    bid_depth: float
    ask_depth: float
    market_volume: float
    volatility: float
    volume_imbalance: float = 0.0
    volatility_regime: str = "normal"
    liquidity_regime: str = "medium"


@dataclass
class ChildOrderFill:
    """Execution receipt for an individual child slice."""
    step: int
    requested_shares: float
    shares_filled: float
    fill_price: float
    spread_cost_paid: float
    temporary_impact_paid: float
    permanent_impact_generated: float
    transaction_cost_paid: float
    is_passive: bool
    unfilled_shares: float
    participation_rate: float
    effective_slippage_bps: float


class LimitOrderBookSimulator:
    """Microstructure-calibrated point-in-time limit order book simulator.

    Simulates discrete 1-minute order book dynamics calibrated from empirical
    Indian equity data, modeling aggressive taker crossing and passive maker queue fills.

    IMPORTANT DISCLAIMER:
    This simulator models top-of-book effective depth and spreads using theoretical
    microstructure formulations and empirical 1-minute calibration. It does NOT claim
    to use real Level-2/Level-3 order book feeds, real queue position, or exchange latency.
    """

    def __init__(
        self,
        baseline_spread_bps: float = 5.0,
        depth_multiplier: float = 0.05,
        temp_impact_alpha: float = 0.50,
        temp_impact_eta: float = 0.50,
        perm_impact_gamma: float = 0.10,
        queue_absorption_theta: float = 0.40,
        transaction_cost_bps: float = 2.4653,  # Buy-side intraday programmatic total
        random_seed: int = 42,
    ):
        self.baseline_spread_bps = baseline_spread_bps
        self.depth_multiplier = depth_multiplier
        self.queue_theta = queue_absorption_theta
        self.transaction_cost_bps = transaction_cost_bps
        self.impact_model = AlmgrenChrissImpactModel(
            temporary_exponent_alpha=temp_impact_alpha,
            temporary_eta=temp_impact_eta,
            permanent_fraction_gamma=perm_impact_gamma,
        )
        self.random_seed = random_seed
        self.rng = np.random.default_rng(random_seed)
        self.cumulative_permanent_impact: float = 0.0

    def reset(self, random_seed: Optional[int] = None):
        """Reset simulator state and reseed random number generator."""
        seed = random_seed if random_seed is not None else self.random_seed
        self.rng = np.random.default_rng(seed)
        self.cumulative_permanent_impact = 0.0

    def create_state(
        self,
        step: int,
        mid_price: float,
        interval_volume: float,
        interval_volatility: float,
        timestamp: Optional[pd.Timestamp] = None,
        volume_imbalance: float = 0.0,
        volatility_regime: str = "normal",
        liquidity_regime: str = "medium",
    ) -> OrderBookState:
        """Construct point-in-time order book state for current interval.

        Accounts for accumulated permanent market impact from previous child orders.
        """
        # Apply accumulated permanent price impact to base mid price
        adjusted_mid = mid_price + self.cumulative_permanent_impact

        # Compute spread in rupees (enforce minimum tick size of 0.05 INR for NSE)
        spread_bps = self.baseline_spread_bps
        # Spread widening in stressed volatility regimes
        if volatility_regime == "stressed":
            spread_bps *= 1.4
        elif volatility_regime == "calm":
            spread_bps *= 0.85

        spread = max(0.05, adjusted_mid * (spread_bps * 1e-4))
        spread = round(spread / 0.05) * 0.05  # Round to tick size 0.05
        spread = max(0.05, spread)

        # Depth at best quotes
        effective_vol = max(100.0, interval_volume)
        base_depth = max(100.0, self.depth_multiplier * effective_vol)

        # Asymmetric depth conditioned on volume imbalance
        bid_depth = max(50.0, base_depth * (1.0 + 0.5 * volume_imbalance))
        ask_depth = max(50.0, base_depth * (1.0 - 0.5 * volume_imbalance))

        return OrderBookState(
            step=step,
            timestamp=timestamp,
            mid_price=adjusted_mid,
            spread=spread,
            best_bid=adjusted_mid - spread / 2.0,
            best_ask=adjusted_mid + spread / 2.0,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            market_volume=effective_vol,
            volatility=max(0.01, interval_volatility),
            volume_imbalance=volume_imbalance,
            volatility_regime=volatility_regime,
            liquidity_regime=liquidity_regime,
        )

    def execute_order(
        self,
        state: OrderBookState,
        requested_shares: float,
        is_passive: bool = False,
        max_participation: float = 0.20,
    ) -> ChildOrderFill:
        """Execute a child order slice against current order book state.

        Supports:
        - Aggressive taker orders crossing the spread with square-root temporary impact
        - Passive maker orders joining the queue behind visible depth
        - Participation rate capping
        - Permanent market impact accumulation
        - Transaction cost deduction
        """
        if requested_shares <= 0:
            return ChildOrderFill(
                step=state.step,
                requested_shares=0.0,
                shares_filled=0.0,
                fill_price=state.mid_price,
                spread_cost_paid=0.0,
                temporary_impact_paid=0.0,
                permanent_impact_generated=0.0,
                transaction_cost_paid=0.0,
                is_passive=is_passive,
                unfilled_shares=0.0,
                participation_rate=0.0,
                effective_slippage_bps=0.0,
            )

        # Hard participation limit (e.g. 20% of interval volume)
        max_executable = max_participation * state.market_volume
        capped_shares = min(requested_shares, max_executable)

        if not is_passive:
            # === AGGRESSIVE (TAKER) EXECUTION ===
            # Crosses spread: buys at best_ask + temporary impact
            filled_shares = capped_shares
            unfilled_shares = requested_shares - filled_shares
            participation = filled_shares / state.market_volume

            # Calculate impacts
            impacts = self.impact_model.evaluate(
                trade_size=filled_shares,
                interval_volume=state.market_volume,
                volatility=state.volatility,
                mid_price=state.mid_price,
            )

            temp_impact_inr = impacts.temporary_impact_currency
            perm_impact_inr = impacts.permanent_impact_currency

            # Taker fill price = best_ask + temporary impact
            half_spread = state.spread / 2.0
            fill_price = state.best_ask + temp_impact_inr
            spread_cost_inr = half_spread * filled_shares

            # Accumulate permanent impact on mid-price persistently
            self.cumulative_permanent_impact += perm_impact_inr

        else:
            # === PASSIVE (MAKER) QUEUE EXECUTION ===
            # Joins queue at best_bid. Fill depends on incoming volume depleting queue depth.
            # Effective incoming taker flow consuming queue:
            # In buy order, incoming market sell volume hits bid
            incoming_absorbing_volume = self.queue_theta * state.market_volume * (1.0 - 0.2 * state.volume_imbalance)
            incoming_absorbing_volume = max(0.0, incoming_absorbing_volume)

            # Queue-position logic: our order sits behind existing bid depth
            queue_ahead = state.bid_depth
            if incoming_absorbing_volume <= queue_ahead:
                # Queue ahead was not depleted: 0 shares filled
                filled_shares = 0.0
            elif incoming_absorbing_volume >= (queue_ahead + capped_shares):
                # Entire queue and our slice were consumed
                filled_shares = capped_shares
            else:
                # Partial execution: our position in queue was partially reached
                filled_shares = incoming_absorbing_volume - queue_ahead

            unfilled_shares = requested_shares - filled_shares
            participation = filled_shares / state.market_volume if state.market_volume > 0 else 0.0

            if filled_shares > 0:
                # Passive fill earns the half-spread; temporary impact is negligible for maker
                fill_price = state.best_bid
                spread_cost_inr = - (state.spread / 2.0) * filled_shares  # Negative cost = earned spread
                temp_impact_inr = 0.0

                # Permanent impact generated by passive flow (lower than aggressive: 50% fraction)
                perm_impact_inr = self.impact_model.calculate_permanent_impact(
                    trade_size=filled_shares,
                    interval_volume=state.market_volume,
                    volatility=state.volatility,
                    mid_price=state.mid_price,
                ) * 0.50
                self.cumulative_permanent_impact += perm_impact_inr
            else:
                fill_price = 0.0
                spread_cost_inr = 0.0
                temp_impact_inr = 0.0
                perm_impact_inr = 0.0

        # Transaction cost calculation in currency units
        turnover = filled_shares * fill_price
        tx_cost_inr = turnover * (self.transaction_cost_bps * 1e-4) if filled_shares > 0 else 0.0

        # Slippage vs mid-price in basis points
        if filled_shares > 0 and state.mid_price > 0:
            slippage_bps = ((fill_price - state.mid_price) / state.mid_price) * 10000.0
        else:
            slippage_bps = 0.0

        return ChildOrderFill(
            step=state.step,
            requested_shares=requested_shares,
            shares_filled=filled_shares,
            fill_price=fill_price,
            spread_cost_paid=spread_cost_inr,
            temporary_impact_paid=temp_impact_inr * filled_shares if not is_passive else 0.0,
            permanent_impact_generated=perm_impact_inr,
            transaction_cost_paid=tx_cost_inr,
            is_passive=is_passive,
            unfilled_shares=unfilled_shares,
            participation_rate=participation,
            effective_slippage_bps=slippage_bps,
        )
