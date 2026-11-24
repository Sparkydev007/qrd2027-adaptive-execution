# Evaluation Metrics & Mathematical Formulation

**Project:** QRD 2027 Conference Presentation  
**Document ID:** DOC-EM-01  
**Version:** 1.0.0  

---

This document establishes the mathematical definitions, operational formulas, and economic interpretations for all 20 execution evaluation metrics used throughout the project.

---

### 1. Arrival Price ($P_0$)
- **Formula:**
  $$P_0 = P_{\tau_0}^{\text{mid}}$$
- **Plain English:** The prevailing mid-quote price at the exact moment the parent order is received by the trading desk, prior to any child slice placement.

---

### 2. Interval VWAP ($P_{\text{VWAP}}$)
- **Formula:**
  $$P_{\text{VWAP}} = \frac{\sum_{t=1}^N P_t V_t}{\sum_{t=1}^N V_t}$$
- **Plain English:** The market volume-weighted average price across all market participants during the execution window $t \in [1, N]$. Serves as the standard industry benchmark.

---

### 3. Implementation Shortfall ($\text{IS}$)
- **Formula:**
  $$\text{IS}_{\text{currency}} = \sum_{t=1}^N q_t P_t^{\text{exec}} - Q_0 P_0$$
  $$\text{IS}_{\text{bps}} = \frac{\sum_{t=1}^N q_t P_t^{\text{exec}} - Q_0 P_0}{Q_0 P_0} \times 10{,}000$$
- **Plain English:** The total execution drag relative to decision price, encompassing spread costs, market impact, and market drift while holding unexecuted inventory (Perold, 1988).

---

### 4. Slippage versus Arrival Price ($\text{Slip}_{\text{arr}}$)
- **Formula:**
  $$\text{Slip}_{\text{arr}} = \left( \frac{\bar{P}_{\text{exec}} - P_0}{P_0} \right) \times 10{,}000$$
  where $\bar{P}_{\text{exec}} = \frac{\sum_{t=1}^N q_t P_t^{\text{exec}}}{\sum_{t=1}^N q_t}$.
- **Plain English:** Percentage difference (in basis points) between the average execution price achieved and the initial arrival price.

---

### 5. Slippage versus Interval VWAP ($\text{Slip}_{\text{vwap}}$)
- **Formula:**
  $$\text{Slip}_{\text{vwap}} = \left( \frac{\bar{P}_{\text{exec}} - P_{\text{VWAP}}}{P_{\text{VWAP}}} \right) \times 10{,}000$$
- **Plain English:** Performance relative to average market price; negative slippage denotes outperforming market VWAP.

---

### 6. Temporary Market Impact ($\mathcal{I}_{\text{temp}}$)
- **Formula:**
  $$\mathcal{I}_{\text{temp}, t} = P_t^{\text{exec}} - P_t^{\text{post-child}}$$
  $$\bar{\mathcal{I}}_{\text{temp}} = \frac{1}{Q_0} \sum_{t=1}^N q_t \cdot \eta \sigma_t \left( \frac{q_t}{V_t} \right)^{0.5}$$
- **Plain English:** The instantaneous price penalty caused by child order liquidity consumption that dissipates immediately after trade execution.

---

### 7. Permanent Market Impact ($\mathcal{I}_{\text{perm}}$)
- **Formula:**
  $$\Delta P_t^{\text{perm}} = \gamma \sigma_t \left( \frac{q_t}{V_t} \right)$$
  $$\bar{\mathcal{I}}_{\text{perm}} = \frac{P_N^{\text{mid}} - P_0 - \int \text{drift}}{P_0} \times 10{,}000$$
- **Plain English:** The permanent shift in the asset's equilibrium mid-price caused by the information content of order flow.

---

### 8. Average Spread Paid ($\bar{S}_{\text{paid}}$)
- **Formula:**
  $$\bar{S}_{\text{paid}} = \frac{1}{Q_0} \sum_{t \in \text{Aggressive}} q_t \frac{S_t}{2}$$
- **Plain English:** The volume-weighted half-spread incurred whenever the execution algorithm acts as a liquidity taker.

---

### 9. Fill Rate ($\mathcal{F}$)
- **Formula:**
  $$\mathcal{F} = \frac{\sum_{t=1}^N q_t^{\text{filled}}}{Q_0} \times 100\%$$
- **Plain English:** Total percentage of the parent order successfully executed within the target horizon $T$.

---

### 10. Passive Fill Rate ($\mathcal{F}_{\text{passive}}$)
- **Formula:**
  $$\mathcal{F}_{\text{passive}} = \frac{\sum_{t=1}^N q_t^{\text{passive}}}{Q_0} \times 100\%$$
- **Plain English:** Fraction of total shares executed via non-marketable limit orders that earned the bid-ask spread.

---

### 11. Aggressive Fill Rate ($\mathcal{F}_{\text{aggressive}}$)
- **Formula:**
  $$\mathcal{F}_{\text{aggressive}} = \frac{\sum_{t=1}^N q_t^{\text{aggressive}}}{Q_0} \times 100\%$$
- **Plain English:** Fraction of total shares executed by crossing the spread with market orders.

---

### 12. Turnover ($\mathcal{T}$)
- **Formula:**
  $$\mathcal{T} = \sum_{t=1}^N q_t P_t^{\text{exec}}$$
- **Plain English:** Total gross rupee value executed across the parent order.

---

### 13. Inventory ($Q_t$)
- **Formula:**
  $$Q_t = Q_0 - \sum_{i=1}^t q_i$$
- **Plain English:** Remaining number of unexecuted shares at simulation step $t$.

---

### 14. Inventory Variance ($\sigma_Q^2$)
- **Formula:**
  $$\sigma_Q^2 = \frac{1}{N} \sum_{t=1}^N \left( Q_t - Q_t^{\text{ideal}} \right)^2$$
- **Plain English:** Measure of trajectory divergence against a linear liquidation path, proxying exposure to timing and price risk.

---

### 15. Maximum Inventory ($Q_{\max}$)
- **Formula:**
  $$Q_{\max} = \max_{t} Q_t = Q_0$$
- **Plain English:** Peak capital exposure committed to the execution mandate.

---

### 16. Execution Completion Rate ($\mathcal{C}$)
- **Formula:**
  $$\mathcal{C} = \mathbb{I}\left( Q_N = 0 \right)$$
- **Plain English:** Binary indicator or terminal proportion indicating whether the order completed fully without requiring a terminal sweep.

---

### 17. Participation Rate ($\rho_t$)
- **Formula:**
  $$\rho_t = \frac{q_t}{V_t}$$
  $$\bar{\rho} = \frac{\sum_{t=1}^N q_t}{\sum_{t=1}^N V_t}$$
- **Plain English:** Ratio of algorithm volume to total market volume in that interval. Must respect $\rho_t \le \rho_{\max}$.

---

### 18. Transaction-Cost-Adjusted Execution Cost ($\text{IS}_{\text{net}}$)
- **Formula:**
  $$\text{IS}_{\text{net}} = \text{IS}_{\text{bps}} + \text{Cost}_{\text{statutory, bps}}$$
  where $\text{Cost}_{\text{statutory}}$ accounts for STT, GST, stamp duty, and exchange fees.
- **Plain English:** Realized implementation shortfall inclusive of mandatory Indian statutory transaction charges.

---

### 19. Performance by Volatility Regime ($\text{IS} \mid \mathcal{R}_{\text{vol}}$)
- **Formula:**
  $$\text{IS}_{\text{regime}} = \mathbb{E}\left[ \text{IS} \mid \sigma_t \in \mathcal{R}_k \right], \quad k \in \{\text{calm}, \text{normal}, \text{stressed}\}$$
- **Plain English:** Stratified shortfall metrics conditioned on prevailing volatility percentiles.

---

### 20. Performance by Liquidity Regime ($\text{IS} \mid \mathcal{R}_{\text{liq}}$)
- **Formula:**
  $$\text{IS}_{\text{liq}} = \mathbb{E}\left[ \text{IS} \mid V_t \in \mathcal{R}_m \right], \quad m \in \{\text{high}, \text{medium}, \text{low}\}$$
- **Plain English:** Stratified shortfall metrics conditioned on relative market trading activity.
