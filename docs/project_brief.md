# Project Brief: QRD 2027 Conference Presentation

**Project Name:** `qrd2027_adaptive_execution`  
**Working Title:** Liquidity-Adaptive Optimal Execution in Indian Equities: A Microstructure-Aware Simulation Study  
**Target Event:** Conference on Quant, Risk & Data (QRD 2027)  
**Deliverable Format:** A0 Portrait Academic Poster (841 mm wide × 1189 mm high) & Accompanying Working Paper  

---

## 1. Executive Summary
Institutional execution quality in the National Stock Exchange of India (NSE) is governed by unique structural constraints: consolidated central limit order book liquidity, heavy statutory transaction levies (STT), and sharp intraday volume smiles. Static scheduling strategies like TWAP and VWAP exhibit systematic execution drag when liquidity evaporates or volatility spikes.

This research project develops a reproducible, empirically calibrated limit-order-book execution simulator to rigorously evaluate a **microstructure-aware, liquidity-adaptive execution controller**. The policy dynamically allocates child order volume across passive and aggressive execution paths conditioned on real-time spread width, order-book depth, volatility regimes, and terminal completion urgency.

## 2. Target Audience
- Quantitative execution researchers and algorithmic traders.
- Institutional buy-side portfolio managers and TCA (Transaction Cost Analysis) heads.
- Microstructure researchers and risk officers.

## 3. Core Contributions for the QRD 2027 Poster
1. **First Open-Source Indian Equity Microstructure Calibration:** Standardized calibration of intraday volume profiles, spread dynamics, and temporary/permanent impact coefficients across liquid NIFTY 50 equities.
2. **Controlled Microstructure Simulation Engine:** A non-lookahead discrete-time simulation model bridging the gap between coarse daily VWAP models and inaccessible multi-terabyte Level-3 tick feeds.
3. **Statistically Rigorous Policy Comparison:** Empirical distribution of Implementation Shortfall, market impact, and trajectory variance across calm, normal, and stressed market regimes.
4. **Transaction-Cost-Adjusted TCA:** Full decomposition of execution costs including statutory Indian levies (STT, stamp duty, exchange turnover fees, and GST).

## 4. Empirical Specifications
- **Calibration Period:** Calendar Year 2024 (January 2024 – December 2024).
- **Universe:** 10 core NIFTY 50 large-cap equities.
- **Granularity:** 1-minute OHLCV calibration data.
- **Parent Order Sizes:** 0.5%, 1.0%, and 2.0% of Average Daily Volume (ADV).
- **Execution Windows:** Full session (375 minutes) and intraday sub-windows.
- **Reproduction:** 100% deterministic via configuration-driven parameters and pinned random seeds.

## 5. Poster Layout Plan (A0 Portrait)
- **Header:** Title, Authors, Institutional Affiliations, QRD 2027 Branding.
- **Panel 1 (Top Left):** Research Question, Market Microstructure Context (NSE vs. US/EU), and Empirical Gap.
- **Panel 2 (Top Right):** Data Calibration (Volume Smile, Realized Volatility Clusters, Regime Classification).
- **Panel 3 (Center):** Simulator Architecture & Microstructure-Aware Fill Model (Square-Root Impact, Queue Absorption).
- **Panel 4 (Mid Left):** Execution Policies (TWAP, VWAP, POV, and Proposed Adaptive Controller).
- **Panel 5 (Mid Right):** Primary Results: Implementation Shortfall Boxplots & Impact Curves by Regime.
- **Panel 6 (Bottom):** Summary Table of 20 Evaluation Metrics, Robustness Checks, Practical Implications, and Open-Source Code QR Code.
