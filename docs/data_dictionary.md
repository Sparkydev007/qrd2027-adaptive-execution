# Data Dictionary

**Project:** QRD 2027: Liquidity-Adaptive Optimal Execution in Indian Equities  
**Document ID:** DOC-DD-01  
**Version:** 1.0.0  

---

## 1. Schema Definition

| Field | Type | Unit | Definition | Validation Rule |
|---|---|---|---|---|
| `timestamp` | `datetime64[ns, Asia/Kolkata]` | ISO 8601 | Candle opening timestamp in Asia/Kolkata timezone | Must be strictly monotonic within stock-day; no duplicates |
| `open` | `float64` | INR | First traded price in 1-minute interval | Must be finite and $> 0.0$ |
| `high` | `float64` | INR | Highest traded price in 1-minute interval | Must be $\ge \max(\text{open}, \text{close}, \text{low})$ |
| `low` | `float64` | INR | Lowest traded price in 1-minute interval | Must be $> 0.0$ and $\le \min(\text{open}, \text{close}, \text{high})$ |
| `close` | `float64` | INR | Last traded price in 1-minute interval | Must be finite and $> 0.0$ |
| `volume` | `int64` | Shares | Total traded share volume in 1-minute interval | Must be non-negative integer ($\ge 0$) |
| `returns` | `float64` | Ratio | Continuous log return from previous close: $\ln(C_t / C_{t-1})$ | Must be finite; $\|r_t\| < 0.20$ (flags circuit breaker) |
| `realised_volatility` | `float64` | Ratio (Ann.) | Rolling 20-period annualized or interval realized volatility | Must be non-negative ($\ge 0.0$) and finite |
| `dollar_volume` | `float64` | INR | Total turnover in rupees: $\text{close} \times \text{volume}$ | Must be non-negative ($\ge 0.0$) |
| `relative_volume` | `float64` | Ratio | Ratio of interval volume to rolling average volume | Must be non-negative ($\ge 0.0$) |
| `volatility_regime` | `category` | String | Volatility state: `calm`, `normal`, or `stressed` | Must be one of `['calm', 'normal', 'stressed']` |
| `liquidity_regime` | `category` | String | Volume state: `high`, `medium`, or `low` | Must be one of `['high', 'medium', 'low']` |

---

## 2. Extended Microstructure & Calibration Fields

| Extended Field | Type | Unit | Definition | Calculation / Source |
|---|---|---|---|---|
| `stock` | `string` | Ticker | NSE equity symbol | Configured universe (e.g. `RELIANCE`) |
| `date` | `date` | YYYY-MM-DD | Trading session calendar date | Extracted from localized timestamp |
| `minute_of_day` | `int16` | Minutes | Minutes elapsed from session open (0 to 374) | $(t_{\text{hour}} - 9) \times 60 + t_{\text{min}} - 15$ |
| `time_bucket_30m` | `int8` | Index | Intraday 30-minute bucket index (0 to 12) | $\lfloor \text{minute\_of\_day} / 30 \rfloor$ |
| `adv_shares` | `float64` | Shares | 20-day rolling Average Daily Volume | Rolling mean of daily aggregate volume |
| `adv_turnover` | `float64` | INR | 20-day rolling Average Daily Turnover | Rolling mean of daily rupee turnover |
| `spread_bps` | `float64` | bps | Calibrated top-of-book bid-ask spread | Calibrated parameter or volatility function |
| `depth_shares` | `float64` | Shares | Calibrated top-of-book queue depth | Multiplier $\lambda_d \times \text{volume}$ |

---

## 3. Regular Trading Hours Definition
- **Exchange:** National Stock Exchange of India (NSE)
- **Segment:** Equity Cash Segment (CM)
- **Start Time:** 09:15:00 IST
- **End Time:** 15:30:00 IST
- **Intervals per Full Session:** 375 one-minute intervals exactly.
- **Handling Gaps:** Missing minutes within 09:15–15:30 are audited and handled via clean forward-fill for price and zero-fill for volume.
