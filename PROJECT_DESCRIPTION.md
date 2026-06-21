# FairFlow Guardian Project Description

## One-Line Summary

FairFlow Guardian is an AI trading safety layer that asks whether a market is fair enough for a retail user before allowing even a paper trade.

## High-Level Overview

FairFlow Guardian is a full-stack, explainable trading strategy and risk review system built for the BGA AI Trading & Strategy Track. Rather than optimizing for the highest return, it evaluates public crypto market data through a committee of specialist agents and produces an auditable approve, reduce, hold, or reject decision.

The core idea is simple: a no-trade decision can be the right answer when market quality, execution costs, manipulation risk, liquidation exposure, or retail affordability make a trade unsafe.

The project combines a Next.js dashboard, FastAPI backend, Bybit public market data with deterministic demo fallbacks, risk and market-integrity engines, agentic AI-style review, paper portfolio simulation, fairness scoring, route analysis, and optional on-chain audit anchoring. Every decision includes plain-English reasoning, visible guardrails, cohort fairness checks, and a SHA-256 receipt that can be verified or anchored.

## The Problem

Retail traders often see the same headline price as institutions, but they do not see the same decision context. They may lack access to market depth, spread analysis, hidden execution costs, funding pressure, liquidation stress, manipulation warnings, and robust strategy validation.

Many trading tools make speculation faster. FairFlow Guardian is designed to make trading decisions safer, more explainable, and more inclusive.

## The Solution

FairFlow Guardian acts as a pre-trade fairness and risk review layer. Before a trade can be approved, the system checks:

- whether the market regime is calm, volatile, or manipulated
- whether liquidity and spread conditions are fair for retail execution
- whether hidden costs make the trade economically unreasonable
- whether the strategy survives realistic trading costs and chronological validation
- whether the same trade remains accessible across different retail account sizes
- whether execution routes create unnecessary slippage, leakage, or manipulation exposure
- whether agent concerns should downgrade, block, or allow the proposed action

If the checks fail, execution is locked and the dashboard explains why. If the checks pass, the system only permits a capped paper route with an audit receipt.

## How It Works

1. The user selects a market, such as BTC, ETH, SOL, BNB, XRP, LINK, ADA, or DOGE.
2. The backend pulls public market data, or uses deterministic fallback scenarios for reliable demos.
3. The risk engine calculates spread, volatility, liquidity, funding pressure, stress loss, and hidden-cost drag.
4. The AI committee reviews the trade from multiple angles, including market regime, manipulation risk, uncertainty, execution route, backtest quality, memory calibration, and audit narration.
5. The frontend shows an explainable decision: approve, reduce, hold, or reject.
6. The system generates a receipt, evidence pack, fairness passport, policy stress report, and optional on-chain anchor payload.
7. The paper portfolio records only permitted simulated actions, while blocked actions remain visible for transparency.

## What Makes It Agentic

FairFlow Guardian is not a single model response wrapped in a dashboard. It uses a structured agent committee, where each specialist has a clear role:

- Market Regime Agent: classifies current conditions from rolling candles.
- Manipulation Sentinel: detects abnormal volatility, wick, volume, spread, and order-book behavior.
- Risk Guardian: checks liquidation exposure, stress loss, and policy limits.
- Execution Planner: selects the least harmful paper route only when approval is justified.
- Backtest Agent: evaluates whether a strategy survives out-of-sample validation and realistic costs.
- Fairness Agent: checks whether the trade is still accessible and defensible for different retail cohorts.
- Audit Narrator: turns the decision path into judge-ready plain English.

The agents can disagree, and disagreement matters. A single serious risk concern can downgrade or block the trade.

## Why It Fits the BGA Track

FairFlow Guardian is aligned with the BGA ethos because it treats trading infrastructure as a public-safety and market-transparency problem, not just a return-generation problem.

It promotes:

- Financial inclusion: cohort checks show whether micro, starter, everyday, and active retail accounts can participate safely.
- Fairness: guardrails focus on hidden costs, route quality, liquidation pressure, and retail execution parity.
- Transparency: every decision has a visible trace, evidence pack, receipt, and audit hash.
- Healthier markets: no-trade is treated as a successful protective outcome when conditions are unsafe.
- Verifiability: decisions can be reproduced, copied, reviewed, and optionally anchored on-chain.

The project is intentionally paper-only for the demo. It does not request exchange keys, place live trades, or encourage unbounded autonomous execution.

## Technical Stack

- Frontend: Next.js App Router, TypeScript, responsive dashboard UI.
- Backend: FastAPI service with market, agent, risk, audit, and portfolio endpoints.
- Data: Bybit V5 public market data with deterministic fallback scenarios.
- Persistence: SQLite audit ledger for generated reports.
- Strategy and risk: chronological validation, realistic cost assumptions, volatility and liquidity controls, manipulation probes, route scoring, and stress testing.
- Blockchain component: Solidity audit anchor contract for storing decision hashes.
- Demo assets: judge-facing PDF walkthrough, narrated MP4 demo, deck, scripts, screenshots, and submission package.

## Live Demo Path

The intended two-minute judge demo shows:

1. Competition Runway: the thesis, readiness score, and proof bundle.
2. Live Price Chart: real-time market context from the same data path used by the agents.
3. Agent Dashboard: specialist agents approving, warning, or blocking.
4. Fairness Passport: retail access, execution parity, manipulation exposure, risk protection, and auditability.
5. Execution Router: route choices that are locked unless the trade is fair enough.
6. Evidence Pack: a copyable proof artifact with decision, receipt, policy stress, route proof, and anchor payload.
7. Manipulated Scenario: a visible no-trade outcome with clear reasons.

## Safety Boundaries

FairFlow Guardian is a decision-support and paper-trading project. It is not financial advice, not a live trading bot, and not a guarantee of profit. The design deliberately favors explainability, guardrails, and blocked execution over aggressive autonomous trading.

## Submission Artifacts

- Main repository: `README.md`
- Submission notes: `SUBMISSION.md`
- Judge live demo PDF: `submission/judge-live-demo/FairFlow_Guardian_judge_live_demo_walkthrough.pdf`
- Judge live demo video: `submission/judge-live-demo/FairFlow_Guardian_judge_live_demo_walkthrough_from_pdf_male_narrated.mp4`
- Final deck package: `submission/deck/`
- Full walkthrough documents: `submission/docs/`

## GitHub About Description

AI trading safety layer that audits crypto trades for fairness, manipulation risk, hidden costs, liquidation exposure, and verifiable execution before any action is allowed.
