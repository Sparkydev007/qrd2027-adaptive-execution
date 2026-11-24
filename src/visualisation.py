"""Visualisation and publication figure generation module.

Generates high-resolution publication-ready figures for A0 portrait academic poster:
- Intraday U-shaped volume profile curves
- Rolling realized volatility regime distribution
- Implementation shortfall distribution boxplots across policies
- Execution inventory trajectory curves
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
    ax.set_xlabel("30-Minute Intraday Session Buckets (09:15 to 15:30 IST)")
    ax.set_ylabel("Volume Percentage of Day (%)")

    if save_path:
        fig.savefig(save_path, bbox_inches="tight", dpi=300)
    return fig
