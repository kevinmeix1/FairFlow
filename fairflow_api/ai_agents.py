from __future__ import annotations

import math
from datetime import datetime
from statistics import median, pstdev
from typing import Literal

from .models import (
    AgentFinding,
    AnomalySignal,
    BacktestSummary,
    CalibrationMemory,
    Candle,
    CommitteeReport,
    ExecutionPlan,
    ForecastSignal,
    MLRegimeSignal,
    MarketMetrics,
    MarketSnapshot,
    StrategyProposal,
    StressResult,
)

REGIME_MODEL_VERSION = "nearest-centroid-v0.2-weak-labels"
ANOMALY_MODEL_VERSION = "robust-mad-isolation-v0.2"
COMMITTEE_MEMORY: list[dict[str, object]] = []


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
    return 100 - (100 / (1 + avg_gain / avg_loss))


def _returns(closes: list[float]) -> list[float]:
    return [
        closes[index] / closes[index - 1] - 1
        for index in range(1, len(closes))
        if closes[index - 1] != 0
    ]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    return ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)


def _mad(values: list[float]) -> float:
    if not values:
        return 1.0
    center = median(values)
    deviations = [abs(value - center) for value in values]
    return median(deviations) or 1e-9


def _candle_wick_pct(candle: Candle) -> float:
    upper = candle.high - max(candle.open, candle.close)
    lower = min(candle.open, candle.close) - candle.low
    return max(upper, lower) / candle.close * 100 if candle.close else 0.0


def _window_features(candles: list[Candle]) -> dict[str, float]:
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    returns = _returns(closes)
    recent_returns = returns[-24:] if len(returns) >= 24 else returns
    volatility = pstdev(recent_returns) * math.sqrt(12) * 100 if len(recent_returns) > 2 else 0.0
    range_pct = (max(highs) - min(lows)) / closes[-1] * 100 if closes[-1] else 0.0
    momentum_1h = _pct_change(closes[-1], closes[-13]) if len(closes) >= 13 else 0.0
    momentum_4h = _pct_change(closes[-1], closes[-49]) if len(closes) >= 49 else momentum_1h
    prior_volumes = volumes[-25:-1] if len(volumes) >= 25 else volumes[:-1]
    volume_ratio = volumes[-1] / median(prior_volumes) if prior_volumes and median(prior_volumes) else 1.0
    return {
        "volatility": volatility,
        "range": range_pct,
        "momentum_1h": momentum_1h,
        "momentum_4h": momentum_4h,
        "rsi": _rsi(closes),
        "volume_ratio": volume_ratio,
        "wick": _candle_wick_pct(candles[-1]),
    }


def _feature_rows(snapshot: MarketSnapshot) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    candles = snapshot.candles
    for end in range(24, len(candles)):
        window = candles[max(0, end - 48) : end + 1]
        rows.append(_window_features(window))
    return rows


def _regime_label(row: dict[str, float]) -> str:
    if row["volatility"] > 1.65 or row["range"] > 6.0 or row["wick"] > 1.15:
        return "high_volatility"
    if abs(row["momentum_1h"]) > 0.55 and abs(row["momentum_4h"]) > 0.95:
        return "trend"
    if row["rsi"] > 68 or row["rsi"] < 32:
        return "mean_reversion"
    if row["volume_ratio"] > 2.1 and row["wick"] > 0.7:
        return "fragile_liquidity"
    return "choppy"


def _current_regime_row(metrics: MarketMetrics) -> dict[str, float]:
    return {
        "volatility": metrics.realized_volatility_pct,
        "range": metrics.range_24h_pct,
        "momentum_1h": metrics.momentum_1h_pct,
        "momentum_4h": metrics.momentum_4h_pct,
        "rsi": metrics.rsi_14,
        "volume_ratio": metrics.latest_volume_ratio,
        "wick": metrics.latest_wick_pct,
    }


def ml_regime_classifier(snapshot: MarketSnapshot, metrics: MarketMetrics) -> tuple[MLRegimeSignal, AgentFinding]:
    rows = _feature_rows(snapshot)
    current = _current_regime_row(metrics)
    labels = ["trend", "mean_reversion", "choppy", "high_volatility", "fragile_liquidity"]
    feature_names = list(current.keys())
    if len(rows) < 8:
        probabilities = {label: 0.0 for label in labels}
        probabilities["choppy"] = 1.0
        signal = MLRegimeSignal(
            regime="choppy",
            confidence=0.35,
            probabilities=probabilities,
            top_drivers=["Insufficient live window for stable ML classification."],
            model_version=REGIME_MODEL_VERSION,
        )
        return signal, AgentFinding(
            name="ML Market Regime Classifier",
            status="watch",
            verdict="Low-sample choppy regime",
            score=35,
            rationale=signal.top_drivers,
        )

    scale = {
        name: pstdev([row[name] for row in rows]) or 1.0
        for name in feature_names
    }
    buckets: dict[str, list[dict[str, float]]] = {label: [] for label in labels}
    for row in rows:
        buckets[_regime_label(row)].append(row)

    fallback = {name: median([row[name] for row in rows]) for name in feature_names}
    centroids: dict[str, dict[str, float]] = {}
    for label in labels:
        source = buckets[label] or rows
        centroids[label] = {
            name: sum(row[name] for row in source) / len(source)
            for name in feature_names
        }
    distances: dict[str, float] = {}
    for label, centroid in centroids.items():
        distances[label] = math.sqrt(
            sum(((current[name] - centroid.get(name, fallback[name])) / scale[name]) ** 2 for name in feature_names)
        )
    raw = {label: math.exp(-distance) for label, distance in distances.items()}
    total = sum(raw.values()) or 1.0
    probabilities = {label: raw[label] / total for label in labels}
    regime = max(probabilities, key=probabilities.get)
    confidence = probabilities[regime]

    zscores = {
        name: abs((current[name] - median([row[name] for row in rows])) / scale[name])
        for name in feature_names
    }
    driver_labels = {
        "volatility": f"volatility {current['volatility']:.2f}%",
        "range": f"24h range {current['range']:.2f}%",
        "momentum_1h": f"1h momentum {current['momentum_1h']:.2f}%",
        "momentum_4h": f"4h momentum {current['momentum_4h']:.2f}%",
        "rsi": f"RSI {current['rsi']:.1f}",
        "volume_ratio": f"volume ratio {current['volume_ratio']:.2f}x",
        "wick": f"latest wick {current['wick']:.2f}%",
    }
    top_drivers = [driver_labels[name] for name, _ in sorted(zscores.items(), key=lambda item: item[1], reverse=True)[:3]]
    if metrics.liquidity_score < 45:
        regime = "fragile_liquidity"
        confidence = max(confidence, 0.72)
        top_drivers.insert(0, f"liquidity score is only {metrics.liquidity_score:.0f}/100")

    status: Literal["pass", "watch", "block"] = "pass"
    if regime in {"high_volatility", "fragile_liquidity"} and confidence > 0.52:
        status = "block" if metrics.liquidity_score < 45 or metrics.realized_volatility_pct > 2.2 else "watch"
    elif confidence < 0.42:
        status = "watch"

    signal = MLRegimeSignal(
        regime=regime,  # type: ignore[arg-type]
        confidence=_clamp(confidence, 0, 1),
        probabilities={key: round(value, 4) for key, value in probabilities.items()},
        top_drivers=top_drivers,
        model_version=REGIME_MODEL_VERSION,
    )
    return signal, AgentFinding(
        name="ML Market Regime Classifier",
        status=status,
        verdict=f"{regime.replace('_', ' ').title()} regime",
        score=_clamp(confidence * 100, 0, 100),
        rationale=[
            f"Nearest-centroid classifier predicts {regime.replace('_', ' ')} with {confidence:.0%} confidence.",
            *top_drivers,
        ],
    )


def anomaly_detection_agent(snapshot: MarketSnapshot, metrics: MarketMetrics) -> tuple[AnomalySignal, AgentFinding]:
    rows = _feature_rows(snapshot)
    vol_values = [row["volatility"] for row in rows] or [metrics.realized_volatility_pct]
    range_values = [row["range"] for row in rows] or [metrics.range_24h_pct]
    volume_values = [row["volume_ratio"] for row in rows] or [metrics.latest_volume_ratio]
    wick_values = [row["wick"] for row in rows] or [metrics.latest_wick_pct]

    checks = [
        ("volatility", metrics.realized_volatility_pct, vol_values, 8.5),
        ("range", metrics.range_24h_pct, range_values, 4.5),
        ("volume", metrics.latest_volume_ratio, volume_values, 5.5),
        ("wick", metrics.latest_wick_pct, wick_values, 7.5),
    ]
    score = 0.0
    drivers: list[str] = []
    for name, value, values, weight in checks:
        robust_z = abs(value - median(values)) / (_mad(values) * 1.4826)
        contribution = _clamp(robust_z * weight, 0, 28)
        score += contribution
        if robust_z > 2.2:
            drivers.append(f"{name} is {robust_z:.1f} robust deviations from its rolling baseline")

    market_quality_checks = [
        ("spread", metrics.spread_bps, 6, 1.8),
        ("market impact", metrics.impact_25k_bps, 8, 2.0),
        ("funding crowding", abs(metrics.funding_rate_bps), 4.5, 3.0),
        ("order-book imbalance", abs(metrics.order_book_imbalance) * 100, 32, 0.9),
    ]
    for name, value, threshold, weight in market_quality_checks:
        if value > threshold:
            score += min(22, (value - threshold) * weight)
            drivers.append(f"{name} is outside the safe execution envelope")

    score = _clamp(score, 0, 100)
    if score >= 68:
        status_text: Literal["normal", "elevated", "extreme"] = "extreme"
        finding_status: Literal["pass", "watch", "block"] = "block"
        verdict = "Extreme anomaly risk"
    elif score >= 36:
        status_text = "elevated"
        finding_status = "watch"
        verdict = "Elevated anomaly risk"
    else:
        status_text = "normal"
        finding_status = "pass"
        verdict = "Normal market structure"

    if not drivers:
        drivers.append("Rolling robust-z detector did not find abnormal volatility, volume, wick, or market-quality conditions.")

    signal = AnomalySignal(score=score, status=status_text, drivers=drivers[:5], method=ANOMALY_MODEL_VERSION)
    return signal, AgentFinding(
        name="ML Manipulation Analyst",
        status=finding_status,
        verdict=verdict,
        score=_clamp(100 - score, 0, 100),
        rationale=signal.drivers,
    )


def uncertainty_forecast_agent(snapshot: MarketSnapshot, metrics: MarketMetrics, proposal: StrategyProposal) -> tuple[ForecastSignal, AgentFinding]:
    closes = [c.close for c in snapshot.candles]
    horizon = 6
    moves: list[float] = []
    for start in range(0, max(0, len(closes) - horizon)):
        if closes[start] != 0:
            moves.append((closes[start + horizon] / closes[start] - 1) * 100)
    expected = median(moves) if moves else 0.0
    downside = _percentile(moves, 0.10)
    upside = _percentile(moves, 0.90)

    if proposal.action != "NO_TRADE" and proposal.entry_price and proposal.stop_loss:
        stop_distance = abs((proposal.entry_price - proposal.stop_loss) / proposal.entry_price * 100)
        if proposal.action == "LONG":
            adverse_hits = [move for move in moves if move <= -stop_distance]
        else:
            adverse_hits = [move for move in moves if move >= stop_distance]
        stop_probability = len(adverse_hits) / len(moves) if moves else 0.0
        direction_text = "upward" if proposal.action == "SHORT" else "downward"
        rationale = [
            f"Historical 30-minute {direction_text} stop-hit frequency is {stop_probability:.0%}.",
            f"Modeled 10th to 90th percentile move range is {downside:.2f}% to {upside:.2f}%.",
        ]
    else:
        stop_probability = _clamp(abs(downside) / 4.0 + metrics.realized_volatility_pct / 5.0, 0, 1)
        rationale = [
            "No executable setup exists, so forecast is used as context rather than an execution trigger.",
            f"Modeled 10th to 90th percentile move range is {downside:.2f}% to {upside:.2f}%.",
        ]

    confidence = _clamp(len(moves) / 70, 0.25, 0.88)
    if metrics.realized_volatility_pct > 1.8:
        confidence *= 0.82
        rationale.append("Confidence is discounted because volatility is elevated.")

    if stop_probability > 0.62:
        status: Literal["pass", "watch", "block"] = "block"
        verdict = "Stop-hit risk is too high"
    elif stop_probability > 0.38:
        status = "watch"
        verdict = "Stop-hit risk is elevated"
    else:
        status = "pass"
        verdict = "Forecast risk is acceptable"

    signal = ForecastSignal(
        horizon_minutes=30,
        expected_move_pct=expected,
        downside_risk_pct=downside,
        upside_risk_pct=upside,
        stop_loss_hit_probability=stop_probability,
        confidence=confidence,
        rationale=rationale,
    )
    return signal, AgentFinding(
        name="Uncertainty Forecast Agent",
        status=status,
        verdict=verdict,
        score=_clamp((1 - stop_probability) * 100, 0, 100),
        rationale=rationale,
    )


def backtest_agent(snapshot: MarketSnapshot) -> tuple[BacktestSummary, AgentFinding]:
    candles = snapshot.candles
    trades = 0
    wins = 0
    rejected = 0
    returns_pct: list[float] = []
    equity = 100.0
    peak = equity
    max_drawdown = 0.0

    for idx in range(24, len(candles) - 4):
        window = candles[max(0, idx - 24) : idx + 1]
        features = _window_features(window)
        if features["volatility"] > 1.65 or features["range"] > 6.0 or features["wick"] > 1.2:
            rejected += 1
            continue

        action: Literal["LONG", "SHORT", "NO_TRADE"] = "NO_TRADE"
        if features["rsi"] < 34:
            action = "LONG"
        elif features["rsi"] > 66:
            action = "SHORT"
        elif features["momentum_1h"] > 0.35 and features["volatility"] < 1.35:
            action = "LONG"
        elif features["momentum_1h"] < -0.35 and features["volatility"] < 1.35:
            action = "SHORT"

        if action == "NO_TRADE":
            continue

        entry = candles[idx].close
        exit_price = candles[idx + 4].close
        raw_return = _pct_change(exit_price, entry)
        trade_return = raw_return if action == "LONG" else -raw_return
        trades += 1
        wins += 1 if trade_return > 0 else 0
        returns_pct.append(trade_return)
        equity *= 1 + trade_return / 100
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100 if peak else 0.0)

    win_rate = wins / trades if trades else 0.0
    average_return = sum(returns_pct) / trades if trades else 0.0
    if trades < 3:
        conclusion = "Too few clean historical setups; strategy should stay conservative."
        status: Literal["pass", "watch", "block"] = "watch"
    elif win_rate < 0.30 and average_return < -0.12:
        conclusion = "Recent rolling backtest is materially weak; execution should be challenged."
        status = "block"
    elif win_rate < 0.42 or average_return < 0:
        conclusion = "Recent rolling backtest is mixed; keep size capped and require the other agents to pass."
        status = "watch"
    elif max_drawdown > 4.0:
        conclusion = "Backtest has drawdown pressure; size should be reduced."
        status = "watch"
    else:
        conclusion = "Recent rolling backtest is acceptable for a capped paper trade."
        status = "pass"

    summary = BacktestSummary(
        strategy_name="RSI + momentum with volatility rejection",
        lookback_candles=len(candles),
        trades=trades,
        rejected_setups=rejected,
        win_rate=win_rate,
        average_return_pct=average_return,
        max_drawdown_pct=max_drawdown,
        conclusion=conclusion,
    )
    return summary, AgentFinding(
        name="Backtest Agent",
        status=status,
        verdict=conclusion,
        score=_clamp((win_rate * 70) + max(0, 30 - max_drawdown * 4), 0, 100),
        rationale=[
            f"Simulated {trades} trades over {len(candles)} recent candles.",
            f"Win rate {win_rate:.0%}, average return {average_return:.2f}%, max drawdown {max_drawdown:.2f}%.",
            f"Rejected {rejected} unsafe historical setups before entry.",
        ],
    )


def execution_planner_agent(
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
    status: Literal["approved", "blocked", "observe"],
    metrics: MarketMetrics,
    proposal: StrategyProposal,
) -> tuple[ExecutionPlan, AgentFinding]:
    if status != "approved" or final_action == "NO_TRADE":
        plan = ExecutionPlan(
            order_style="none",
            side="None",
            entry_style="Execution locked by FairFlow Guardian.",
            max_slippage_bps=0,
            cooldown_seconds=90,
            time_in_force="None",
            notes=[
                "No route is produced unless the full committee and deterministic gate approve.",
                "User can refresh after cooldown to get a new decision report.",
            ],
        )
        return plan, AgentFinding(
            name="Execution Planner Agent",
            status="watch" if status == "observe" else "block",
            verdict="No executable route",
            score=72 if status == "observe" else 20,
            rationale=plan.notes,
        )

    side: Literal["Buy", "Sell", "None"] = "Buy" if final_action == "LONG" else "Sell"
    max_slippage = _clamp(max(4.0, metrics.spread_bps * 1.8 + metrics.impact_25k_bps), 4.0, 18.0)
    plan = ExecutionPlan(
        order_style="limit",
        side=side,
        entry_style="Post-only limit near mid-price; fall back to no-fill rather than chasing.",
        max_slippage_bps=max_slippage,
        cooldown_seconds=120,
        time_in_force="PostOnly",
        notes=[
            f"Route {side} with notional capped at {proposal.position_size_usdt:.0f} USDT.",
            "Attach stop loss and take profit from the approved strategy proposal.",
            "Cancel instead of crossing the book if market quality degrades before fill.",
        ],
    )
    return plan, AgentFinding(
        name="Execution Planner Agent",
        status="pass",
        verdict="Capped limit route prepared",
        score=_clamp(100 - max_slippage * 2, 0, 100),
        rationale=plan.notes,
    )


def memory_calibration_agent(
    symbol: str,
    status: Literal["approved", "blocked", "observe"],
    proposal: StrategyProposal,
) -> tuple[CalibrationMemory, AgentFinding]:
    sample = len(COMMITTEE_MEMORY)
    relevant = [item for item in COMMITTEE_MEMORY[-25:] if item.get("symbol") == symbol]
    avoided = sum(1 for item in relevant if item.get("status") in {"blocked", "observe"})
    false_positives = sum(1 for item in relevant if item.get("status") == "approved" and item.get("proposal_confidence", 0) < 0.58)
    bucket = "cold start" if sample < 5 else "warming up" if sample < 20 else "session calibrated"
    base_score = 55 if sample < 5 else 68 if sample < 20 else 78
    confidence_adjustment = (proposal.confidence - 0.5) * 28
    calibration_score = _clamp(base_score + confidence_adjustment - false_positives * 4, 0, 100)
    note = (
        "Session memory is still warming up; future decisions will compare confidence with later price outcomes."
        if sample < 5
        else "Session memory is tracking prior decisions, avoided trades, and low-confidence approvals."
    )
    memory = CalibrationMemory(
        sample_size=sample,
        confidence_bucket=bucket,
        calibration_score=calibration_score,
        recent_false_positives=false_positives,
        avoided_trade_count=avoided,
        note=note,
    )
    finding_status: Literal["pass", "watch", "block"] = "pass" if sample >= 5 else "watch"
    return memory, AgentFinding(
        name="Memory Calibration Agent",
        status=finding_status,
        verdict=bucket.title(),
        score=calibration_score,
        rationale=[
            note,
            f"Memory has {sample} prior decisions, with {avoided} avoided trades for {symbol}.",
        ],
    )


def _committee_blockers(
    proposal: StrategyProposal,
    ml_regime: MLRegimeSignal,
    anomaly: AnomalySignal,
    forecast: ForecastSignal,
    backtest: BacktestSummary,
) -> list[str]:
    if proposal.action == "NO_TRADE":
        return []
    blockers: list[str] = []
    if ml_regime.regime == "fragile_liquidity" and ml_regime.confidence > 0.62:
        blockers.append("ML regime classifier detected fragile liquidity.")
    if anomaly.status == "extreme":
        blockers.append("ML anomaly detector flagged extreme market-structure risk.")
    if forecast.stop_loss_hit_probability > 0.62:
        blockers.append("Uncertainty forecast estimates excessive stop-loss hit probability.")
    if backtest.trades >= 3 and backtest.win_rate < 0.30 and backtest.average_return_pct < -0.12:
        blockers.append("Rolling backtest is materially too weak for execution.")
    return blockers


def _narrate(
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
    status: Literal["approved", "blocked", "observe"],
    proposal: StrategyProposal,
    ml_regime: MLRegimeSignal,
    anomaly: AnomalySignal,
    forecast: ForecastSignal,
    backtest: BacktestSummary,
    blockers: list[str],
) -> tuple[str, list[str]]:
    if status == "approved":
        summary = (
            f"The AI committee approves a capped {final_action.lower()} paper route. "
            f"The ML regime model sees {ml_regime.regime.replace('_', ' ')} conditions, anomaly risk is {anomaly.status}, "
            f"and the forecasted stop-hit probability is {forecast.stop_loss_hit_probability:.0%}."
        )
    elif status == "blocked":
        reason = blockers[0] if blockers else "one or more deterministic safety agents rejected the setup."
        summary = (
            "The AI committee blocks execution. "
            f"Primary reason: {reason} The strategy proposal is preserved for audit, but no order route is produced."
        )
    else:
        summary = (
            "The AI committee recommends observation only. "
            "Market quality may be acceptable, but the strategy signal or confidence is not strong enough to justify a trade."
        )
    debate = [
        f"Strategy Agent: {proposal.thesis}",
        f"ML Regime Classifier: {ml_regime.regime.replace('_', ' ')} at {ml_regime.confidence:.0%} confidence.",
        f"Manipulation Analyst: anomaly risk is {anomaly.status} with score {anomaly.score:.0f}/100.",
        f"Forecast Agent: 30-minute downside/upside band is {forecast.downside_risk_pct:.2f}% to {forecast.upside_risk_pct:.2f}%.",
        f"Backtest Agent: {backtest.trades} trades, {backtest.win_rate:.0%} win rate, {backtest.max_drawdown_pct:.2f}% max drawdown.",
    ]
    return summary, debate


def build_ai_committee(
    snapshot: MarketSnapshot,
    metrics: MarketMetrics,
    proposal: StrategyProposal,
    deterministic_agents: list[AgentFinding],
    stress_results: list[StressResult],
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
    status: Literal["approved", "blocked", "observe"],
) -> tuple[CommitteeReport, list[AgentFinding], list[str]]:
    ml_regime, regime_finding = ml_regime_classifier(snapshot, metrics)
    anomaly, anomaly_finding = anomaly_detection_agent(snapshot, metrics)
    forecast, forecast_finding = uncertainty_forecast_agent(snapshot, metrics, proposal)
    backtest, backtest_finding = backtest_agent(snapshot)
    blockers = _committee_blockers(proposal, ml_regime, anomaly, forecast, backtest)

    adjusted_status = "blocked" if blockers and proposal.action != "NO_TRADE" else status
    adjusted_action = "NO_TRADE" if adjusted_status == "blocked" else final_action
    execution_plan, planner_finding = execution_planner_agent(adjusted_action, adjusted_status, metrics, proposal)
    calibration, calibration_finding = memory_calibration_agent(snapshot.symbol, adjusted_status, proposal)
    narrator_summary, debate = _narrate(
        adjusted_action,
        adjusted_status,
        proposal,
        ml_regime,
        anomaly,
        forecast,
        backtest,
        blockers,
    )
    narrator_finding = AgentFinding(
        name="Audit Narrator Agent",
        status="pass" if adjusted_status == "approved" else "watch" if adjusted_status == "observe" else "block",
        verdict="Decision explanation generated",
        score=85,
        rationale=[narrator_summary],
    )
    report = CommitteeReport(
        narrator_summary=narrator_summary,
        debate=debate,
        ml_regime=ml_regime,
        anomaly=anomaly,
        forecast=forecast,
        execution_plan=execution_plan,
        backtest=backtest,
        calibration=calibration,
    )
    findings = [
        regime_finding,
        anomaly_finding,
        forecast_finding,
        planner_finding,
        backtest_finding,
        calibration_finding,
        narrator_finding,
    ]
    return report, findings, blockers


def remember_committee_decision(
    *,
    audit_hash: str,
    symbol: str,
    status: Literal["approved", "blocked", "observe"],
    final_action: Literal["LONG", "SHORT", "NO_TRADE"],
    proposal: StrategyProposal,
    price: float,
    generated_at: datetime,
) -> None:
    COMMITTEE_MEMORY.append(
        {
            "audit_hash": audit_hash,
            "symbol": symbol,
            "status": status,
            "final_action": final_action,
            "proposal_confidence": proposal.confidence,
            "price": price,
            "generated_at": generated_at.isoformat(),
        }
    )
    del COMMITTEE_MEMORY[:-100]
