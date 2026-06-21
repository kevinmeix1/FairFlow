from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from statistics import median, pstdev
from typing import Literal

from fastapi.encoders import jsonable_encoder

from .ai_agents import build_ai_committee, remember_committee_decision
from .models import (
    AgentFinding,
    CommitteeReport,
    DecisionTraceStep,
    FairnessCheck,
    FairnessPassport,
    GuardianDecision,
    MarketMetrics,
    MarketSnapshot,
    StrategyProposal,
    StressResult,
)

ACCOUNT_EQUITY_USDT = 10_000.0
MAX_POSITION_USDT = 2_500.0
RISK_BUDGET_PCT = 1.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current / previous - 1) * 100


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = [max(change, 0.0) for change in recent]
    losses = [abs(min(change, 0.0)) for change in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def _market_impact_bps(levels: list, mid_price: float, notional: float, side: str) -> float:
    remaining = notional
    spent_or_received = 0.0
    acquired = 0.0

    for level in levels:
        level_notional = level.price * level.size
        consumed = min(remaining, level_notional)
        size = consumed / level.price
        acquired += size
        spent_or_received += consumed
        remaining -= consumed
        if remaining <= 0:
            break

    if remaining > 0 or acquired == 0:
        return 250.0

    average_price = spent_or_received / acquired
    if side == "buy":
        return max(0.0, (average_price / mid_price - 1) * 10000)
    return max(0.0, (1 - average_price / mid_price) * 10000)


def compute_metrics(snapshot: MarketSnapshot) -> MarketMetrics:
    closes = [c.close for c in snapshot.candles]
    highs = [c.high for c in snapshot.candles]
    lows = [c.low for c in snapshot.candles]
    volumes = [c.volume for c in snapshot.candles]
    returns = [
        (closes[index] / closes[index - 1] - 1)
        for index in range(1, len(closes))
        if closes[index - 1] != 0
    ]

    best_bid = snapshot.bids[0].price
    best_ask = snapshot.asks[0].price
    mid_price = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid_price * 10000
    bid_depth = sum(level.price * level.size for level in snapshot.bids[:10])
    ask_depth = sum(level.price * level.size for level in snapshot.asks[:10])
    total_depth = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total_depth if total_depth else 0.0
    top_depth_usd = snapshot.bids[0].price * snapshot.bids[0].size + snapshot.asks[0].price * snapshot.asks[0].size

    buy_impact = _market_impact_bps(snapshot.asks, mid_price, 25_000, "buy")
    sell_impact = _market_impact_bps(snapshot.bids, mid_price, 25_000, "sell")
    impact_25k_bps = max(buy_impact, sell_impact)

    latest_returns = returns[-24:] if len(returns) >= 24 else returns
    realized_volatility_pct = (pstdev(latest_returns) * math.sqrt(12) * 100) if len(latest_returns) > 2 else 0.0
    range_24h_pct = ((max(highs) - min(lows)) / closes[-1] * 100) if closes[-1] else 0.0
    momentum_1h_pct = _pct_change(closes[-1], closes[-13]) if len(closes) >= 13 else 0.0
    momentum_4h_pct = _pct_change(closes[-1], closes[-49]) if len(closes) >= 49 else momentum_1h_pct

    recent_median_volume = median(volumes[-25:-1]) if len(volumes) >= 25 else median(volumes)
    latest_volume_ratio = volumes[-1] / recent_median_volume if recent_median_volume else 1.0
    latest = snapshot.candles[-1]
    upper_wick = latest.high - max(latest.open, latest.close)
    lower_wick = min(latest.open, latest.close) - latest.low
    latest_wick_pct = max(upper_wick, lower_wick) / latest.close * 100

    funding_rate_bps = snapshot.ticker.funding_rate * 10000
    liquidity_score = 100
    liquidity_score -= _clamp(spread_bps * 4.0, 0, 35)
    liquidity_score -= _clamp(impact_25k_bps * 2.4, 0, 30)
    liquidity_score -= _clamp(abs(imbalance) * 28, 0, 20)
    liquidity_score -= 12 if top_depth_usd < 15_000 else 0
    liquidity_score = _clamp(liquidity_score, 0, 100)

    return MarketMetrics(
        price=snapshot.ticker.last_price,
        mid_price=mid_price,
        spread_bps=spread_bps,
        order_book_imbalance=imbalance,
        top_depth_usd=top_depth_usd,
        impact_25k_bps=impact_25k_bps,
        realized_volatility_pct=realized_volatility_pct,
        range_24h_pct=range_24h_pct,
        momentum_1h_pct=momentum_1h_pct,
        momentum_4h_pct=momentum_4h_pct,
        rsi_14=_rsi(closes),
        latest_volume_ratio=latest_volume_ratio,
        latest_wick_pct=latest_wick_pct,
        funding_rate_bps=funding_rate_bps,
        open_interest=snapshot.ticker.open_interest,
        liquidity_score=liquidity_score,
    )


def market_regime_agent(metrics: MarketMetrics) -> AgentFinding:
    rationale: list[str] = []
    score = 78.0
    status = "pass"
    verdict = "Orderly market"

    if metrics.realized_volatility_pct > 1.65 or metrics.range_24h_pct > 6.0:
        rationale.append("Short-window volatility is elevated relative to the allowed execution band.")
        score -= 28
        status = "watch"
        verdict = "High volatility regime"

    if abs(metrics.momentum_1h_pct) > 0.7 and abs(metrics.momentum_4h_pct) > 1.2:
        direction = "up" if metrics.momentum_1h_pct > 0 else "down"
        rationale.append(f"Momentum is directional {direction}, so trend-following logic is available.")
        score += 8
        if verdict == "Orderly market":
            verdict = "Directional trend regime"

    if metrics.rsi_14 > 70 or metrics.rsi_14 < 30:
        rationale.append("RSI is stretched, so entries need mean-reversion awareness.")
        score -= 9
        status = "watch"

    if metrics.liquidity_score < 50:
        rationale.append("Liquidity quality is too weak for fair retail execution.")
        score -= 20
        status = "block"
        verdict = "Fragile liquidity regime"

    if not rationale:
        rationale.append("Volatility, liquidity, and momentum are within normal operating bounds.")

    return AgentFinding(
        name="Market Regime Agent",
        status=status,
        verdict=verdict,
        score=_clamp(score, 0, 100),
        rationale=rationale,
    )


def strategy_agent(metrics: MarketMetrics) -> tuple[StrategyProposal, AgentFinding]:
    action = "NO_TRADE"
    confidence = 0.42
    thesis = "Signal quality is not strong enough to justify execution."

    if metrics.rsi_14 < 34 and metrics.liquidity_score > 55:
        action = "LONG"
        confidence = 0.64
        thesis = "Mean-reversion long: RSI is washed out while liquidity remains acceptable."
    elif metrics.rsi_14 > 66 and metrics.liquidity_score > 55:
        action = "SHORT"
        confidence = 0.62
        thesis = "Mean-reversion short: RSI is extended while liquidity remains acceptable."
    elif metrics.momentum_1h_pct > 0.35 and metrics.realized_volatility_pct < 1.35 and metrics.liquidity_score > 60:
        action = "LONG"
        confidence = 0.67
        thesis = "Trend-following long: short-term momentum is positive without excessive volatility."
    elif metrics.momentum_1h_pct < -0.35 and metrics.realized_volatility_pct < 1.35 and metrics.liquidity_score > 60:
        action = "SHORT"
        confidence = 0.66
        thesis = "Trend-following short: short-term momentum is negative without excessive volatility."
    elif abs(metrics.momentum_1h_pct) > 1.2:
        action = "SHORT" if metrics.momentum_1h_pct < 0 else "LONG"
        confidence = 0.51
        thesis = "Momentum is strong, but risk controls must decide whether this is a chase."

    stop_distance_pct = _clamp(metrics.realized_volatility_pct * 1.55 + metrics.spread_bps / 18, 0.55, 2.8)
    take_profit_distance_pct = stop_distance_pct * 1.85
    leverage = 1.5 if metrics.realized_volatility_pct > 1.2 else 2.0

    if action == "NO_TRADE":
        proposal = StrategyProposal(
            action=action,
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            leverage=0,
            position_size_usdt=0,
            confidence=confidence,
            thesis=thesis,
        )
    else:
        entry = metrics.price
        if action == "LONG":
            stop_loss = entry * (1 - stop_distance_pct / 100)
            take_profit = entry * (1 + take_profit_distance_pct / 100)
        else:
            stop_loss = entry * (1 + stop_distance_pct / 100)
            take_profit = entry * (1 - take_profit_distance_pct / 100)

        risk_budget_usdt = ACCOUNT_EQUITY_USDT * (RISK_BUDGET_PCT / 100)
        raw_position = risk_budget_usdt / (stop_distance_pct / 100)
        position_size = min(MAX_POSITION_USDT, raw_position)

        proposal = StrategyProposal(
            action=action,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=leverage,
            position_size_usdt=position_size,
            confidence=confidence,
            thesis=thesis,
        )

    status = "pass" if confidence >= 0.62 and action != "NO_TRADE" else "watch"
    if action == "NO_TRADE":
        status = "watch"
    finding = AgentFinding(
        name="Strategy Agent",
        status=status,
        verdict=f"{action.replace('_', ' ').title()} proposal",
        score=_clamp(confidence * 100, 0, 100),
        rationale=[
            thesis,
            f"Confidence is {confidence:.0%}; the execution gate requires independent risk approval.",
        ],
    )
    return proposal, finding


def manipulation_sentinel(metrics: MarketMetrics) -> AgentFinding:
    risk = 0.0
    rationale: list[str] = []

    if metrics.spread_bps > 6:
        risk += min(25, metrics.spread_bps * 1.8)
        rationale.append(f"Spread is wide at {metrics.spread_bps:.1f} bps.")
    if metrics.impact_25k_bps > 8:
        risk += min(22, metrics.impact_25k_bps * 1.6)
        rationale.append(f"A 25k USDT market order would move price by about {metrics.impact_25k_bps:.1f} bps.")
    if abs(metrics.order_book_imbalance) > 0.32:
        risk += min(22, abs(metrics.order_book_imbalance) * 42)
        side = "bid-heavy" if metrics.order_book_imbalance > 0 else "ask-heavy"
        rationale.append(f"Top-of-book depth is unusually {side}.")
    if metrics.latest_volume_ratio > 2.2:
        risk += min(18, (metrics.latest_volume_ratio - 1) * 9)
        rationale.append(f"Latest volume is {metrics.latest_volume_ratio:.1f}x the recent median.")
    if metrics.latest_wick_pct > 0.85:
        risk += min(18, metrics.latest_wick_pct * 8)
        rationale.append(f"Latest candle wick is large at {metrics.latest_wick_pct:.2f}%.")
    if abs(metrics.funding_rate_bps) > 4.5:
        risk += min(18, abs(metrics.funding_rate_bps) * 3)
        crowded = "longs" if metrics.funding_rate_bps > 0 else "shorts"
        rationale.append(f"Funding suggests crowded {crowded} at {metrics.funding_rate_bps:.2f} bps.")

    if not rationale:
        rationale.append("No abnormal spread, volume, funding, wick, or depth pattern detected.")

    if risk >= 62:
        status = "block"
        verdict = "Manipulation/liquidity trap risk is high"
    elif risk >= 34:
        status = "watch"
        verdict = "Market quality is degraded"
    else:
        status = "pass"
        verdict = "Market quality is acceptable"

    return AgentFinding(
        name="Manipulation Sentinel",
        status=status,
        verdict=verdict,
        score=_clamp(100 - risk, 0, 100),
        rationale=rationale,
    )


def stress_tests(metrics: MarketMetrics, proposal: StrategyProposal) -> list[StressResult]:
    if proposal.action == "NO_TRADE" or not proposal.entry_price:
        return [
            StressResult(
                price_move_pct=0,
                projected_pnl_pct=0,
                projected_equity_usdt=ACCOUNT_EQUITY_USDT,
                stop_triggered=False,
                note="No position is opened, so portfolio equity is unchanged.",
            )
        ]

    tests = [-1, -2, -5, -10, 1, 2, 5, 10]
    results: list[StressResult] = []
    direction = 1 if proposal.action == "LONG" else -1
    for move in tests:
        pnl_pct = move * direction * proposal.leverage
        projected_equity = ACCOUNT_EQUITY_USDT + proposal.position_size_usdt * pnl_pct / 100
        adverse_move = move < 0 if proposal.action == "LONG" else move > 0
        stop_distance_pct = abs((proposal.entry_price - proposal.stop_loss) / proposal.entry_price * 100) if proposal.stop_loss else 0
        stop_triggered = adverse_move and abs(move) >= stop_distance_pct
        note = "Stop would trigger before full scenario loss." if stop_triggered else "Within modeled stop band."
        if pnl_pct < -8:
            note = "Large adverse move creates unacceptable drawdown pressure."
        results.append(
            StressResult(
                price_move_pct=move,
                projected_pnl_pct=pnl_pct,
                projected_equity_usdt=projected_equity,
                stop_triggered=stop_triggered,
                note=note,
            )
        )
    return results


def risk_guardian_agent(
    metrics: MarketMetrics,
    proposal: StrategyProposal,
    sentinel: AgentFinding,
    regime: AgentFinding,
) -> tuple[AgentFinding, list[str]]:
    rationale: list[str] = []
    safeguards = [
        "Paper/testnet execution only in this prototype.",
        "Stop loss is mandatory for any executable recommendation.",
        "Position size is capped at 25% of demo equity.",
        "Maximum modeled risk budget is 1% of demo equity.",
        "Execution is blocked during high manipulation or fragile-liquidity states.",
        "Cooldown-first design: one decision report per user refresh, no runaway loop.",
    ]
    score = 88.0
    blocked = False

    if proposal.action == "NO_TRADE":
        rationale.append("The strategy did not produce an actionable setup.")
        return (
            AgentFinding(
                name="Risk Guardian",
                status="watch",
                verdict="No execution requested",
                score=72,
                rationale=rationale,
            ),
            safeguards,
        )

    if sentinel.status == "block":
        blocked = True
        score -= 34
        rationale.append("Manipulation Sentinel blocked execution due to market-quality risk.")
    if regime.status == "block":
        blocked = True
        score -= 24
        rationale.append("Market Regime Agent identified fragile liquidity.")
    if metrics.realized_volatility_pct > 2.1:
        blocked = True
        score -= 18
        rationale.append(f"Realized volatility is too high at {metrics.realized_volatility_pct:.2f}%.")
    if metrics.liquidity_score < 55:
        blocked = True
        score -= 18
        rationale.append(f"Liquidity score {metrics.liquidity_score:.0f}/100 is below execution threshold.")
    if proposal.confidence < 0.58:
        blocked = True
        score -= 14
        rationale.append(f"Strategy confidence {proposal.confidence:.0%} is below the approval threshold.")
    if proposal.stop_loss is None:
        blocked = True
        score -= 25
        rationale.append("Stop loss is missing.")

    stop_distance_pct = (
        abs((proposal.entry_price - proposal.stop_loss) / proposal.entry_price * 100)
        if proposal.entry_price and proposal.stop_loss
        else 0
    )
    liquidation_distance_pct = (1 / proposal.leverage) * 88 if proposal.leverage else 0
    if stop_distance_pct * 2 > liquidation_distance_pct:
        blocked = True
        score -= 10
        rationale.append("Stop distance is too close to estimated liquidation distance.")

    if not rationale:
        rationale.append("Risk budget, liquidity, volatility, stop loss, and strategy confidence pass the gate.")

    return (
        AgentFinding(
            name="Risk Guardian",
            status="block" if blocked else "pass",
            verdict="Execution rejected" if blocked else "Execution approved with guardrails",
            score=_clamp(score, 0, 100),
            rationale=rationale,
        ),
        safeguards,
    )


def _audit_hash(payload: dict) -> str:
    canonical = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _worst_status(statuses: list[Literal["pass", "watch", "block"]]) -> Literal["pass", "watch", "block"]:
    if "block" in statuses:
        return "block"
    if "watch" in statuses:
        return "watch"
    return "pass"


def _status_from_score(score: float, *, block_below: float = 45, watch_below: float = 70) -> Literal["pass", "watch", "block"]:
    if score < block_below:
        return "block"
    if score < watch_below:
        return "watch"
    return "pass"


def build_fairness_passport(
    *,
    snapshot: MarketSnapshot,
    metrics: MarketMetrics,
    proposal: StrategyProposal,
    sentinel: AgentFinding,
    ai_committee: CommitteeReport,
    status: Literal["approved", "blocked", "observe"],
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
) -> FairnessPassport:
    if snapshot.source == "bybit:v5-public":
        data_score = 96.0
        data_status: Literal["pass", "watch", "block"] = "pass"
        data_explanation = "Decision uses public Bybit market data that any retail user can independently query."
    elif "after-live-error" in snapshot.source:
        data_score = 62.0
        data_status = "watch"
        data_explanation = "Live data failed over to a deterministic fallback, so execution should remain paper-only."
    else:
        data_score = 82.0
        data_status = "pass"
        data_explanation = "Scenario data is deterministic and reproducible for demos, so judges can replay the same decision."

    execution_score = _clamp(
        100
        - metrics.spread_bps * 4.2
        - metrics.impact_25k_bps * 3.0
        - abs(metrics.order_book_imbalance) * 24
        - (12 if metrics.top_depth_usd < 25_000 else 0),
        0,
        100,
    )
    execution_status = _status_from_score(execution_score, block_below=50, watch_below=72)
    execution_explanation = (
        "Top-of-book costs are low enough that a small retail-sized order is not obviously disadvantaged."
        if execution_status == "pass"
        else "Execution quality is degraded; the user may face avoidable spread, impact, or book-imbalance costs."
    )

    manipulation_score = sentinel.score
    manipulation_status = sentinel.status
    manipulation_explanation = (
        "Manipulation and liquidity-trap signals are inside the safe envelope."
        if sentinel.status == "pass"
        else "Market-quality warnings suggest retail users may be trading against an unfair setup."
    )

    if proposal.action == "NO_TRADE":
        risk_score = 84.0 if status == "observe" else 72.0
        risk_status: Literal["pass", "watch", "block"] = "watch"
        risk_explanation = "No position is opened, which protects the user while signal quality is weak."
        risk_evidence = [
            "Final route is locked",
            "No leverage is applied",
            f"Strategy confidence {proposal.confidence:.0%}",
        ]
    else:
        stop_is_present = proposal.stop_loss is not None and proposal.entry_price is not None
        stop_distance_pct = (
            abs((proposal.entry_price - proposal.stop_loss) / proposal.entry_price * 100)
            if proposal.entry_price and proposal.stop_loss
            else 0.0
        )
        risk_score = 92.0
        risk_score -= 34 if not stop_is_present else 0
        risk_score -= _clamp((proposal.leverage - 2.0) * 12, 0, 24)
        risk_score -= _clamp((proposal.position_size_usdt / ACCOUNT_EQUITY_USDT - 0.18) * 80, 0, 16)
        risk_score -= 18 if ai_committee.forecast.stop_loss_hit_probability > 0.62 else 0
        risk_score = _clamp(risk_score, 0, 100)
        risk_status = _status_from_score(risk_score, block_below=55, watch_below=75)
        risk_explanation = (
            "Trade sizing, stop loss, and leverage keep the proposed exposure inside the retail protection envelope."
            if risk_status == "pass"
            else "The proposed exposure needs more protection before it is fair to execute."
        )
        risk_evidence = [
            f"Leverage {proposal.leverage:.1f}x",
            f"Position cap {proposal.position_size_usdt:.0f} USDT",
            f"Stop distance {stop_distance_pct:.2f}%",
            f"Forecast stop-hit probability {ai_committee.forecast.stop_loss_hit_probability:.0%}",
        ]

    transparency_score = 94.0
    transparency_status: Literal["pass", "watch", "block"] = "pass"
    transparency_explanation = "The report includes a decision trace, agent rationales, safeguards, and a hashable payload."

    estimated_hidden_cost_bps = _clamp(
        metrics.spread_bps / 2
        + metrics.impact_25k_bps
        + max(0.0, abs(metrics.funding_rate_bps) - 3.0) * 0.6
        + max(0.0, metrics.latest_wick_pct - 0.45) * 2.0,
        0,
        250,
    )

    checks = [
        FairnessCheck(
            name="Information parity",
            status=data_status,
            score=data_score,
            explanation=data_explanation,
            evidence=[
                f"Source: {snapshot.source}",
                f"Scenario: {snapshot.scenario}",
                f"{len(snapshot.candles)} candles and {len(snapshot.bids) + len(snapshot.asks)} book levels reviewed",
            ],
        ),
        FairnessCheck(
            name="Execution parity",
            status=execution_status,
            score=execution_score,
            explanation=execution_explanation,
            evidence=[
                f"Spread {metrics.spread_bps:.1f} bps",
                f"25k impact {metrics.impact_25k_bps:.1f} bps",
                f"Book imbalance {metrics.order_book_imbalance * 100:.1f}%",
                f"Top depth {metrics.top_depth_usd:,.0f} USDT",
            ],
        ),
        FairnessCheck(
            name="Manipulation exposure",
            status=manipulation_status,
            score=manipulation_score,
            explanation=manipulation_explanation,
            evidence=sentinel.rationale[:4],
        ),
        FairnessCheck(
            name="Retail risk protection",
            status=risk_status,
            score=risk_score,
            explanation=risk_explanation,
            evidence=risk_evidence,
        ),
        FairnessCheck(
            name="Auditability",
            status=transparency_status,
            score=transparency_score,
            explanation=transparency_explanation,
            evidence=[
                "Decision trace is included in the audited payload",
                "AI committee debate is preserved",
                "SHA-256 hash is generated before paper execution",
            ],
        ),
    ]

    score = _clamp(
        data_score * 0.15
        + execution_score * 0.22
        + manipulation_score * 0.25
        + risk_score * 0.20
        + transparency_score * 0.18,
        0,
        100,
    )
    worst_status = _worst_status([check.status for check in checks])
    if worst_status == "block" or score < 55:
        verdict: Literal["fair_to_execute", "wait_for_parity", "unfair_to_retail"] = "unfair_to_retail"
        summary = "FairFlow marks this market as unfair for retail execution right now."
    elif status == "approved" and final_action != "NO_TRADE" and score >= 72:
        verdict = "fair_to_execute"
        summary = "FairFlow finds enough parity, protection, and auditability for a capped paper route."
    else:
        verdict = "wait_for_parity"
        summary = "FairFlow recommends waiting until signal quality or market fairness improves."

    retail_protections = [
        "Block execution when manipulation, liquidity, or volatility creates an avoidable retail disadvantage.",
        "Prefer no-fill or paper-only routes over chasing the book.",
        "Expose spread, impact, funding, and book imbalance before any order simulation.",
        "Attach an audit hash so the decision can be checked after the market moves.",
    ]
    if proposal.action != "NO_TRADE":
        retail_protections.append("Require a stop loss and cap notional size before routing.")
    else:
        retail_protections.append("Keep execution locked when the strategy has no defensible setup.")

    return FairnessPassport(
        score=score,
        verdict=verdict,
        summary=summary,
        estimated_hidden_cost_bps=estimated_hidden_cost_bps,
        checks=checks,
        retail_protections=retail_protections,
    )


def build_decision_trace(
    *,
    snapshot: MarketSnapshot,
    metrics: MarketMetrics,
    proposal: StrategyProposal,
    deterministic_agents: list[AgentFinding],
    all_agents: list[AgentFinding],
    ai_committee: CommitteeReport,
    stress_results: list[StressResult],
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
    status: Literal["approved", "blocked", "observe"],
) -> list[DecisionTraceStep]:
    data_status: Literal["pass", "watch", "block"] = "watch" if "after-live-error" in snapshot.source else "pass"
    feature_status: Literal["pass", "watch", "block"] = "pass"
    if metrics.liquidity_score < 45:
        feature_status = "block"
    elif metrics.liquidity_score < 60 or metrics.realized_volatility_pct > 1.65 or metrics.spread_bps > 6:
        feature_status = "watch"

    strategy_status: Literal["pass", "watch", "block"] = "watch" if proposal.action == "NO_TRADE" else "pass"
    if proposal.confidence < 0.52 and proposal.action != "NO_TRADE":
        strategy_status = "watch"

    deterministic_status = _worst_status([agent.status for agent in deterministic_agents])
    committee_status = _worst_status(
        [agent.status for agent in all_agents if agent.name not in {agent.name for agent in deterministic_agents}]
    )
    stop_hit_probability = ai_committee.forecast.stop_loss_hit_probability
    worst_stress = min((result.projected_pnl_pct for result in stress_results), default=0.0)
    risk_status: Literal["pass", "watch", "block"] = "pass"
    if status == "blocked":
        risk_status = "block"
    elif status == "observe" or stop_hit_probability > 0.38 or worst_stress < -6:
        risk_status = "watch"

    final_status: Literal["pass", "watch", "block"] = (
        "pass" if status == "approved" else "block" if status == "blocked" else "watch"
    )

    return [
        DecisionTraceStep(
            step=1,
            status=data_status,
            title="Market data intake",
            summary=f"{snapshot.symbol} {snapshot.category} market context loaded from {snapshot.source}.",
            evidence=[
                f"{len(snapshot.candles)} five-minute candles",
                f"{len(snapshot.bids)} bid levels and {len(snapshot.asks)} ask levels",
                f"Scenario mode: {snapshot.scenario}",
            ],
        ),
        DecisionTraceStep(
            step=2,
            status=feature_status,
            title="Feature engineering",
            summary="FairFlow converts raw candles and order-book depth into execution-quality features.",
            evidence=[
                f"Liquidity score {metrics.liquidity_score:.0f}/100",
                f"Spread {metrics.spread_bps:.1f} bps and 25k impact {metrics.impact_25k_bps:.1f} bps",
                f"RSI {metrics.rsi_14:.1f}, volatility {metrics.realized_volatility_pct:.2f}%, funding {metrics.funding_rate_bps:.2f} bps",
            ],
        ),
        DecisionTraceStep(
            step=3,
            status=strategy_status,
            title="Strategy proposal",
            summary=proposal.thesis,
            evidence=[
                f"Candidate action: {proposal.action.replace('_', ' ')}",
                f"Confidence {proposal.confidence:.0%}",
                f"Risk budget {proposal.risk_budget_pct:.1f}% with notional cap {proposal.position_size_usdt:.0f} USDT",
            ],
        ),
        DecisionTraceStep(
            step=4,
            status=deterministic_status,
            title="Deterministic agent gate",
            summary="Specialized agents challenge the proposal for regime, manipulation, and risk-budget failures.",
            evidence=[
                f"{agent.name}: {agent.verdict} ({agent.status})"
                for agent in deterministic_agents
            ],
        ),
        DecisionTraceStep(
            step=5,
            status=committee_status,
            title="AI committee debate",
            summary=ai_committee.narrator_summary,
            evidence=[
                f"ML regime: {ai_committee.ml_regime.regime.replace('_', ' ')} at {ai_committee.ml_regime.confidence:.0%}",
                f"Anomaly risk: {ai_committee.anomaly.status} ({ai_committee.anomaly.score:.0f}/100)",
                f"Forecast stop-hit probability: {stop_hit_probability:.0%}",
                f"Backtest: {ai_committee.backtest.trades} trades, {ai_committee.backtest.win_rate:.0%} win rate",
            ],
        ),
        DecisionTraceStep(
            step=6,
            status=risk_status,
            title="Risk and stress decision",
            summary="The system checks whether the proposal survives liquidation, stop-loss, volatility, and drawdown pressure.",
            evidence=[
                f"Worst modeled PnL: {worst_stress:.1f}%",
                f"Execution route: {ai_committee.execution_plan.order_style}",
                f"Slippage cap: {ai_committee.execution_plan.max_slippage_bps:.1f} bps",
            ],
        ),
        DecisionTraceStep(
            step=7,
            status=final_status,
            title="Final audited outcome",
            summary=f"Final action is {final_action.replace('_', ' ')} with status {status}.",
            evidence=[
                "No live order is sent; this prototype only simulates paper execution.",
                "The full decision report is serialized and hashed for later verification.",
            ],
        ),
    ]


def build_decision(snapshot: MarketSnapshot) -> GuardianDecision:
    metrics = compute_metrics(snapshot)
    regime = market_regime_agent(metrics)
    proposal, strategy = strategy_agent(metrics)
    sentinel = manipulation_sentinel(metrics)
    guardian, safeguards = risk_guardian_agent(metrics, proposal, sentinel, regime)
    stresses = stress_tests(metrics, proposal)
    deterministic_agents = [regime, strategy, sentinel, guardian]

    if proposal.action == "NO_TRADE":
        final_action = "NO_TRADE"
        status = "observe"
        summary = "FairFlow recommends no trade because the strategy signal is not strong enough after review."
    elif guardian.status == "pass":
        final_action = proposal.action
        status = "approved"
        summary = f"FairFlow approves a small {proposal.action.lower()} paper order with mandatory guardrails."
    else:
        final_action = "NO_TRADE"
        status = "blocked"
        summary = "FairFlow blocks execution because one or more safety agents rejected the setup."

    committee, ai_agents, ai_blockers = build_ai_committee(
        snapshot=snapshot,
        metrics=metrics,
        proposal=proposal,
        deterministic_agents=deterministic_agents,
        stress_results=stresses,
        final_action=final_action,
        status=status,
    )
    if ai_blockers and proposal.action != "NO_TRADE":
        final_action = "NO_TRADE"
        status = "blocked"
        summary = f"FairFlow blocks execution after AI committee review: {ai_blockers[0]}"

    all_agents = [*deterministic_agents, *ai_agents]
    fairness_passport = build_fairness_passport(
        snapshot=snapshot,
        metrics=metrics,
        proposal=proposal,
        sentinel=sentinel,
        ai_committee=committee,
        status=status,
        final_action=final_action,
    )
    decision_trace = build_decision_trace(
        snapshot=snapshot,
        metrics=metrics,
        proposal=proposal,
        deterministic_agents=deterministic_agents,
        all_agents=all_agents,
        ai_committee=committee,
        stress_results=stresses,
        final_action=final_action,
        status=status,
    )
    payload = {
        "id": "",
        "symbol": snapshot.symbol,
        "category": snapshot.category,
        "scenario": snapshot.scenario,
        "source": snapshot.source,
        "generated_at": snapshot.generated_at,
        "final_action": final_action,
        "status": status,
        "summary": summary,
        "metrics": metrics,
        "proposal": proposal,
        "agents": all_agents,
        "ai_committee": committee,
        "decision_trace": decision_trace,
        "fairness_passport": fairness_passport,
        "stress_tests": stresses,
        "safeguards": safeguards,
    }
    audit_hash = _audit_hash(payload)
    payload["audit_hash"] = audit_hash
    payload["id"] = f"ffg-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{audit_hash[:8]}"
    decision = GuardianDecision(**payload)
    remember_committee_decision(
        audit_hash=decision.audit_hash,
        symbol=decision.symbol,
        status=decision.status,
        final_action=decision.final_action,
        proposal=decision.proposal,
        price=decision.metrics.price,
        generated_at=decision.generated_at,
    )
    return decision
