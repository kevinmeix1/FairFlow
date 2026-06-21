# FairFlow Guardian Solution Diagram

This diagram shows the full FairFlow Guardian solution: the judge-facing dashboard, data path, backend services, agentic review layer, risk controls, audit artifacts, and optional on-chain verification.

```mermaid
flowchart TB
    User["Retail user or hackathon judge"] --> UI["Next.js dashboard"]

    subgraph Frontend["Frontend experience"]
        UI --> Runway["Competition Runway"]
        UI --> Chart["Real-time price chart"]
        UI --> AgentsPanel["Active agents dashboard"]
        UI --> FairnessPassport["Fairness Passport"]
        UI --> PolicyStudio["Policy Studio and Stress Lab"]
        UI --> RouterView["Fair Execution Router"]
        UI --> PortfolioView["Paper portfolio"]
        UI --> EvidenceView["Evidence Pack and Receipt"]
        UI --> DemoViews["Judge demo, runbook, and submission views"]
    end

    UI --> Client["Typed API client"]
    Client --> Proxy["Next.js API proxy"]
    Proxy --> API["FastAPI backend service"]

    subgraph DataLayer["Market data and scenario layer"]
        API --> Bybit["Bybit V5 public market data"]
        API --> Fallback["Deterministic fallback scenarios"]
        Bybit --> Normalizer["Candle, depth, funding, and ticker normalizer"]
        Fallback --> Normalizer
        Normalizer --> Metrics["Market metrics engine"]
        Metrics --> Spread["Spread and liquidity quality"]
        Metrics --> Volatility["Volatility and stress loss"]
        Metrics --> Funding["Funding and crowding pressure"]
        Metrics --> CostModel["Fees, slippage, and hidden-cost model"]
    end

    subgraph AgentLayer["Agentic AI and strategy review layer"]
        Metrics --> RegimeAgent["Market Regime Agent"]
        Metrics --> ManipulationAgent["Manipulation Sentinel"]
        Metrics --> RiskAgent["Risk Guardian"]
        Metrics --> ForecastAgent["Uncertainty Forecast Agent"]
        Metrics --> BacktestAgent["Backtest and Robustness Agent"]
        Metrics --> FairnessAgent["Retail Fairness Agent"]
        Metrics --> ExecutionAgent["Execution Planner Agent"]
        Metrics --> NarratorAgent["Audit Narrator Agent"]
    end

    subgraph Guardrails["Decision, fairness, and risk guardrails"]
        RegimeAgent --> Committee["Agent committee review"]
        ManipulationAgent --> Committee
        RiskAgent --> Committee
        ForecastAgent --> Committee
        BacktestAgent --> Committee
        FairnessAgent --> Committee
        ExecutionAgent --> Committee
        NarratorAgent --> Committee

        Committee --> PolicyGate["Policy gate"]
        PolicyGate --> CohortCheck["Retail cohort simulator"]
        PolicyGate --> RedTeam["Market integrity red-team probes"]
        PolicyGate --> RouteScore["Route scoring and execution quality"]
        CohortCheck --> Decision["Approve, reduce, hold, or reject"]
        RedTeam --> Decision
        RouteScore --> Decision
    end

    subgraph SafetyActions["Allowed and blocked actions"]
        Decision -->|Unsafe market| NoTrade["No-trade lock with plain-English reason"]
        Decision -->|Acceptable market| PaperRoute["Capped paper-trade route"]
        PaperRoute --> PaperLedger["Paper portfolio ledger"]
        NoTrade --> BlockedLog["Blocked action history"]
    end

    subgraph AuditLayer["Transparency and verification layer"]
        Decision --> Trace["Decision trace"]
        Trace --> Receipt["Retail fairness receipt"]
        Receipt --> EvidencePack["Audit evidence pack"]
        EvidencePack --> Hash["SHA-256 audit hash"]
        Hash --> SQLite["SQLite audit ledger"]
        Hash --> AnchorPayload["Solidity anchor payload"]
        AnchorPayload --> Contract["Optional FairFlowAudit smart contract"]
    end

    PaperLedger --> PortfolioView
    BlockedLog --> PortfolioView
    Receipt --> EvidenceView
    EvidencePack --> EvidenceView
    Committee --> AgentsPanel
    RouteScore --> RouterView

    subgraph Submission["Submission and demo artifacts"]
        EvidencePack --> PDF["Live demo PDF walkthrough"]
        EvidencePack --> Video["Two-minute narrated MP4 demo"]
        EvidencePack --> Deck["Presentation deck and script"]
        EvidencePack --> GitHubDocs["GitHub documentation"]
    end
```

## How to Explain the Diagram

FairFlow Guardian starts with a user or judge interacting with the Next.js dashboard. The dashboard is not just a visual shell; it exposes the main product workflow: live market context, agent status, fairness checks, policy controls, paper portfolio, evidence pack, and demo materials.

The frontend calls a typed API client, which passes requests through a Next.js API proxy into the FastAPI backend. The backend pulls public market data from Bybit when available and falls back to deterministic scenarios when live data is unavailable or when a judge needs a reliable calm, volatile, or manipulated market example.

The backend normalizes raw market data into trading metrics such as spread, liquidity quality, volatility, funding pressure, stress loss, and hidden execution costs. Those metrics feed a committee of specialist agents. Each agent has a defined job: classify the regime, detect manipulation, review risk, forecast uncertainty, test strategy robustness, check retail fairness, plan execution, or explain the audit.

The agent outputs are passed through policy and fairness guardrails. This layer decides whether the trade should be approved, reduced, held, or rejected. If the market is unsafe, FairFlow Guardian locks execution and explains the reason. If conditions are acceptable, it only permits a capped paper-trade route.

Every decision creates a transparent audit trail. The system generates a decision trace, retail fairness receipt, evidence pack, SHA-256 hash, persistent ledger entry, and optional Solidity anchor payload. This makes the decision explainable to the user and verifiable for judges.

The final outputs are the dashboard, PDF walkthrough, narrated MP4 demo, presentation deck, and GitHub documentation. Together, they show the hackathon thesis: AI trading systems should be safer, more transparent, and more fair, not merely more aggressive.

## Core Design Principle

FairFlow Guardian treats **no trade** as a valid protective outcome. A blocked trade is not a failed demo; it is proof that the system can prioritize retail safety, transparency, and market integrity over speculation.
