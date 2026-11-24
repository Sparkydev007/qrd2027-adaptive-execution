# Research Design Document: Liquidity-Adaptive Optimal Execution in Indian Equities

**Project:** QRD 2027 Conference Presentation  
**Document ID:** DOC-RD-01  
**Version:** 1.0.0  

---

## 1. Research Problem
Large institutional equity orders face substantial execution costs when entering modern electronic financial markets. Slicing a large parent order into smaller child orders over time introduces a fundamental trade-off between **market impact** (cost incurred by aggressively consuming liquidity and pushing market prices adversely) and **market risk / inventory risk** (cost and variance incurred by holding unexecuted shares while market prices drift).

In emerging market microstructure such as the National Stock Exchange of India (NSE), liquidity is non-stationary, exhibiting extreme intraday volume smile patterns, wide spread widening during volatility spikes, and high transaction tax burdens (Securities Transaction Tax). Institutional execution desks frequently rely on static schedules (TWAP or historical VWAP) that are blind to real-time order-book liquidity shifts.

## 2. Research Gap
While optimal execution models originating from Almgren & Chriss (2000), Bertsimas & Lo (1998), and Gatheral (2010) are mathematically well-studied, existing literature exhibits two critical deficiencies:
1. **US/EU Market Centricity:** The vast majority of published studies calibrate models to US equity markets (characterized by fragmented exchanges, maker-taker rebates, and sub-penny pricing) or liquid European bourses.
2. **Absence of Indian Market Calibration:** The Indian equity market features a single consolidated order book (NSE dominance), no maker-taker rebate subsidization, explicit statutory levies on trade value, and distinct order size clustering. No standardized open benchmark evaluates adaptive execution policies under empirically calibrated Indian microstructure dynamics.

## 3. Research Question
> **Can a liquidity-adaptive execution policy reduce implementation shortfall and market impact relative to TWAP and VWAP under changing liquidity and volatility conditions in a limit-order-book simulation calibrated to Indian equity market data?**

## 4. Primary Hypothesis
- **$H_1$ (Primary):** A liquidity-adaptive execution policy that modulates passive-versus-aggressive order participation conditioned on real-time spread, book depth, and local volatility achieves a statistically significant reduction in implementation shortfall ($p < 0.01$) compared to static TWAP and VWAP policies for parent orders of size $0.5\%$, $1.0\%$, and $2.0\%$ of Average Daily Volume (ADV).

## 5. Secondary Hypotheses
- **$H_2$ (Impact Reduction):** The adaptive policy reduces temporary market impact during stressed volatility regimes by throttling execution during liquidity voids and accelerating passive fills during liquidity surges.
- **$H_3$ (Variance & Inventory):** While static policies maintain deterministic inventory trajectories, the adaptive policy maintains acceptable inventory variance while capping terminal unexecuted shares to zero.
- **$H_4$ (Regime Sensitivity):** The economic benefit (basis points saved) of the adaptive policy increases monotonically as market conditions transition from calm to stressed regimes.

## 6. Data and Calibration Plan
- **Calibration Frequency:** 1-minute historical OHLCV bars over 120+ trading days (calendar year 2024).
- **Timezone:** Asia/Kolkata (IST).
- **Session Hours:** 09:15 to 15:30 IST (375 trading minutes).
- **Calibration Outputs:**
  1. Intraday volume distribution function $\bar{v}_t = \mathbb{E}[V_t / V_{\text{day}}]$ across 13 30-minute intervals and 1-minute buckets.
  2. Intraday realized volatility curve $\bar{\sigma}_t$.
  3. Rolling volatility distribution percentiles (40th and 80th percentiles for regime partition).
  4. Average bid-ask spread parameter $\bar{S}$ and depth multiplier $D$.
  5. Temporary impact coefficient $\eta$ and permanent impact fraction $\gamma$.

## 7. Simulator Assumptions
1. **Point-in-Time Discrete Simulation:** The simulation steps at discrete 1-minute intervals matching empirical calibration intervals.
2. **Order Book Representation:** At each interval $t$, the simulator establishes mid-price $P_t$, best bid $P_t^b = P_t - S_t/2$, best ask $P_t^a = P_t + S_t/2$, and effective queue depth $Q_t^d$.
3. **Price Evolution:** Mid-price follows an arithmetic random walk augmented with drift, permanent market impact, and volatility:
   $$P_{t+1} = P_t + \sigma_t \sqrt{\Delta t}\,\epsilon_t + \Delta P_t^{\text{perm}}$$
   where $\epsilon_t \sim \mathcal{N}(0, 1)$.
4. **No Tick-Level Fabrication:** The simulator does not claim to reconstruct exact L3 queue positions; queue execution probabilities for passive limit orders are modeled via a calibrated Poisson/Bernoulli arrival probability decaying with queue depth.

## 8. Parent-Order Specification
- **Order Side:** Buy (symmetric to Sell under zero-drift benchmark).
- **Order Size ($Q_0$):** Calibrated as a percentage of Average Daily Volume (ADV):
  - Tier 1: $0.005 \times \text{ADV}$ (50 bps of daily volume - small institutional slice)
  - Tier 2: $0.010 \times \text{ADV}$ (100 bps of daily volume - moderate institutional order)
  - Tier 3: $0.020 \times \text{ADV}$ (200 bps of daily volume - large institutional block)
- **Execution Horizon ($T$):** 375 minutes (full trading day, 09:15 to 15:30 IST) or sub-session intervals (e.g., 60, 120 minutes).
- **Terminal Completion Constraint:** $Q_T = 0$ (all shares must be executed by horizon end).

## 9. Execution Policies
1. **TWAP (Time-Weighted Average Price):**
   $$q_t^{\text{TWAP}} = \frac{Q_0}{N}$$
   Uniform slicing across all $N$ time intervals.
2. **VWAP (Volume-Weighted Average Price):**
   $$q_t^{\text{VWAP}} = Q_0 \cdot \bar{v}_t$$
   Slicing proportional to historical expected volume fraction $\bar{v}_t$.
3. **Naive Aggressive:**
   $$q_1 = Q_0$$
   Executes 100% of parent order immediately at $t=1$ via market orders.
4. **Percentage of Volume (POV):**
   $$q_t^{\text{POV}} = \min\left(Q_t, \rho \cdot V_t\right)$$
   Maintains target participation rate $\rho$ (e.g., 10%) of interval volume.
5. **Adaptive Execution Policy (Proposed):**
   Rule-based policy computing dynamic order rate $q_t^*$:
   $$q_t^* = q_t^{\text{VWAP}} \times f(\text{Spread}_t) \times g(\text{Depth}_t) \times h(\text{Vol}_t) \times \psi(\text{Urgency}_t)$$
   subject to:
   - Maximum participation rate cap $q_t \le 0.20 \times V_t$.
   - Passive queue preference when spread $S_t \ge \bar{S}$.
   - Aggressive market sweep when remaining time is critical ($t \to T$).

## 10. Market-Impact Model
Following Almgren-Chriss (2000) and Bouchaud et al. (2009):
- **Temporary Impact (Cost per child slice):**
  $$\Delta P_t^{\text{temp}} = \eta \cdot \sigma_t \cdot \left(\frac{q_t}{V_t}\right)^\alpha$$
  where $\alpha = 0.5$ (the classical empirical square-root law).
- **Permanent Impact (Persistent shift in mid-price):**
  $$\Delta P_t^{\text{perm}} = \gamma \cdot \sigma_t \cdot \frac{q_t}{V_t}$$
  where $\gamma$ is the permanent price impact coefficient.

## 11. Transaction-Cost Model
Reflects Indian statutory cash equity institutional schedule:
- **Brokerage / Execution fee:** 1.5 bps
- **Securities Transaction Tax (STT):** 10 bps on delivery buy/sell; 2.5 bps intraday.
- **Exchange Turnover Charges (NSE):** 0.325 bps
- **SEBI Turnover Charges:** 0.01 bps
- **Stamp Duty:** 1.5 bps on buy delivery.
- **Goods and Services Tax (GST):** 18% on (brokerage + exchange charges + SEBI charges).
- **Configurable Standard Model:** Flat 5.0 bps baseline plus exact tax breakdown.

## 12. Evaluation Metrics
1. Implementation Shortfall (IS) in basis points:
   $$\text{IS} = \frac{\sum_{t=1}^N q_t P_t^{\text{exec}} - Q_0 P_0}{Q_0 P_0} \times 10{,}000$$
2. Slippage vs. Arrival Price ($P_0$).
3. Slippage vs. Interval VWAP ($P_{\text{VWAP}}$).
4. Temporary & Permanent Impact fractions.
5. Average realized spread paid.
6. Passive fill fraction versus aggressive fill fraction.
7. Trajectory inventory variance $\frac{1}{N}\sum_{t=1}^N (Q_t - Q_t^{\text{ideal}})^2$.
8. Completion rate $\frac{\sum q_t}{Q_0}$.

## 13. Out-of-Sample Validation Plan
- **Temporal Split:** Calibrate parameters on Q1–Q3 2024 (January–September 2024); evaluate simulations out-of-sample on Q4 2024 (October–December 2024).
- **Cross-Stock Validation:** Calibrate on 5 high-beta stocks and test on 5 lower-volatility stocks to test parameter transferability.

## 14. Robustness Checks
1. **Participation Limit Scenarios:** Vary max participation cap from 10% to 30%.
2. **Impact Parameter Perturbation:** Perturb $\eta$ and $\gamma$ by $\pm 25\%$ and $\pm 50\%$.
3. **Execution Window Variations:** Test full-day (375 min), morning session (120 min), and closing session (60 min).
4. **Monte Carlo Path Diversity:** 100 paths per regime with varied random seeds.

## 15. Limitations
- Does not utilize proprietary Level-3 tick matching logs.
- Assumes stationary intra-minute price discovery between 1-minute bars.
- Does not model latency competition among HFT market makers.
- Excludes dark pool mechanisms (which have limited regulatory scope in India).

## 16. Practical Implications
Provides institutional buy-side execution desks, quantitative asset managers, and algorithmic brokers in India with:
1. An empirical baseline demonstrating the cost penalty of naive TWAP under Indian volume volatility smile.
2. A quantifiable decision matrix showing when adaptive passive placement justifies queue-risk exposure.
3. A transparent, non-black-box execution strategy ready for regulatory audit under SEBI algorithmic trading guidelines.
