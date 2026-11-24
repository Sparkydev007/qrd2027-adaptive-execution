# Liquidity-Adaptive Optimal Execution in Indian Equities: A Microstructure-Aware Simulation Study

[![Conference](https://img.shields.io/badge/Conference-QRD%202027-blue.svg)](https://github.com/Sparkydev007/qrd2027-adaptive-execution)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Clean](https://img.shields.io/badge/Code%20Style-Quant%20Research-green.svg)](https://github.com/Sparkydev007/qrd2027-adaptive-execution)

---

## 2. Important Disclaimer

**This repository contains academic quantitative execution research conducted for conference presentation at QRD 2027 (Conference on Quant, Risk & Data).**

- **Not an Investment Recommendation:** Nothing in this repository constitutes investment advice, financial promotion, or a recommendation to buy, sell, or hold any security, derivative, or financial instrument.
- **Not a Live Trading System or Alpha Strategy:** This project does not forecast asset returns, generate trading profits, or provide live trading execution connectivity.
- **Simulation-Based Findings:** All reported metrics reflect discrete-time, simulation-based limit-order-book experiments calibrated with historical 1-minute OHLCV data. The simulator does not replay Level-2/Level-3 order book feeds, real queue queues, or live exchange latency.

---

## 3. Executive Summary

Executing institutional parent orders in modern equity markets involves navigating non-stationary liquidity, stochastic volatility, and persistent market impact. In the National Stock Exchange of India (NSE), continuous trading follows a consolidated central limit order book structure characterized by sharp intraday volume smiles, wide spread dispersion across market regimes, and mandatory statutory transaction levies. Standard static execution schedules—such as Time-Weighted Average Price (TWAP) and historical Volume-Weighted Average Price (VWAP)—rely on deterministic participation paths that fail to adapt when liquidity evaporates or volatility spikes, frequently resulting in adverse selection and elevated implementation shortfall.

This study examines whether a liquidity-adaptive execution policy can reduce implementation shortfall and market impact relative to TWAP and VWAP under changing liquidity and volatility conditions in a limit-order-book simulation calibrated to Indian equity market data. The research constructs a transparent, event-driven, discrete-time simulation environment incorporating square-root temporary price impact, linear permanent impact with inter-interval persistence, queue-position approximations, and statutory transaction costs. The proposed rule-based liquidity-adaptive controller dynamically modulates aggression and maker-taker order routing conditioned on instantaneous spread width, top-of-book depth, order flow imbalance, and realized volatility regimes. Across parent order sizes of 0.5%, 1.0%, and 2.0% of Average Daily Volume, policy performance is benchmarked against TWAP, VWAP, Naive Aggressive execution, and Percentage-of-Volume (POV) schedules to quantify the trade-offs between execution shortfall, market impact, inventory variance, and completion risk.

---

## 4. Research Problem

Institutional asset managers and quantitative funds face substantial execution friction when liquidating or accumulating large equity positions. A large parent order cannot be executed instantaneously without inflicting prohibitive price concessions. Slicing the parent order into child orders over an extended execution horizon creates a classical dual-objective optimization problem:

1. **Market Impact:** Aggressive child orders consume visible liquidity and walk the book, incurring temporary price penalties and generating permanent adverse price displacement.
2. **Timing and Inventory Risk:** Prolonging execution to minimize instantaneous price impact exposes unexecuted shares to market drift, volatility spikes, and adverse selection.

Traditional execution algorithms deployed across sell-side desks frequently rely on static schedules. TWAP uniformly slices quantity across time, while VWAP tracks an empirical historical volume curve. Both approaches are structurally blind to real-time order-book conditions: they consume liquidity aggressively during market stress (when spreads are widest and depth is thinnest) and fail to accelerate participation during transient liquidity surges. 

Rigorous execution research requires measuring execution quality through **Implementation Shortfall**, **temporary and permanent market impact**, **completion risk**, **trajectory inventory variance**, and **transaction costs**—rather than treating trade execution as a frictionless afterthought or confusing execution efficiency with alpha generation.

---

## 5. Research Gap

Existing optimal execution literature (e.g., Bertsimas & Lo, 1998; Almgren & Chriss, 2000; Gatheral, 2010; Lehalle & Neuman, 2019) exhibits two prominent empirical limitations:

1. **Developed-Market Centricity:** The vast majority of published studies are calibrated to US or European equity markets, characterized by fragmented multi-venue routing, maker-taker exchange rebates, and sub-penny pricing regimes.
2. **Absence of Calibrated Indian Microstructure Studies:** The Indian equity market operates a single consolidated order book (NSE dominance), strict price-time priority without maker-taker subsidies, distinct retail-to-institutional volume concentrations, and mandatory statutory turnover levies (Securities Transaction Tax, stamp duty, exchange turnover fees, and GST). Most published domestic execution studies rely on coarse daily VWAP tracking errors without modeling microstructure-level book depth or regime transitions.

This project addresses this gap by building a transparent, reproducible, discrete-time limit-order-book simulation framework empirically calibrated to liquid National Stock Exchange of India (NSE) large-cap equities.

---

## 6. Research Question

> **Can a liquidity-adaptive execution policy reduce implementation shortfall and market impact relative to TWAP and VWAP under changing liquidity and volatility conditions in a limit-order-book simulation calibrated to Indian equity market data?**

---

## 7. Objectives

1. **Scaffold a Reproducible Research Pipeline:** Build an institutional-grade, configuration-driven Python framework adhering to modern scientific software engineering standards.
2. **Empirical Microstructure Calibration:** Calibrate Average Daily Volume (ADV), 30-minute intraday volume curves, rolling realized volatility distributions, and regime classification thresholds across liquid NIFTY 50 large caps.
3. **Formulate a Discrete-Time LOB Simulator:** Engineer a point-in-time order book environment modeling best bid/ask quotes, effective depth, queue-position approximations, and cancellation dynamics.
4. **Implement Classical Benchmarks:** Construct deterministic TWAP, profile-driven VWAP, liquidity-consuming Naive Aggressive, and volume-tracking Percentage-of-Volume (POV) policies.
5. **Develop a Rule-Based Adaptive Controller:** Engineer a transparent, non-black-box policy that modulates aggression, maker/taker placement, and slice sizing based on real-time spread, depth, volume imbalance, volatility, and completion urgency.
6. **Decompose Execution Costs:** Quantify execution performance across all 18 standard transaction cost analysis (TCA) metrics, including statutory Indian tax schedules.
7. **Prepare Academic Poster Assets:** Generate publication-quality vector charts and summary tables suitable for an A0 portrait academic poster presentation at QRD 2027.

---

## 8. Why This Matters to HFT and Quant Firms

- **Execution Desks & TCA Teams:** Execution drag (slippage, market impact, and statutory taxes) frequently erodes 30% to 70% of gross alpha in systematic strategies with high portfolio turnover. Quantifying policy shortfall under controlled market conditions provides direct operational savings.
- **Brokerage Algorithm Developers:** Modern institutional clients demand microstructure-aware execution algorithms that dynamically route passive maker limit orders when spreads are wide, switching to aggressive taker sweeps only when completion risk warrants.
- **Quantitative Portfolio Managers:** Portfolio optimization models require accurate transaction cost inputs. Calibrated execution profiles provide realistic post-cost capacity estimates for high-turnover equity factors.
- **Market Makers & Liquidity Providers:** Simulating how algorithmic child orders interact with top-of-book depth enhances the calibration of inventory hazard models and adverse selection parameters.
- **Risk & Compliance Officers:** Regulators (such as SEBI) increasingly require transparency and auditability in algorithmic execution. Transparent, rule-based policies provide explainable compliance trails that black-box machine-learning models cannot offer.

---

## 9. Methodology Overview

The research methodology follows a sequential, event-driven, discrete-time simulation workflow:

```
Historical 1-Minute OHLCV Data (NSE Equities)
   │
   ▼
[ 14-Point Data Integrity Audit Engine ]
   │ (Schema, price positivity, High >= Low, session boundary 09:15-15:29)
   ▼
[ Microstructure Calibration Framework ]
   │ (ADV, 30-min U-shaped volume smile, realized volatility percentiles)
   ▼
[ Regime Partitioning ]
   │ (Calm ≤ p40, Normal p40–p80, Stressed > p80; Liquidity Low/Med/High)
   ▼
[ Event-Driven Discrete-Time LOB Simulator ]
   │ ◄── Step t (0 to 374): Mid-price, Spread, Bid/Ask Depth, Imbalance
   ▼
[ Execution Policy Slicing Decisions ]
   │ (TWAP, VWAP, Naive Aggressive, POV, Liquidity-Adaptive)
   ▼
[ Fill Simulator & Queue Approximation Engine ]
   │ ├── Aggressive: Crosses spread, incurs square-root temporary impact
   │ └── Passive: Joins queue behind depth, stochastic fill via absorption
   ▼
[ Market Impact & Price Evolution Engine ]
   │ ├── Temporary Impact: Dissipates post-execution
   │ └── Permanent Impact: Accumulates persistently into mid-price
   ▼
[ Transaction Cost Accounting Engine ]
   │ (Brokerage, NSE Turnover Fees, SEBI Charges, GST, Stamp Duty, STT)
   ▼
[ 18-Metric TCA Evaluation & Benchmark Comparison ]
   │ (Implementation Shortfall, VWAP Slippage, Inventory Variance, Completion)
   ▼
[ Publication Outputs (Reports & 300 DPI A0 Poster Figures) ]
```

---

## 10. Data and Calibration

The framework utilizes historical 1-minute OHLCV data for liquid National Stock Exchange of India (NSE) large-cap equities (e.g., RELIANCE, HDFCBANK, TCS).

### Scope and Boundaries
- **Calibration Purpose Only:** 1-minute OHLCV bars are used strictly to calibrate statistical macro-parameters:
  - Rolling 20-day Average Daily Volume (ADV) and daily turnover in INR.
  - Empirical 30-minute intraday volume curves $\bar{v}_t$ (13 session buckets summing strictly to 1.0).
  - Rolling 20-period annualized realized volatility distributions.
  - Volatility regime boundaries (40th and 80th percentiles).
  - Liquidity regime boundaries (33.3rd and 66.7th percentiles).
- **Explicit Data Boundary:** Historical 1-minute OHLCV data is **not** tick-level order-book data. Intraday price discovery between 1-minute boundaries is modeled conditionally through the simulation engine rather than replaying historical Level-2/Level-3 market-depth messages.

---

## 11. Limit-Order-Book Simulation Design

The simulator operates as an event-driven, discrete-time state engine stepping across 375 continuous 1-minute intervals per trading session:

1. **State Space Tuple ($\mathcal{S}_t$):**
   $$\mathcal{S}_t = \left( P_t^{\text{mid}}, S_t, P_t^{\text{bid}}, P_t^{\text{ask}}, D_t^b, D_t^a, V_t, \sigma_t, \mathcal{I}_t^{\text{imb}}, \mathcal{R}_t^{\text{vol}}, \mathcal{R}_t^{\text{liq}} \right)$$
2. **Top-of-Book Pricing:**
   $$P_t^{\text{bid}} = P_t^{\text{mid}} - \frac{S_t}{2}, \quad P_t^{\text{ask}} = P_t^{\text{mid}} + \frac{S_t}{2}$$
   Spreads are rounded to the mandatory NSE tick size ($₹0.05$) and widen conditionally during stressed volatility regimes.
3. **Effective Queue Depth:** Visible depth on bid and ask sides is parameterized as an empirical volume multiple:
   $$D_t = 0.05 \times V_t$$
   Asymmetric depth is maintained conditioned on bar-level order flow imbalance $\mathcal{I}_t^{\text{imb}}$.
4. **Market-Order (Taker) Execution:** Aggressive slices cross the spread immediately, filling 100% of requested shares (up to the 20% interval participation cap) at:
   $$P_t^{\text{exec, agg}} = P_t^{\text{ask}} + \Delta P_t^{\text{temp}}$$
5. **Limit-Order (Maker) Execution:** Passive slices join the queue at $P_t^{\text{bid}}$. Fill probability is determined by queue depletion: incoming market sell volume ($\theta V_t$, $\theta = 0.40$) must absorb the visible queue depth ahead of our order before shares execute.
6. **Cancellation Dynamics:** Unfilled passive limit order balances are canceled at interval close to allow the execution controller to reprice and reallocate.
7. **Terminal Sweep:** A mandatory liquidity sweep executes any residual unexecuted shares at $t = 374$ to guarantee 100% parent order completion ($Q_T = 0$).

---

## 12. Execution Policies

The research engine benchmarks five distinct parent-order execution policies:

| Execution Policy | Formal Operational Rule | Research Purpose & Benchmark Role |
|---|---|---|
| **TWAP** | $q_t = \frac{Q_t}{T - t}$ | Deterministic time-slicing benchmark; uniform liquidity consumption. |
| **VWAP** | $q_t = Q_0 \cdot \bar{v}_t$ | Empirical volume-weighted benchmark; tracks historical intraday volume smile. |
| **Naive Aggressive** | $q_0 = Q_0$ (immediate sweep) | Maximum liquidity-consumption benchmark; quantifies worst-case market impact. |
| **Percentage-of-Volume (POV)** | $q_t = \min\left(Q_t, \rho \cdot V_t\right)$ | Liquidity-tracking benchmark; maintains fixed participation rate $\rho = 10\%$. |
| **Liquidity-Adaptive (Proposed)** | $q_t = f(Q_t, t, S_t, D_t, \mathcal{I}_t^{\text{imb}}, \sigma_t, \mathcal{R}_t)$ | Proposed policy; dynamically modulates maker/taker urgency based on real-time microstructure state. |

### Proposed Liquidity-Adaptive Policy Formulation
The adaptive controller is transparent and rule-based (zero black-box machine learning):
- **Urgency Tracking:** Computes normalized completion urgency:
  $$\mathcal{U}_t = \frac{Q_t / Q_0}{\max(1, T - t) / T}$$
- **Volatility Throttling:** Throttles slice sizes by $25\%$ during stressed volatility regimes ($\sigma_t > p80$) to avoid walking wide books, and accelerates by $25\%$ during calm regimes.
- **Spread Sensitivity:** Measures real-time spread ratio $S_t / \bar{S}$. When spreads widen, aggression is suppressed.
- **Dynamic Maker/Taker Routing:** Routes orders **passively** (maker limit order at best bid) when time remaining is ample ($T - t > 10$), urgency is moderate ($\mathcal{U}_t \le 1.25$), and spreads are wide, capturing the half-spread. Switches to **aggressive** spread crossing when completion risk rises or time expires.

---

## 13. Market-Impact Model

Price impact is separated into temporary and permanent components following Almgren & Chriss (2000) and Bouchaud et al. (2009):

### 1. Temporary Price Impact (Liquidity Consumption Penalty)
Instantaneous price concession incurred by child orders crossing the book, modeled via the empirical square-root law:
$$\Delta P_t^{\text{temp}} = \eta \cdot \sigma_t \cdot \left(\frac{q_t^{\text{agg}}}{V_t}\right)^\alpha \cdot P_t^{\text{mid}}$$
where $\alpha = 0.50$ (square-root exponent) and $\eta = 0.50$ (calibrated simulation assumption). Temporary impact dissipates immediately after trade execution.

### 2. Permanent Price Impact (Information Disruption)
Persistent shift in equilibrium mid-price caused by cumulative order flow:
$$\Delta P_t^{\text{perm}} = \gamma \cdot \sigma_t \cdot \left(\frac{q_t^{\text{total}}}{V_t}\right) \cdot P_t^{\text{mid}}$$
where $\gamma = 0.10$ (permanent fraction assumption). 

### 3. Inter-Interval Persistence
Permanent impact accumulates into the simulated mid-price across intervals:
$$P_{t+1}^{\text{mid}} = P_t^{\text{mid}} + \Delta P_t^{\text{perm}} + \epsilon_{t+1}$$
ensuring that aggressive front-loading penalizes all subsequent child executions.

---

## 14. Transaction-Cost Model

The framework models the institutional statutory cash equity transaction schedule applicable to Indian equity markets (NSE). All cost rates are configurable illustrative simulation assumptions:

| Statutory Component | Buy-Side Intraday Rate | Sell-Side Intraday Rate | Delivery Benchmark |
|---|---|---|---|
| **Brokerage Fee** | $1.5000\text{ bps}$ | $1.5000\text{ bps}$ | $1.5000\text{ bps}$ |
| **Exchange Turnover Charges (NSE Cash)** | $0.3250\text{ bps}$ | $0.3250\text{ bps}$ | $0.3250\text{ bps}$ |
| **SEBI Turnover Charges** | $0.0100\text{ bps}$ | $0.0100\text{ bps}$ | $0.0100\text{ bps}$ |
| **GST (18% on Brokerage + Exchange + SEBI)** | $0.3303\text{ bps}$ | $0.3303\text{ bps}$ | $0.3303\text{ bps}$ |
| **Stamp Duty (Statutory Buy-Side)** | $\mathbf{0.3000\text{ bps}}$ ($0.003\%$) | $0.0000\text{ bps}$ | $1.5000\text{ bps}$ ($0.015\%$) |
| **Securities Transaction Tax (STT)** | $0.0000\text{ bps}$ | $\mathbf{2.5000\text{ bps}}$ ($0.025\%$) | $10.0000\text{ bps}$ ($0.100\%$) |
| **Total Programmatic Cost** | $\mathbf{2.4653\text{ bps}}$ | $\mathbf{4.6653\text{ bps}}$ | $\mathbf{13.6653\text{ bps}}$ |

For parent buy orders, the applicable statutory transaction cost charged against traded turnover is strictly the programmatic buy-side rate: **2.4653 bps**.

---

## 15. Evaluation Metrics

Execution quality is evaluated across 18 standardized transaction cost analysis (TCA) metrics:

1. **Arrival Price ($P_0$):** Prevailing mid-price at decision inception $t = 0$.
2. **Interval VWAP ($P_{\text{VWAP}}$):** Volume-weighted average market price across the execution window.
3. **Implementation Shortfall (IS):** Total execution drag relative to arrival decision price:
   $$\text{IS}_{\text{bps}} = \frac{\sum_{t=0}^{T-1} q_t P_t^{\text{exec}} - Q_0 P_0}{Q_0 P_0} \times 10{,}000$$
4. **Slippage vs. Arrival Price:** Basis point difference between volume-weighted execution price $\bar{P}$ and $P_0$.
5. **Slippage vs. Interval VWAP:** Basis point difference between $\bar{P}$ and $P_{\text{VWAP}}$.
6. **Temporary Market Impact:** Total rupees and basis point drag incurred from liquidity consumption.
7. **Permanent Market Impact:** Terminal basis point shift in equilibrium mid-price attributable to order flow.
8. **Average Spread Paid:** Volume-weighted half-spread incurred across executions (negative for maker fills).
9. **Fill Rate:** Percentage of total parent order shares executed ($\sum q_t / Q_0 \times 100\%$).
10. **Turnover:** Gross rupee value executed ($\sum q_t P_t^{\text{exec}}$).
11. **Mean Inventory:** Time-weighted average unexecuted inventory $\frac{1}{T}\sum Q_t$.
12. **Inventory Variance ($\sigma_Q^2$):** Mean squared divergence against ideal linear liquidation path:
    $$\sigma_Q^2 = \frac{1}{T}\sum_{t=0}^{T-1}\left(Q_t - Q_0(1 - t/T)\right)^2$$
13. **Maximum Inventory:** Peak inventory exposure committed to execution ($Q_0$).
14. **Execution Completion Rate:** Binary indicator verifying zero terminal inventory ($\mathbb{I}(Q_T = 0)$).
15. **Participation Rate:** Volume share of algorithm relative to market volume ($\sum q_t / \sum V_t \times 100\%$).
16. **Net Execution Cost:** Implementation Shortfall plus statutory transaction costs.
17. **Performance by Volatility Regime:** Stratified shortfall across Calm ($\le p40$), Normal ($p40-p80$), and Stressed ($> p80$) regimes.
18. **Performance by Liquidity Regime:** Stratified shortfall across Low ($\le p33$), Medium ($p33-p67$), and High ($> p67$) liquidity buckets.

---

## 16. Repository Structure

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
│   ├── test_calibration.py
│   └── test_simulator.py
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

---

## 17. Installation

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Git

### Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/Sparkydev007/qrd2027-adaptive-execution.git
cd qrd2027-adaptive-execution

# 2. Create a clean virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# 3. Upgrade pip and install pinned research dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Verify test suite execution
pytest -v tests/
```

---

## 18. Configuration

All empirical parameters, market conventions, universe selections, and simulation assumptions are managed centrally through [config/config.yaml](file:///c:/Users/Prathmesh%20Bunde/qrd2027_adaptive_execution/config/config.yaml). No magic numbers or hardcoded parameters exist in source code modules.

Key configurable parameter groups:
1. **Data Ingestion:** Data provider source (`upstox`, `angelone`, `csv`), 1-minute frequency, Asia/Kolkata timezone.
2. **Session Definition:** Continuous trading window (`09:15` to `15:29` IST, exactly 375 minutes).
3. **Asset Universe:** Constituents (`RELIANCE`, `HDFCBANK`, `TCS`, `ICICIBANK`, `INFY`, etc.), minimum history filter (120 days), minimum ADV ($100{,}000$ shares).
4. **Calibration Window:** Rolling volatility window (20 minutes), intraday volume profile buckets (13 buckets).
5. **Simulation Assumptions:**
   - Baseline spread assumption (5.0 bps fixed or dynamic volatility-scaled).
   - Visible depth multiplier assumption (0.05 volume multiple).
   - Temporary impact exponent (0.50) and coefficient $\eta$ (0.50).
   - Permanent impact fraction $\gamma$ (0.10).
6. **Transaction Costs:** Configurable itemized rates for brokerage, NSE exchange fees, SEBI charges, GST rate, buy-side stamp duty, and sell-side STT.
7. **Execution Mandates:** Parent order sizes ($0.005$, $0.010$, $0.020$ of ADV), horizon ($375$ minutes), maximum participation cap ($20\%$).
8. **Reproducibility:** Pinned random seed (`42`), number of paths ($100$).
9. **Regimes:** Percentile boundaries for calm ($\le 40\%$), normal ($40\%-80\%$), and stressed ($> 80\%$) volatility states.

---

## 19. How to Run

### 1. Run the Complete Automated Test Suite
```bash
pytest -v tests/
```

### 2. Execute the Data Audit Pipeline
Run the 14-point microstructure validation engine on raw market data:
```bash
python -c "from src.data_audit import run_audit_pipeline; run_audit_pipeline('data/raw/sample_RELIANCE_1min.csv')"
```

### 3. Run Microstructure Calibration
Calibrate empirical ADV, volume profiles, and volatility distributions:
```bash
python -c "from src.calibration import run_calibration_pipeline; run_calibration_pipeline('data/processed/RELIANCE_1min.parquet', ticker='RELIANCE')"
```

### 4. Execute the Multi-Stock Simulation Study
Run the complete execution simulation across all 5 policies and 3 parent order sizes:
```bash
python -m src.run_simulation
```
Outputs are written to `reports/tables/simulation_results.csv` and figures to `reports/figures/`.

### 5. Open Interactive Research Notebooks
```bash
jupyter lab
```
Navigate to:
- `notebooks/01_data_audit.ipynb` — Interactive 14-point data audit and regime distributions.
- `notebooks/02_calibration.ipynb` — Multi-stock empirical volume smiles and volatility calibration.
- `notebooks/03_simulation_results.ipynb` — Policy shortfall comparison, TCA breakdown, and statistical checks.

---

## 20. Reproducibility

To guarantee scientific reproducibility across independent computing environments, this project adheres to strict deterministic protocols:

1. **Fixed Random Seeds:** NumPy random number generators are explicitly seeded (`random_seed: 42`) in configuration and passed through all stochastic components.
2. **Configuration-Driven Parameters:** No parameter values are embedded inside procedural logic.
3. **Deterministic Preprocessing:** Timestamps are sorted monotonically, regularized across 375 minutes, and localized to `Asia/Kolkata` with zero forward-looking data leakage.
4. **Exported Structured Audit Trails:** Calibration outputs and audit results are serialized as version-controlled JSON artifacts in `reports/tables/`.

*Note: Exact numerical reproduction requires the identical input dataset, Python package versions specified in `requirements.txt`, and configuration file settings.*

---

## 21. Testing

The repository maintains an automated test suite with **36 unit tests** covering all pipeline layers:

- **Data Ingestion (`tests/test_data_loader.py`):** Schema validation, timestamp parsing, deduplication, market-hours filtering (09:15–15:29), log returns, realized volatility non-negativity, and Parquet serialization.
- **Microstructure Audit (`tests/test_data_audit.py`):** Corrupt price detection, negative volume flagging, High < Low violations, Open/Close range violations, extreme returns, and session gap detection.
- **Calibration Engine (`tests/test_calibration.py`):** ADV estimation, volume profile normalization ($\sum \bar{v}_t = 1.0$), volatility percentile monotonicity, and programmatic verification that reported total transaction costs strictly equal the sum of itemized components.
- **Simulator & Policy Suite (`tests/test_simulator.py`):** Terminal order completion ($Q_T = 0$) for TWAP, VWAP, Naive Aggressive, and Adaptive policies; participation constraint enforcement; impact monotonicity; permanent impact persistence; and bit-level seed reproducibility.

---

## 22. Current Status

**Current Milestone:** Day 1 Foundation and Day 2 Simulator Core Complete.

### Completed Components
- [x] Complete project scaffold, configuration loader, and documentation suite.
- [x] 14-point automated microstructure data-audit engine.
- [x] Data ingestion pipeline with exact 375-minute continuous horizon regularization.
- [x] Multi-stock empirical calibration framework (ADV, volume smiles, volatility distributions).
- [x] Discrete-time limit-order-book simulation engine with queue-position approximations.
- [x] Five execution policies implemented (TWAP, VWAP, Naive Aggressive, POV, Liquidity-Adaptive).
- [x] Almgren-Chriss market impact engine (square-root temporary, linear permanent with inter-interval persistence).
- [x] Buy-side intraday programmatic transaction cost schedule ($2.4653\text{ bps}$).
- [x] 36 unit tests passing across all pipeline modules.
- [x] Three interactive Jupyter research notebooks executed and verified.
- [x] Initial benchmark comparison results and 4 publication figures generated at 300 DPI.

### In Progress
- [ ] Multi-day Monte Carlo path expansion across 100 paths per regime.
- [ ] Formal statistical hypothesis testing ($H_1$ to $H_4$ paired tests and Wilcoxon signed-rank tests).
- [ ] Cross-asset beta sensitivity analysis across the broader NIFTY 50 universe.

---

## 23. Roadmap

- **Day 3: Robustness Analysis & Queue Hazard Rates**
  - Parameterize adverse selection hazard rates for passive queue placements during volatility spikes.
  - Run multi-day stochastic drift scenarios and evaluate fill degradation.
  - Refine execution-policy parameter sensitivity across participation limits (10% to 30%).
- **Day 4: Multi-Stock Expansion & Statistical Hypothesis Testing**
  - Run batch empirical calibration across 10 NIFTY 50 stocks.
  - Conduct formal statistical hypothesis testing ($H_1$–$H_4$) with paired t-tests and bootstrap confidence intervals.
  - Finalize empirical comparison tables.
- **Day 5: Academic Abstract & Poster Panel Layout**
  - Draft formal 350–500 word conference abstract adhering to QRD 2027 guidelines.
  - Architect the visual panel layout for the A0 portrait poster (841 mm $\times$ 1189 mm).
- **Day 6: Reviewer-Style Audit & Repository Polish**
  - Conduct independent code audit for lookahead bias, numerical precision, and documentation accuracy.
  - Polish figures, LaTeX tables, and reproducible reproduction scripts.
- **Day 7: Final Submission Preparation**
  - Finalize camera-ready poster assets, working paper preprint, and release tag.

---

## 24. Limitations

1. **Granularity Limitation:** The study calibrates macro-state dynamics using 1-minute OHLCV data, not tick-by-tick order-book message feeds.
2. **Order-Book Simplification:** The simulator does not replay historical Level-2/Level-3 market depth. Top-of-book depth is simulated via calibrated volume multiples.
3. **Queue Modeling:** Queue position, exchange latency, and matching-engine order race conditions are approximated rather than directly measured from exchange matching logs.
4. **Market-Impact Parameterization:** Impact coefficients ($\eta = 0.50$, $\gamma = 0.10$) represent theoretical simulation assumptions based on institutional literature, not parameters fitted to proprietary execution logs.
5. **Illustrative Transaction Costs:** Statutory taxes and brokerage fees reflect standardized schedules and may vary across institutional broker tiering and clearing agreements.
6. **No Alpha or Profitability Claims:** Results quantify relative execution drag (basis points saved); they do not establish live-market trading profitability or generate speculative alpha.
7. **Calibration Sample Scope:** The baseline calibration sample covers liquid large-cap constituents; findings may not extrapolate directly to illiquid small-cap equities.
8. **Rule-Based Adaptive Controller:** The adaptive policy is structured around transparent economic heuristic rules rather than dynamic reinforcement-learning optimization.

---

## 25. Research Integrity and AI Use

Generative AI tools were used to assist with code drafting, documentation formatting, test generation, and visual layout. All research design formulations, hypothesis definitions, data audit validation, mathematical specifications, interpretation of empirical results, and final responsibility remain strictly with the human researcher.

No fabricated market data, synthetic price paths disguised as live data, fraudulent citations, or unverified market parameters are used in this study.

---

## 26. License

This project is licensed under the terms of the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 27. Author

**Prathmesh Bunde**  
Quantitative Finance Researcher  
Pimpri, Maharashtra, India  
*Specialization: Market Microstructure, Algorithmic Execution, and Empirical Asset Pricing*  
*Conference Submission: QRD 2027 — Conference on Quant, Risk & Data*
