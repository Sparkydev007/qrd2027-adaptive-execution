"""Unit tests for execution simulator, impact model, and five execution policies."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtester import ExecutionBacktester
from src.config import get_config
from src.evaluation import evaluate_trajectory
from src.execution_policies import (
    LiquidityAdaptivePolicy,
    NaiveAggressivePolicy,
    PercentageOfVolumePolicy,
    TWAPPolicy,
    VWAPPolicy,
)
from src.impact_model import AlmgrenChrissImpactModel
from src.order_book import LimitOrderBookSimulator, OrderBookState


@pytest.fixture
def clean_session_df() -> pd.DataFrame:
    """Fixture providing one clean 375-minute continuous trading session."""
    times = pd.date_range("2024-01-01 09:15:00", periods=375, freq="1min", tz="Asia/Kolkata")
    n = len(times)
    np.random.seed(42)
    closes = 2500.0 + np.cumsum(np.random.normal(0, 0.5, n))
    vols = np.random.poisson(lam=2000, size=n)
    return pd.DataFrame({
        "timestamp": times,
        "open": closes,
        "high": closes + 1.0,
        "low": closes - 1.0,
        "close": closes,
        "volume": np.maximum(50, vols),
        "realised_volatility": [0.18] * n,
        "volume_imbalance": [0.0] * n,
        "volatility_regime": ["normal"] * n,
        "liquidity_regime": ["medium"] * n,
    })


@pytest.fixture
def simulator() -> LimitOrderBookSimulator:
    return LimitOrderBookSimulator(
        baseline_spread_bps=5.0,
        depth_multiplier=0.05,
        temp_impact_alpha=0.5,
        temp_impact_eta=0.5,
        perm_impact_gamma=0.10,
        transaction_cost_bps=2.4653,
        random_seed=42,
    )


def test_twap_completes_parent_order(clean_session_df, simulator):
    """Test 1: TWAP policy completes 100% of the parent order."""
    q0 = 5000.0
    policy = TWAPPolicy(parent_order_size=q0, horizon_steps=375)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)

    assert np.isclose(traj.total_executed_shares, q0, atol=1e-4)
    assert traj.terminal_unexecuted_shares == 0.0


def test_vwap_completes_parent_order(clean_session_df, simulator):
    """Test 2: VWAP policy completes 100% of the parent order."""
    q0 = 5000.0
    vol_profile = [1.0 / 375] * 375
    policy = VWAPPolicy(parent_order_size=q0, horizon_steps=375, volume_profile=vol_profile)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)

    assert np.isclose(traj.total_executed_shares, q0, atol=1e-4)
    assert traj.terminal_unexecuted_shares == 0.0


def test_naive_aggressive_completes_parent_order(clean_session_df, simulator):
    """Test 3: Naive aggressive completes 100% of the parent order."""
    q0 = 5000.0
    policy = NaiveAggressivePolicy(parent_order_size=q0, horizon_steps=375)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)

    assert np.isclose(traj.total_executed_shares, q0, atol=1e-4)
    assert traj.terminal_unexecuted_shares == 0.0


def test_pov_respects_participation_constraints(clean_session_df, simulator):
    """Test 4: POV respects max participation rate constraint."""
    q0 = 10000.0
    max_part = 0.20
    policy = PercentageOfVolumePolicy(parent_order_size=q0, horizon_steps=375, target_participation_rate=0.10)
    backtester = ExecutionBacktester(simulator, max_participation=max_part)
    traj = backtester.run_session(clean_session_df, policy)

    df_rec = traj.to_dataframe()
    # Check that in normal execution intervals (excluding terminal sweep), participation does not exceed max_part
    normal_steps = df_rec.iloc[:-1]
    participation_rates = normal_steps["filled_shares"] / normal_steps["market_volume"]
    assert (participation_rates <= max_part + 1e-5).all()


def test_adaptive_policy_respects_inventory_and_completion(clean_session_df, simulator):
    """Test 5: Adaptive policy respects non-negative inventory and terminal completion."""
    q0 = 8000.0
    vol_profile = [1.0 / 375] * 375
    policy = LiquidityAdaptivePolicy(parent_order_size=q0, horizon_steps=375, volume_profile=vol_profile)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)

    assert np.isclose(traj.total_executed_shares, q0, atol=1e-4)
    assert traj.terminal_unexecuted_shares == 0.0

    df_rec = traj.to_dataframe()
    # Non-negative inventory throughout
    assert (df_rec["remaining_inventory"] >= 0.0).all()
    assert (df_rec["remaining_inventory"] <= q0).all()


def test_temporary_impact_increases_with_participation():
    """Test 6: Temporary impact monotonically increases with participation rate."""
    model = AlmgrenChrissImpactModel(temporary_exponent_alpha=0.5, temporary_eta=0.5)
    vol = 0.18
    mid = 2500.0
    market_vol = 10000.0

    imp_low = model.calculate_temporary_impact(trade_size=100.0, interval_volume=market_vol, volatility=vol, mid_price=mid)
    imp_med = model.calculate_temporary_impact(trade_size=500.0, interval_volume=market_vol, volatility=vol, mid_price=mid)
    imp_high = model.calculate_temporary_impact(trade_size=1500.0, interval_volume=market_vol, volatility=vol, mid_price=mid)

    assert 0.0 < imp_low < imp_med < imp_high


def test_permanent_impact_persists_across_intervals(clean_session_df, simulator):
    """Test 7: Permanent impact accumulates and persistently shifts mid-price."""
    simulator.reset(random_seed=42)
    state1 = simulator.create_state(step=0, mid_price=2500.0, interval_volume=10000.0, interval_volatility=0.18)
    # Execute a trade that causes permanent impact
    fill1 = simulator.execute_order(state1, requested_shares=1000.0, is_passive=False)
    assert fill1.permanent_impact_generated > 0.0
    assert simulator.cumulative_permanent_impact > 0.0

    # Step 2: mid-price should be shifted upwards by the accumulated permanent impact
    state2 = simulator.create_state(step=1, mid_price=2500.0, interval_volume=10000.0, interval_volatility=0.18)
    assert state2.mid_price == 2500.0 + fill1.permanent_impact_generated


def test_transaction_costs_calculated_correctly(clean_session_df, simulator):
    """Test 8: Transaction costs are charged at exact buy-side intraday rate."""
    q0 = 1000.0
    policy = NaiveAggressivePolicy(parent_order_size=q0, horizon_steps=375)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)

    expected_cost = traj.total_turnover * (2.4653 * 1e-4)
    assert np.isclose(traj.total_transaction_costs, expected_cost, atol=1e-2)


def test_implementation_shortfall_calculated_correctly(clean_session_df, simulator):
    """Test 9: Implementation Shortfall matches Perold formula."""
    q0 = 2000.0
    policy = TWAPPolicy(parent_order_size=q0, horizon_steps=375)
    backtester = ExecutionBacktester(simulator)
    traj = backtester.run_session(clean_session_df, policy)
    metrics = evaluate_trajectory(traj)

    expected_is_inr = traj.total_turnover - (q0 * traj.arrival_price)
    expected_is_bps = (expected_is_inr / (q0 * traj.arrival_price)) * 10000.0

    assert np.isclose(metrics.implementation_shortfall_inr, expected_is_inr, atol=1e-2)
    assert np.isclose(metrics.implementation_shortfall_bps, expected_is_bps, atol=1e-3)


def test_random_seeds_produce_reproducible_results(clean_session_df, simulator):
    """Test 10: Fixed random seeds produce byte-identical execution trajectories."""
    q0 = 3000.0
    policy1 = TWAPPolicy(parent_order_size=q0, horizon_steps=375)
    policy2 = TWAPPolicy(parent_order_size=q0, horizon_steps=375)
    backtester = ExecutionBacktester(simulator)

    traj1 = backtester.run_session(clean_session_df, policy1, seed=123)
    traj2 = backtester.run_session(clean_session_df, policy2, seed=123)

    assert np.isclose(traj1.total_turnover, traj2.total_turnover, atol=1e-5)
    assert np.isclose(traj1.average_execution_price, traj2.average_execution_price, atol=1e-5)
    assert np.isclose(traj1.total_temporary_impact, traj2.total_temporary_impact, atol=1e-5)
