# Simulator Scope & Architectural Specification

**Project:** QRD 2027 Conference Presentation  
**Document ID:** DOC-SS-01  
**Version:** 1.0.0  

---

## 1. Simulation Objective
The simulator provides a controlled, reproducible, point-in-time microstructural environment to evaluate parent-order execution policies on Indian equities. It quantifies execution costs, market impact, and trajectory risk under distinct liquidity and volatility regimes without lookahead bias or unrealistic fill assumptions.

## 2. Asset Universe
- **Target Stocks:** Top 10 constituents of NIFTY 50 by traded value:
  `['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'SBIN', 'AXISBANK', 'KOTAKBANK', 'LT', 'ITC']`
- **Selection Criteria:** Minimum 120 consecutive trading days, minimum Average Daily Volume $\ge 100{,}000$ shares, average daily turnover $\ge 50$ Crore INR.
- **Survivorship Control:** Stocks fixed as of the 2024 index composition baseline.

## 3. Time Granularity
- **Base Resolution:** 1-minute discrete simulation steps ($t = 1, 2, \dots, 375$).
- **Sub-Minute Discretization:** For order placement and cancellation dynamics, child slices operate at 1-minute decision boundaries.

## 4. Trading Session Definition & 375-Minute Horizon
- **Exchange:** National Stock Exchange of India (NSE).
- **Continuous Trading Hours:** 09:15:00 IST to 15:29:59 IST.
- **Session Duration:** Exactly 375 discrete 1-minute execution intervals ($t = 0, 1, \dots, 374$).
- **Boundary Candle Exclusion:** The 15:30:00 timestamp candle marks the boundary close of continuous trading and the commencement of the closing auction (15:30–16:00 IST). It is strictly excluded from continuous parent-order execution intervals.
- **Session Exclusions:** Pre-open discovery auction (09:00–09:15 IST) and closing price calculation auction (15:30–16:00 IST) are outside the continuous execution horizon.

## 5. Parent-Order Specification
- **Direction:** Buy (programmable for Sell; symmetry verified).
- **Sizes:** Parameterized as fraction of empirical 20-day ADV:
  - 0.5% ADV (Low participation load)
  - 1.0% ADV (Medium participation load)
  - 2.0% ADV (High participation load)
- **Start Time:** Session open ($t = 0$ / 09:15 IST) or configurable intraday arrival $t_0$.
- **End Time:** Horizon $T = 375$ or configurable sub-interval.

## 6. Order Types
1. **Aggressive (Market / Taker):** Immediately crosses the prevailing best quote; guaranteed execution at $P_t^{\text{ask}} + \Delta P_t^{\text{temp}}$, incurring full spread and temporary price impact.
2. **Passive (Limit / Maker):** Placed at best bid $P_t^{\text{bid}}$ or within spread; subject to queue execution probability and cancellation dynamics.

## 7. Limit-Order-Book State Variables
At each simulation minute $t$, the order book state is defined by the tuple:
$$\mathcal{S}_t = \left( P_t^{\text{mid}}, S_t, D_t^b, D_t^a, V_t, \sigma_t, \mathcal{R}_t^{\text{vol}}, \mathcal{R}_t^{\text{liq}} \right)$$
where:
- $P_t^{\text{mid}}$: Prevailing mid-price.
- $S_t$: Calibrated instantaneous bid-ask spread.
- $D_t^b, D_t^a$: Calibrated visible depth on bid and ask sides.
- $V_t$: Interval market volume.
- $\sigma_t$: Instantaneous rolling realized volatility.
- $\mathcal{R}_t^{\text{vol}}$: Volatility regime (calm, normal, stressed).
- $\mathcal{R}_t^{\text{liq}}$: Liquidity regime (high, medium, low).

## 8. Order-Arrival Process
Market background volume $V_t$ is calibrated from empirical historical volume distributions:
$$V_t = \bar{V} \cdot \bar{v}_t \cdot \exp\left( \xi_t - \frac{\sigma_\xi^2}{2} \right)$$
where $\bar{v}_t$ is the deterministic intraday volume profile and $\xi_t \sim \mathcal{N}(0, \sigma_\xi^2)$ captures idiosyncratic volume bursts.

## 9. Cancellation Process
For passive child orders placed in the queue, cancellation occurs:
1. Endogenous: The execution policy cancels unfilled orders at the end of the 1-minute bucket to reprice.
2. Exogenous (Adverse Selection): If mid-price drifts away from the limit price, the fill probability decays exponentially.

## 10. Fill Logic
- **Aggressive Slices ($q_t^{\text{agg}}$):**
  $$P_t^{\text{exec, agg}} = P_t^{\text{mid}} + \frac{S_t}{2} + \eta \sigma_t \left(\frac{q_t^{\text{agg}}}{V_t}\right)^{0.5}$$
  Fill rate is 100% up to maximum participation constraints.
- **Passive Slices ($q_t^{\text{pas}}$):**
  Executed at $P_t^{\text{exec, pas}} = P_t^{\text{mid}} - \frac{S_t}{2}$ (or mid).
  Fill probability $\pi_t$ is governed by ratio of interval market volume to depth:
  $$\pi_t = \min\left(1.0, \frac{V_t \cdot \theta}{D_t^a + q_t^{\text{pas}}}\right)$$
  where $\theta$ is the turnover-depth absorption parameter.

## 11. Queue-Position Assumptions
- The simulator does not claim exact L3 queue tracking.
- Passive orders are modeled as joining the queue at the end of the prevailing visible depth $D_t$.
- Fill probability is strictly non-lookahead, conditioned solely on interval volume and depth available at placement.

## 12. Spread Simulation Assumption
Instantaneous spread $S_t$ is a parameterized simulation assumption modeled as a function of baseline tick size, price level, and local volatility (not directly extracted from Level-2 tick feeds):
$$S_t = \max\left( \delta_{\text{tick}},\, P_t \times \left( \bar{s}_{\text{bps}} \times 10^{-4} \right) \times \left( \frac{\sigma_t}{\bar{\sigma}} \right)^{\beta_s} \right)$$
where default baseline $\bar{s}_{\text{bps}} = 5.0$ bps and $\beta_s = 0.5$.

## 13. Depth Simulation Assumption
Instantaneous book depth $D_t$ at best quotes is a simulation assumption parameterized as an empirical volume multiple:
$$D_t = \lambda_d \cdot V_t$$
where default multiplier $\lambda_d = 0.05$ (5% of interval volume visible at top-of-book).

## 14. Temporary-Impact Simulation Assumption
Temporary price impact is modeled using the classical Almgren-Chriss square-root simulation assumption:
$$\Delta P_t^{\text{temp}} = \eta \cdot \sigma_t \cdot \left(\frac{q_t}{V_t}\right)^{0.5}$$
Calibrated default assumption $\eta = 0.50$, $\alpha = 0.50$.

## 15. Permanent-Impact Simulation Assumption
Permanent price impact is modeled using a linear simulation assumption with cumulative persistence:
$$\Delta P_t^{\text{perm}} = \gamma \cdot \sigma_t \cdot \left(\frac{q_t}{V_t}\right)$$
Calibrated default assumption fraction $\gamma = 0.10$.

## 16. Inventory Constraints
- Initial inventory: $Q_0 = \text{Target Volume}$.
- Inventory state: $Q_t = Q_{t-1} - q_{t-1}$.
- Terminal constraint: $Q_T = 0$. If $Q_T > 0$ at $t = T$, a mandatory liquidity sweep executes the remaining balance at penalizing market prices.
- Short sales: Disallowed ($\text{allow\_short} = \text{false}$), so $Q_t \ge 0 \quad \forall t$.

## 17. Participation-Rate Constraint
To prevent unrealistic market absorption:
$$q_t \le \rho_{\max} \cdot V_t$$
where $\rho_{\max} = 0.20$ (20% of interval volume).

## 18. Transaction-Cost Model & Programmatic Schedule
Standard Indian cash equity statutory schedule with programmatically calculated itemized components:
- **Brokerage fee:** 1.500 bps
- **Exchange turnover charges (NSE Cash):** 0.325 bps
- **SEBI turnover charges:** 0.010 bps
- **Goods and Services Tax (GST, 18% on brokerage + exchange + SEBI):** $0.18 \times (1.50 + 0.325 + 0.01) = 0.3303$ bps
- **Stamp duty (buy delivery):** 1.500 bps
- **Securities Transaction Tax (STT):** 2.500 bps
- **Total Programmatic Itemized Cost:**
  $$\text{Total}_{\text{itemized}} = 1.50 + 0.325 + 0.01 + 0.3303 + 1.50 + 2.50 = 6.1653\text{ bps}$$
- **Configurable Standard Model:** Flat 5.0 bps baseline comparison parameter.

## 19. Regime Definitions
Regimes are classified via historical rolling 20-day realized volatility percentiles:
- **Calm Regime:** Realized Volatility $\le 40\text{th}$ percentile.
- **Normal Regime:** $40\text{th} < \text{Realized Volatility} \le 80\text{th}$ percentile.
- **Stressed Regime:** Realized Volatility $> 80\text{th}$ percentile.

## 20. Random-Seed and Reproducibility Rules
- Seed is locked in `config/config.yaml` (`random_seed: 42`).
- Monte Carlo simulations generate identical paths across consecutive runs.
- All random number generators utilize NumPy `default_rng(seed)`.

---

### Explicit Scope Declarations
1. **Calibration vs. Execution:** 1-minute historical OHLCV data is used exclusively to calibrate statistical parameters (ADV, volume curves, volatility distributions). It is NOT tick data.
2. **No L2 Order Book Claim:** The simulator does not simulate full depth-of-book levels (L2/L3). It simulates top-of-book effective depth and spreads.
3. **No Latency Claim:** Network colocation latency and exchange queue racing are outside scope.
4. **No Live-Trading Alpha:** The simulator measures execution drag and policy shortfall; it does not forecast stock price trends or claim trading profitability.
