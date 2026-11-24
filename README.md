# Liquidity-Adaptive Optimal Execution in Indian Equities: A Microstructure-Aware Simulation Study

**Conference Submission:** QRD 2027 (Conference on Quant, Risk & Data)  
**Format:** A0 Portrait Academic Poster & Working Paper  
**Author:** Quantitative Research & Microstructure Engineering Team  
**Status:** Day 1 Foundation / Reproducible Research Scaffold  

---

## 1. Project Title
**Liquidity-Adaptive Optimal Execution in Indian Equities: A Microstructure-Aware Simulation Study**

## 2. Research Question
Can a liquidity-adaptive execution policy reduce implementation shortfall and market impact relative to Time-Weighted Average Price (TWAP) and Volume-Weighted Average Price (VWAP) in a limit-order-book simulation calibrated to Indian equity market conditions?

## 3. Objective
To construct a reproducible, empirically calibrated simulation environment that evaluates algorithmic parent-order execution policies on National Stock Exchange of India (NSE) equities, quantifying trade-offs across execution shortfall, temporary and permanent price impact, queue risk, and inventory variance across regime transitions.

## 4. Research Gap
Standard institutional optimal execution literature (e.g., Almgren & Chriss, 2000; Gatheral, 2010; Lehalle & Neuman, 2019) is largely calibrated to US and European tick regimes, which exhibit deep consolidated book depth, low spread-to-tick ratios, and inverted maker-taker fee structures. The Indian equity market (NSE) presents distinct structural features:
- A strict price-time priority Central Limit Order Book (CLOB) without maker-taker subsidies.
- Unique mandatory transaction taxes (Securities Transaction Tax / STT, stamp duty, exchange turnover charges, SEBI turnover fees, and GST).
- Asymmetric intraday liquidity profiles driven by pre-market discovery (09:00–09:15 IST), opening volatility clusters, midday European overlap (12:30–14:00 IST), and institutional closing auction dynamics (15:30–16:00 IST).
- Clustered tick sizes (0.05 INR for most equities) creating substantial relative tick sizes across stock price tiers (e.g., ITC at ~450 INR vs. TCS at ~4000 INR).

Prior empirical execution research on Indian equities remains scarce, proprietary, or constrained to coarse daily VWAP benchmarking without controlled microstructure simulation. This project bridges that gap.

## 5. Why This Matters to HFT and Quant Firms
- **Execution Cost Reduction:** For systematic equity funds with high portfolio turnover (>10x annual), execution drag (slippage, market impact, and transaction taxes) frequently erodes 30% to 70% of gross alpha.
- **Microstructure-Aware Slicing:** Naive static schedules (TWAP/VWAP) fail during liquidity droughts and widen adverse selection when market makers pull depth. An adaptive policy that modulates passive-versus-aggressive urgency preserves execution quality.
- **Inventory & Risk Containment:** Quant desks managing non-linear risk mandates require precise control over cumulative parent order variance and terminal liquidation risks.

## 6. Data Requirements
- **Asset Universe:** Top 10 liquid NIFTY 50 equities (e.g., RELIANCE, HDFCBANK, ICICIBANK, INFY, TCS, SBIN, AXISBANK, KOTAKBANK, LT, ITC).
- **History Length:** Minimum 120 trading days of clean intraday data covering full calendar year 2024.
- **Frequency:** 1-minute OHLCV bars with Asia/Kolkata timezone localization.
- **Trading Session:** Regular trading hours (09:15 to 15:30 IST; 375 minutes per session).
- **Sources Supported:** Upstox API, AngelOne API, historical Parquet/CSV archives, or verified synthetic benchmark series.

## 7. Simulator Overview
The simulation engine evaluates algorithmic execution without requiring prohibitive multi-terabyte Level-3 tick data by using a **microstructure-calibrated point-in-time order book simulator**:
- **Macro-State:** Driven by empirical 1-minute OHLCV, rolling realized volatility, and historical intraday volume profiles.
- **Micro-State:** Calibrates instantaneous bid-ask spread and effective book depth per minute using empirical volume multiples and volatility-dependent scaling.
- **Execution Fill Engine:** Simulates aggressive taker orders crossing the spread and passive limit orders joining the queue with realistic fill probabilities and cancellation dynamics.
- **Price Impact:** Incorporates square-root temporary price impact and linear permanent price impact with exponential decay.

## 8. Execution Policies
1. **TWAP (Time-Weighted Average Price):** Slices parent order into deterministic, equal child slices across the execution window.
2. **VWAP (Volume-Weighted Average Price):** Slices volume strictly proportional to the empirical historical intraday volume curve.
3. **Naive Aggressive:** Immediately crosses the spread with market orders upon order arrival (maximum liquidity consumption benchmark).
4. **Percentage of Volume (POV):** Targets a fixed participation rate (e.g., 5% or 10% of instantaneous volume) tracking observed interval volume.
5. **Adaptive Execution Policy (Proposed):** A dynamic, rule-based controller modulating passive vs. aggressive slicing based on:
   - Remaining parent order inventory vs. remaining time.
   - Real-time spread widening / narrowing indicators.
   - Local order book depth and volume imbalance.
   - Instantaneous volatility regimes (calm, normal, stressed).
   - Hard maximum participation constraints (e.g., $\le 20\%$ ADV).

## 9. Evaluation Metrics
All metrics are mathematically formalized in [docs/evaluation_metrics.md](file:///docs/evaluation_metrics.md):
- **Implementation Shortfall (IS):** Peretz/Almgren shortfall versus pre-trade arrival price (in bps).
- **Slippage vs. Arrival & Interval VWAP:** Execution price deviation against market benchmarks.
- **Temporary and Permanent Market Impact:** Measured in basis points.
- **Fill Rate & Passive Fill Ratio:** Percentage of total parent order executed and fraction filled passively.
- **Turnover & Inventory Variance:** Trajectory risk $\mathrm{Var}(Q_t)$ and peak capital utilization.
- **Net Effective Cost:** Shortfall inclusive of Indian statutory levies (STT, GST, stamp duty).

## 10. Folder Structure
```
qrd2027_adaptive_execution/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── config.yaml
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── notebooks/
│   ├── 01_data_audit.ipynb
│   ├── 02_calibration.ipynb
│   └── 03_simulation_results.ipynb
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data_loader.py
│   ├── data_audit.py
│   ├── calibration.py
│   ├── features.py
│   ├── order_book.py
│   ├── execution_policies.py
│   ├── impact_model.py
│   ├── backtester.py
│   ├── evaluation.py
│   └── visualisation.py
├── tests/
│   ├── test_data_loader.py
│   ├── test_data_audit.py
│   └── test_calibration.py
├── reports/
│   ├── figures/
│   └── tables/
└── docs/
    ├── research_design.md
    ├── simulator_scope.md
    ├── evaluation_metrics.md
    ├── data_dictionary.md
    └── project_brief.md
```

## 11. Installation Instructions
Prerequisites: Python 3.11+ and Git.

```bash
# Clone the repository
git clone https://github.com/quant-research/qrd2027_adaptive_execution.git
cd qrd2027_adaptive_execution

# Create and activate a clean virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install exact pinned research dependencies
pip install -r requirements.txt
```

## 12. How to Run the Data Audit
Run the automated audit module on raw intraday data:
```bash
python -c "from src.data_audit import run_audit_pipeline; run_audit_pipeline('data/raw/sample_RELIANCE_1min.csv')"
```
Or open the interactive Jupyter notebook:
```bash
jupyter lab notebooks/01_data_audit.ipynb
```

## 13. How to Run Calibration & Simulation
Execute the empirical calibration pipeline against historical clean data:
```bash
python -c "from src.calibration import run_calibration_pipeline; run_calibration_pipeline('data/processed/RELIANCE_1min.parquet')"
```
Execute the complete multi-stock execution simulator across all 5 policies (TWAP, VWAP, Naive Aggressive, POV, Liquidity-Adaptive):
```bash
python -m src.run_simulation
```
Results and publication charts are saved directly to `reports/tables/` and `reports/figures/`.

## 14. How to Reproduce Results
All experimental procedures are deterministic and configuration-driven:
1. Inspect or modify execution parameters in `config/config.yaml`.
2. Run test suite: `pytest -v tests/` (all 36 unit tests pass).
3. Execute the simulation engine: `python -m src.run_simulation`
4. Inspect interactive notebooks: `jupyter lab notebooks/`

## 15. Important Limitations
1. **Calibration Granularity:** Calibrated on 1-minute OHLCV data, not Level-2/Level-3 direct feed tick logs.
2. **Synthetic Microstructure:** Queue priority is simulated using stochastic point-in-time fills and queue depth absorption rather than deterministic exchange matching engine order matching logs.
3. **No Latency Modeling:** Colocation network transport latency (<100 microseconds) is abstracted away; simulation operates on discrete algorithmic decision cycles.
4. **Passive Adversity:** Adverse selection for passive limit orders is parameterized via volatility and spread decay rather than counterparty tag identification.

## 16. Academic & Regulatory Disclaimer
**Notice:** This research is strictly simulation-based and conducted exclusively for academic presentation at QRD 2027. It does not constitute investment advice, financial promotion, or a recommendation to trade securities. None of the models predict asset returns or claim live-trading profitability.

## 17. Research Roadmap (Days 1–7)
- **Day 1 (Completed):** Project scaffold, YAML configuration, research design docs, data loader, comprehensive 14-point data audit, calibration skeleton, unit tests, and audit notebook.
- **Day 2 (Completed):** Discrete-time limit order book simulator, queue-position approximation, Almgren-Chriss market impact engine (square-root temporary, linear permanent with full persistence), 5 execution policies (TWAP, VWAP, Naive Aggressive, POV, Liquidity-Adaptive), 3-stock universe calibration (RELIANCE, HDFCBANK, TCS), simulation results, and 4 publication-quality 300 DPI figures.
- **Day 3:** Advanced queue dynamics, adverse selection hazard rates, cancellation ratio calibration, and fill-probability empirical validation.
- **Day 4:** Multi-day Monte Carlo path generation, stochastic drift scenarios, and non-linear market-impact decay kernels.
- **Day 5:** Sensitivity analysis across participation caps (10% to 30%), impact parameter perturbations, and cross-asset beta clustering.
- **Day 6:** Statistical hypothesis testing ($H_1$–$H_4$ paired t-tests, Wilcoxon signed-rank tests), bootstrap confidence intervals, and regime stress testing.
- **Day 7:** Production of high-resolution publication charts, LaTeX tables, and A0 portrait poster assets for QRD 2027.
