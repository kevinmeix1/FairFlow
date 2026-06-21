# Challenge Explanation

The BGA AI Trading & Strategy Track asks teams to build trading and market strategy tools that are not judged purely by profit, but by whether they create better, fairer, more transparent financial systems.

My approach with FairFlow Guardian is to treat trading as a safety and fairness problem first, and a return problem second. Instead of building a bot that simply tries to maximize PnL, FairFlow asks a more important question:

**Is this market fair enough, transparent enough, and safe enough for a retail user to trade?**

FairFlow Guardian reviews a potential crypto trade before execution using multiple AI and risk agents. These agents check market regime, manipulation risk, volatility, liquidity, hidden trading costs, liquidation exposure, execution quality, and retail accessibility. If the trade looks unsafe, the system blocks it and explains why. If conditions are acceptable, it only allows a capped paper-trade route with an audit receipt.

The project is designed around the BGA judging criteria:

- Fairness and inclusion: it checks whether different retail account sizes can participate safely.
- Transparency: every decision includes plain-English reasoning, evidence, and a verifiable audit hash.
- Risk management: no-trade is treated as a valid protective outcome when markets are unsafe.
- Technical depth: the system combines a Next.js dashboard, FastAPI backend, Bybit market data, agentic decision logic, risk engines, paper portfolio simulation, and optional on-chain audit anchoring.
- Blockchain-for-good ethos: the goal is to reduce information asymmetry between retail traders and more sophisticated market participants.

In short, my approach is not to build the most aggressive trading agent. It is to build a guardian layer for AI trading: a system that makes market decisions more explainable, more verifiable, and safer for everyday users.
