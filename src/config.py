"""Configuration loader and typed configuration schema.

Provides typed dataclasses and validation for `config/config.yaml`.
Avoids hardcoding parameters in execution, calibration, and audit modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    version: str
    description: str
    research_type: str


@dataclass(frozen=True)
class MarketHoursConfig:
    start: str
    end: str


@dataclass(frozen=True)
class DataConfig:
    source: str
    frequency: str
    timezone: str
    market_hours: MarketHoursConfig
    date_start: str
    date_end: str
    raw_data_dir: Path
    interim_data_dir: Path
    processed_data_dir: Path


@dataclass(frozen=True)
class UniverseConfig:
    stocks: List[str]
    min_history_days: int
    min_average_daily_volume: int


@dataclass(frozen=True)
class SpreadAssumptionConfig:
    method: str
    value_bps: float


@dataclass(frozen=True)
class DepthAssumptionConfig:
    method: str
    multiplier: float


@dataclass(frozen=True)
class ImpactModelConfig:
    temporary_impact_exponent: float
    permanent_impact_fraction: float


@dataclass(frozen=True)
class CalibrationConfig:
    volatility_window: int
    volume_profile_buckets: int
    spread_assumption: SpreadAssumptionConfig
    depth_assumption: DepthAssumptionConfig
    impact_model: ImpactModelConfig
    transaction_cost_bps: float


@dataclass(frozen=True)
class ExecutionConfig:
    parent_order_sizes_adv: List[float]
    execution_horizon_minutes: int
    max_participation_rate: float
    rebalance_frequency: str
    allow_short: bool


@dataclass(frozen=True)
class EvaluationConfig:
    confidence_level: float
    benchmarks: List[str]
    metrics: List[str]


@dataclass(frozen=True)
class RegimeBoundaryConfig:
    volatility_percentile_min: Optional[float] = None
    volatility_percentile_max: Optional[float] = None


@dataclass(frozen=True)
class SimulationConfig:
    random_seed: int
    number_of_paths: int
    regime_definitions: Dict[str, RegimeBoundaryConfig]


@dataclass(frozen=True)
class AppConfig:
    project: ProjectConfig
    data: DataConfig
    universe: UniverseConfig
    calibration: CalibrationConfig
    execution: ExecutionConfig
    evaluation: EvaluationConfig
    simulation: SimulationConfig
    raw_dict: Dict[str, Any] = field(default_factory=dict, repr=False)


def find_config_path(default_path: str | Path = "config/config.yaml") -> Path:
    """Locate configuration file by searching current and parent directories."""
    path = Path(default_path)
    if path.exists():
        return path.resolve()

    # Search upwards for config/config.yaml
    curr = Path.cwd()
    for parent in [curr, *curr.parents]:
        candidate = parent / default_path
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"Configuration file not found at: {default_path}")


def load_config(config_path: Optional[str | Path] = None) -> AppConfig:
    """Load and parse YAML configuration into a typed AppConfig object.

    Args:
        config_path: Path to configuration file. If None, default location is used.

    Returns:
        AppConfig typed container.
    """
    path = find_config_path(config_path or "config/config.yaml")
    logger.info("Loading configuration from: %s", path)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    project_cfg = ProjectConfig(
        name=data["project"]["name"],
        version=data["project"]["version"],
        description=data["project"]["description"],
        research_type=data["project"]["research_type"],
    )

    market_hours = MarketHoursConfig(
        start=str(data["data"]["market_hours"]["start"]),
        end=str(data["data"]["market_hours"]["end"]),
    )

    base_dir = path.parent.parent
    data_cfg = DataConfig(
        source=data["data"]["source"],
        frequency=data["data"]["frequency"],
        timezone=data["data"]["timezone"],
        market_hours=market_hours,
        date_start=str(data["data"]["date_start"]),
        date_end=str(data["data"]["date_end"]),
        raw_data_dir=(base_dir / data["data"]["raw_data_dir"]).resolve(),
        interim_data_dir=(base_dir / data["data"]["interim_data_dir"]).resolve(),
        processed_data_dir=(base_dir / data["data"]["processed_data_dir"]).resolve(),
    )

    universe_cfg = UniverseConfig(
        stocks=list(data["universe"]["stocks"]),
        min_history_days=int(data["universe"]["min_history_days"]),
        min_average_daily_volume=int(data["universe"]["min_average_daily_volume"]),
    )

    calibration_cfg = CalibrationConfig(
        volatility_window=int(data["calibration"]["volatility_window"]),
        volume_profile_buckets=int(data["calibration"]["volume_profile_buckets"]),
        spread_assumption=SpreadAssumptionConfig(
            method=data["calibration"]["spread_assumption"]["method"],
            value_bps=float(data["calibration"]["spread_assumption"]["value_bps"]),
        ),
        depth_assumption=DepthAssumptionConfig(
            method=data["calibration"]["depth_assumption"]["method"],
            multiplier=float(data["calibration"]["depth_assumption"]["multiplier"]),
        ),
        impact_model=ImpactModelConfig(
            temporary_impact_exponent=float(
                data["calibration"]["impact_model"]["temporary_impact_exponent"]
            ),
            permanent_impact_fraction=float(
                data["calibration"]["impact_model"]["permanent_impact_fraction"]
            ),
        ),
        transaction_cost_bps=float(data["calibration"]["transaction_cost_bps"]),
    )

    execution_cfg = ExecutionConfig(
        parent_order_sizes_adv=[
            float(x) for x in data["execution"]["parent_order_sizes_adv"]
        ],
        execution_horizon_minutes=int(data["execution"]["execution_horizon_minutes"]),
        max_participation_rate=float(data["execution"]["max_participation_rate"]),
        rebalance_frequency=data["execution"]["rebalance_frequency"],
        allow_short=bool(data["execution"]["allow_short"]),
    )

    evaluation_cfg = EvaluationConfig(
        confidence_level=float(data["evaluation"]["confidence_level"]),
        benchmarks=list(data["evaluation"]["benchmarks"]),
        metrics=list(data["evaluation"]["metrics"]),
    )

    regimes: Dict[str, RegimeBoundaryConfig] = {}
    for r_name, r_vals in data["simulation"]["regime_definitions"].items():
        regimes[r_name] = RegimeBoundaryConfig(
            volatility_percentile_min=r_vals.get("volatility_percentile_min"),
            volatility_percentile_max=r_vals.get("volatility_percentile_max"),
        )

    simulation_cfg = SimulationConfig(
        random_seed=int(data["simulation"]["random_seed"]),
        number_of_paths=int(data["simulation"]["number_of_paths"]),
        regime_definitions=regimes,
    )

    return AppConfig(
        project=project_cfg,
        data=data_cfg,
        universe=universe_cfg,
        calibration=calibration_cfg,
        execution=execution_cfg,
        evaluation=evaluation_cfg,
        simulation=simulation_cfg,
        raw_dict=data,
    )


# Singleton cache
_CONFIG_CACHE: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """Retrieve cached configuration or load on demand."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None or reload:
        _CONFIG_CACHE = load_config()
    return _CONFIG_CACHE
