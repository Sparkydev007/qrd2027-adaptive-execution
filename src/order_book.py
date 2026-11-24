"""Limit Order Book (LOB) state representation and synthetic fill engine.

Maintains point-in-time order book state, effective queue depth,
bid/ask quotes, and stochastic fill logic for passive and aggressive child orders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OrderBookState:
    """Snapshot of simulated top-of-book state at minute t."""
    mid_price: float
    spread: float
    best_bid: float
    best_ask: float
    bid_depth: float
    ask_depth: float
    market_volume: float
    volatility: float


@dataclass
class ChildOrderFill:
    """Execution receipt for a child slice."""
    shares_filled: float
    fill_price: float
    spread_cost_paid: float
    temporary_impact_paid: float
    is_passive: bool
    unfilled_shares: float


class LimitOrderBookSimulator:
    """Microstructure-calibrated point-in-time limit order book simulator.

    Simulates discrete 1-minute order book dynamics calibrated from empirical
    Indian equity data, modeling aggressive crossing and passive queue fills.
    """

    def __init__(
        self,
        baseline_spread_bps: float = 5.0,
        depth_multiplier: float = 0.05,
        temp_impact_eta: float = 0.5,
        temp_impact_alpha: float = 0.5,
        random_seed: int = 42,
    ):
        self.baseline_spread_bps = baseline_spread_bps
        self.depth_multiplier = depth_multiplier
        self.temp_impact_eta = temp_impact_eta
        self.temp_impact_alpha = temp_impact_alpha
        self.rng = np.random.default_rng(random_seed)

    def initialize_state(
        self,
        mid_price: float,
        interval_volume: float,
        interval_volatility: float,
    ) -> OrderBookState:
        """Construct order book state for current interval."""
        spread = max(0.05, mid_price * (self.baseline_spread_bps * 1e-4))
        depth = max(100.0, self.depth_multiplier * interval_volume)
        return OrderBookState(
            mid_price=mid_price,
            spread=spread,
            best_bid=mid_price - spread / 2.0,
            best_ask=mid_price + spread / 2.0,
            bid_depth=depth,
            ask_depth=depth,
            market_volume=interval_volume,
            volatility=interval_volatility,
        )

    def execute_child_order(
        self,
        state: OrderBookState,
        order_size: float,
        is_passive: bool = False,
    ) -> ChildOrderFill:
        """Execute a child order slice against current order book state.

        Day 1 skeleton providing foundational execution logic.
        Full queue-priority fill probability will be expanded in Day 3.
        """
        if order_size <= 0:
            return ChildOrderFill(0.0, state.mid_price, 0.0, 0.0, is_passive, 0.0)

        participation = order_size / max(1.0, state.market_volume)
        temp_impact = self.temp_impact_eta * state.volatility * (participation ** self.temp_impact_alpha)

        if not is_passive:
            # Aggressive taker order: pays half-spread + temporary impact
            fill_price = state.best_ask + temp_impact
            spread_cost = state.spread / 2.0
            return ChildOrderFill(
                shares_filled=order_size,
                fill_price=fill_price,
                spread_cost_paid=spread_cost,
                temporary_impact_paid=temp_impact,
                is_passive=False,
                unfilled_shares=0.0,
            )
        else:
            # Passive maker order: joins queue at best bid
            fill_prob = min(1.0, (state.market_volume * 0.5) / (state.ask_depth + order_size))
            filled = order_size if self.rng.random() < fill_prob else 0.0
            unfilled = order_size - filled
            fill_price = state.best_bid if filled > 0 else 0.0
            return ChildOrderFill(
                shares_filled=filled,
                fill_price=fill_price,
                spread_cost_paid=-state.spread / 2.0 if filled > 0 else 0.0,
                temporary_impact_paid=0.0,
                is_passive=True,
                unfilled_shares=unfilled,
            )
