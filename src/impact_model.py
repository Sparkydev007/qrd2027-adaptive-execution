"""Market impact models: Temporary and permanent price impact.

Implements square-root temporary price impact and linear permanent price impact
with exponential memory kernels following Almgren-Chriss (2000) and Bouchaud et al. (2009).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketImpactEstimate:
    """Estimated market impact breakdown for a child execution slice."""
    temporary_impact_currency: float
    temporary_impact_bps: float
    permanent_impact_currency: float
    permanent_impact_bps: float


class AlmgrenChrissImpactModel:
    """Almgren-Chriss market impact model with square-root temporary impact."""

    def __init__(
        self,
        temporary_exponent_alpha: float = 0.50,
        temporary_eta: float = 0.50,
        permanent_fraction_gamma: float = 0.10,
    ):
        self.alpha = temporary_exponent_alpha
        self.eta = temporary_eta
        self.gamma = permanent_fraction_gamma

    def calculate_temporary_impact(
        self,
        trade_size: float,
        interval_volume: float,
        volatility: float,
        mid_price: float,
    ) -> float:
        """Compute temporary price impact in currency units.

        Delta P_temp = eta * sigma * (q / V)^alpha * P_mid
        """
        if trade_size <= 0 or interval_volume <= 0:
            return 0.0
        participation = trade_size / interval_volume
        impact_pct = self.eta * volatility * (participation ** self.alpha)
        return float(impact_pct * mid_price)

    def calculate_permanent_impact(
        self,
        trade_size: float,
        interval_volume: float,
        volatility: float,
        mid_price: float,
    ) -> float:
        """Compute permanent price impact in currency units.

        Delta P_perm = gamma * sigma * (q / V) * P_mid
        """
        if trade_size <= 0 or interval_volume <= 0:
            return 0.0
        participation = trade_size / interval_volume
        impact_pct = self.gamma * volatility * participation
        return float(impact_pct * mid_price)

    def evaluate(
        self,
        trade_size: float,
        interval_volume: float,
        volatility: float,
        mid_price: float,
    ) -> MarketImpactEstimate:
        """Evaluate both temporary and permanent impact for an execution slice."""
        temp_curr = self.calculate_temporary_impact(trade_size, interval_volume, volatility, mid_price)
        perm_curr = self.calculate_permanent_impact(trade_size, interval_volume, volatility, mid_price)
        return MarketImpactEstimate(
            temporary_impact_currency=temp_curr,
            temporary_impact_bps=(temp_curr / mid_price) * 10000.0,
            permanent_impact_currency=perm_curr,
            permanent_impact_bps=(perm_curr / mid_price) * 10000.0,
        )
