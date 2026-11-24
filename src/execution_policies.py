"""Execution policies: TWAP, VWAP, Naive Aggressive, Percentage-of-Volume (POV), and Liquidity-Adaptive.

Implements institutional execution benchmarks and a transparent, rule-based
microstructure-aware liquidity-adaptive execution controller without machine learning.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from src.order_book import OrderBookState

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    """Action computed by an execution policy for discrete time step t."""
    target_shares: float
    is_passive: bool
    urgency_score: float
    metadata: Dict[str, object]


class BaseExecutionPolicy(ABC):
    """Abstract base class for parent-order execution policies."""

    def __init__(self, parent_order_size: float, horizon_steps: int = 375):
        self.parent_order_size = float(parent_order_size)
        self.horizon_steps = int(horizon_steps)
        self.remaining_inventory = float(parent_order_size)
        self.executed_shares = 0.0

    def reset(self):
        """Reset internal inventory tracking for a new simulation path."""
        self.remaining_inventory = float(self.parent_order_size)
        self.executed_shares = 0.0

    def update_fill(self, filled_shares: float):
        """Update inventory state following child order execution."""
        self.executed_shares += filled_shares
        self.remaining_inventory = max(0.0, self.remaining_inventory - filled_shares)

    @abstractmethod
    def compute_action(
        self,
        current_step: int,
        state: OrderBookState,
    ) -> PolicyDecision:
        """Compute child order slice size and passive/aggressive flag for step t."""
        pass


class TWAPPolicy(BaseExecutionPolicy):
    """Time-Weighted Average Price (TWAP) execution policy.

    Slices remaining inventory uniformly across remaining intervals:
    q_t = Q_t / (T - t)
    """

    def compute_action(self, current_step: int, state: OrderBookState) -> PolicyDecision:
        if self.remaining_inventory <= 0:
            return PolicyDecision(0.0, False, 0.0, {"policy": "TWAP"})

        steps_remaining = max(1, self.horizon_steps - current_step)
        if current_step >= self.horizon_steps - 1:
            # Final interval: sweep remaining balance
            target = self.remaining_inventory
        else:
            target = self.remaining_inventory / steps_remaining

        target = min(self.remaining_inventory, target)
        return PolicyDecision(
            target_shares=float(target),
            is_passive=False,
            urgency_score=0.5,
            metadata={"policy": "TWAP", "steps_remaining": steps_remaining},
        )


class VWAPPolicy(BaseExecutionPolicy):
    """Volume-Weighted Average Price (VWAP) execution policy.

    Slices order volume proportional to the historical empirical intraday volume profile:
    q_t = Q_0 * v_bar_t
    """

    def __init__(
        self,
        parent_order_size: float,
        horizon_steps: int,
        volume_profile: List[float],
    ):
        super().__init__(parent_order_size, horizon_steps)
        self.volume_profile = volume_profile

    def compute_action(self, current_step: int, state: OrderBookState) -> PolicyDecision:
        if self.remaining_inventory <= 0:
            return PolicyDecision(0.0, False, 0.0, {"policy": "VWAP"})

        steps_remaining = max(1, self.horizon_steps - current_step)
        if current_step >= self.horizon_steps - 1:
            target = self.remaining_inventory
        else:
            if current_step < len(self.volume_profile):
                # Historical profile target
                profile_frac = self.volume_profile[current_step]
                target = self.parent_order_size * profile_frac
            else:
                target = self.remaining_inventory / steps_remaining

        target = min(self.remaining_inventory, target)
        return PolicyDecision(
            target_shares=float(target),
            is_passive=False,
            urgency_score=0.5,
            metadata={"policy": "VWAP", "steps_remaining": steps_remaining},
        )


class NaiveAggressivePolicy(BaseExecutionPolicy):
    """Naive Aggressive execution benchmark.

    Attempts to execute 100% of parent order immediately at t=0 using market orders.
    Any unexecuted balance (due to participation constraints) is executed at subsequent steps.
    """

    def compute_action(self, current_step: int, state: OrderBookState) -> PolicyDecision:
        if self.remaining_inventory <= 0:
            return PolicyDecision(0.0, False, 0.0, {"policy": "NaiveAggressive"})

        return PolicyDecision(
            target_shares=float(self.remaining_inventory),
            is_passive=False,
            urgency_score=1.0,
            metadata={"policy": "NaiveAggressive", "step": current_step},
        )


class PercentageOfVolumePolicy(BaseExecutionPolicy):
    """Percentage of Volume (POV) execution policy.

    Executes a target participation fraction rho (default: 10%) of interval volume.
    Ramps urgency near the execution horizon end to guarantee completion.
    """

    def __init__(
        self,
        parent_order_size: float,
        horizon_steps: int = 375,
        target_participation_rate: float = 0.10,
    ):
        super().__init__(parent_order_size, horizon_steps)
        self.target_participation = target_participation_rate

    def compute_action(self, current_step: int, state: OrderBookState) -> PolicyDecision:
        if self.remaining_inventory <= 0:
            return PolicyDecision(0.0, False, 0.0, {"policy": "POV"})

        steps_remaining = max(1, self.horizon_steps - current_step)

        # In final 5 minutes, accelerate participation to guarantee order completion
        if current_step >= self.horizon_steps - 1:
            target = self.remaining_inventory
        elif steps_remaining <= 5:
            accelerated_rate = min(0.20, (self.remaining_inventory / max(1.0, state.market_volume * steps_remaining)))
            target = min(self.remaining_inventory, accelerated_rate * state.market_volume)
        else:
            target = min(self.remaining_inventory, self.target_participation * state.market_volume)

        target = min(self.remaining_inventory, max(0.0, target))
        return PolicyDecision(
            target_shares=float(target),
            is_passive=False,
            urgency_score=0.5,
            metadata={"policy": "POV", "participation_rate": self.target_participation},
        )


class LiquidityAdaptivePolicy(BaseExecutionPolicy):
    """Rule-Based Liquidity-Adaptive Optimal Execution Policy.

    Dynamically modulates slice aggressiveness and maker/taker routing using:
    1. Inventory progress vs time elapsed (Urgency score)
    2. Realized volatility regime (calm = accelerate, stressed = throttle)
    3. Bid-ask spread wideness (wide = favor passive maker, tight = aggressive taker)
    4. Top-of-book depth & volume imbalance
    5. Terminal completion guarantee constraint
    """

    def __init__(
        self,
        parent_order_size: float,
        horizon_steps: int = 375,
        volume_profile: Optional[List[float]] = None,
        max_participation: float = 0.20,
        baseline_spread_bps: float = 5.0,
    ):
        super().__init__(parent_order_size, horizon_steps)
        self.volume_profile = volume_profile or [1.0 / horizon_steps] * horizon_steps
        self.max_participation = max_participation
        self.baseline_spread_bps = baseline_spread_bps

    def compute_action(self, current_step: int, state: OrderBookState) -> PolicyDecision:
        if self.remaining_inventory <= 0:
            return PolicyDecision(0.0, False, 0.0, {"policy": "Adaptive"})

        steps_remaining = max(1, self.horizon_steps - current_step)

        # 1. Terminal completion check: final minute must sweep all remaining shares
        if current_step >= self.horizon_steps - 1:
            return PolicyDecision(
                target_shares=float(self.remaining_inventory),
                is_passive=False,
                urgency_score=2.0,
                metadata={"policy": "Adaptive", "mode": "terminal_sweep"},
            )

        # 2. Urgency calculation: ratio of inventory fraction remaining to time fraction remaining
        fraction_inventory_remaining = self.remaining_inventory / self.parent_order_size
        fraction_time_remaining = steps_remaining / self.horizon_steps
        urgency = fraction_inventory_remaining / max(0.001, fraction_time_remaining)

        # 3. Baseline slice from intraday volume curve
        profile_idx = min(current_step, len(self.volume_profile) - 1)
        base_slice = self.parent_order_size * self.volume_profile[profile_idx]

        # 4. Volatility regime multiplier
        if state.volatility_regime == "stressed":
            vol_multiplier = 0.75  # Throttle during high volatility voids
        elif state.volatility_regime == "calm":
            vol_multiplier = 1.25  # Accelerate during stable regimes
        else:
            vol_multiplier = 1.00

        # 5. Spread sensitivity multiplier
        spread_bps = (state.spread / state.mid_price) * 10000.0 if state.mid_price > 0 else self.baseline_spread_bps
        spread_ratio = spread_bps / max(1.0, self.baseline_spread_bps)

        # 6. Order imbalance signal (positive buyer imbalance implies price will rise -> increase urgency)
        imbalance_multiplier = 1.0 + 0.20 * state.volume_imbalance

        # 7. Adaptive target slice
        adjusted_target = base_slice * urgency * vol_multiplier * imbalance_multiplier

        # Respect participation constraint
        max_slice = self.max_participation * state.market_volume
        target_shares = min(self.remaining_inventory, max_slice, max(1.0, adjusted_target))

        # 8. Maker vs Taker Routing Decision:
        # Route passively when:
        # - Not in critical terminal window (>10 minutes left)
        # - Urgency is moderate (<= 1.25)
        # - Spread is wide (spread_ratio >= 0.95), making earning the spread advantageous
        is_passive = (
            (steps_remaining > 10)
            and (urgency <= 1.25)
            and (spread_ratio >= 0.95)
            and (state.volatility_regime != "stressed")
        )

        return PolicyDecision(
            target_shares=float(target_shares),
            is_passive=is_passive,
            urgency_score=float(urgency),
            metadata={
                "policy": "Adaptive",
                "urgency": float(urgency),
                "vol_multiplier": vol_multiplier,
                "spread_ratio": float(spread_ratio),
                "is_passive": is_passive,
            },
        )


# Alias for backward compatibility
AdaptiveExecutionPolicy = LiquidityAdaptivePolicy
