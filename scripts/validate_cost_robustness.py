from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median, pstdev
from typing import Literal

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fairflow_api.ai_agents import _window_features
from fairflow_api.models import Candle


SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "LINKUSDT", "ADAUSDT", "DOGEUSDT"]
BYBIT_BASE_URL = "https://api.bybit.com"
TAKER_FEE_BPS_PER_SIDE = 5.5
HOLD_CANDLES = 4
TRAIN_FRACTION = 0.60
COST_MULTIPLE_REQUIRED = 2.0
REPORT_PATH = Path("docs/experiments/2026-06-20-cost-aware-backtest.md")
IMPLEMENTATION_NOTES = [
    "First validation harness run failed before evaluation because the script did not add the repository root to sys.path; fixed before collecting results.",
]


EXTRA_MARKET_COST_BPS = {
    "BTCUSDT": 2.0,
    "ETHUSDT": 3.0,
    "SOLUSDT": 5.0,
    "BNBUSDT": 5.0,
    "XRPUSDT": 8.0,
    "LINKUSDT": 8.0,
    "ADAUSDT": 8.0,
    "DOGEUSDT": 10.0,
}


@dataclass(frozen=True)
class Trade:
    symbol: str
    timestamp_ms: int
    split: Literal["train", "validation"]
    strategy: Literal["baseline", "candidate"]
    action: Literal["LONG", "SHORT"]
    gross_return_pct: float
    net_return_pct: float
    cost_pct: float


@dataclass(frozen=True)
class SimulationResult:
    trades: list[Trade]
    rejected_by_safety: int
    rejected_by_cost_gate: int


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current / previous - 1) * 100


def _round_trip_cost_pct(symbol: str) -> float:
    round_trip_bps = TAKER_FEE_BPS_PER_SIDE * 2 + EXTRA_MARKET_COST_BPS.get(symbol, 8.0)
    return round_trip_bps / 100


def _past_median_abs_move_pct(candles: list[Candle], idx: int) -> float:
    start = max(HOLD_CANDLES, idx - 24)
    moves = [
        abs(_pct_change(candles[end].close, candles[end - HOLD_CANDLES].close))
        for end in range(start, idx + 1)
    ]
    return median(moves) if moves else 0.0


def _signal_from_features(features: dict[str, float]) -> Literal["LONG", "SHORT", "NO_TRADE"]:
    if features["rsi"] < 34:
        return "LONG"
    if features["rsi"] > 66:
        return "SHORT"
    if features["momentum_1h"] > 0.35 and features["volatility"] < 1.35:
        return "LONG"
    if features["momentum_1h"] < -0.35 and features["volatility"] < 1.35:
        return "SHORT"
    return "NO_TRADE"


def _unsafe_window(features: dict[str, float]) -> bool:
    return features["volatility"] > 1.65 or features["range"] > 6.0 or features["wick"] > 1.2


def simulate_strategy(
    *,
    symbol: str,
    candles: list[Candle],
    split_index: int,
    strategy: Literal["baseline", "candidate"],
) -> SimulationResult:
    trades: list[Trade] = []
    rejected_by_safety = 0
    rejected_by_cost_gate = 0
    cost_pct = _round_trip_cost_pct(symbol)

    for idx in range(24, len(candles) - HOLD_CANDLES):
        split: Literal["train", "validation"] = "train" if idx < split_index else "validation"
        window = candles[max(0, idx - 24) : idx + 1]
        features = _window_features(window)
        if _unsafe_window(features):
            rejected_by_safety += 1
            continue

        action = _signal_from_features(features)
        if action == "NO_TRADE":
            continue

        if strategy == "candidate":
            recent_abs_move_pct = _past_median_abs_move_pct(candles, idx)
            if recent_abs_move_pct < cost_pct * COST_MULTIPLE_REQUIRED:
                rejected_by_cost_gate += 1
                continue

        entry = candles[idx].close
        exit_price = candles[idx + HOLD_CANDLES].close
        raw_return = _pct_change(exit_price, entry)
        gross_return = raw_return if action == "LONG" else -raw_return
        net_return = gross_return - cost_pct
        trades.append(
            Trade(
                symbol=symbol,
                timestamp_ms=candles[idx].start_ms,
                split=split,
                strategy=strategy,
                action=action,
                gross_return_pct=gross_return,
                net_return_pct=net_return,
                cost_pct=cost_pct,
            )
        )

    return SimulationResult(
        trades=trades,
        rejected_by_safety=rejected_by_safety,
        rejected_by_cost_gate=rejected_by_cost_gate,
    )


def summarize(trades: list[Trade]) -> dict[str, float]:
    ordered = sorted(trades, key=lambda trade: trade.timestamp_ms)
    returns = [trade.net_return_pct for trade in ordered]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    equity = 100.0
    peak = equity
    max_drawdown = 0.0
    for value in returns:
        equity *= 1 + value / 100
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)

    profit_factor = sum(wins) / abs(sum(losses)) if losses else (math.inf if wins else 0.0)
    avg_return = sum(returns) / len(returns) if returns else 0.0
    return {
        "trades": float(len(returns)),
        "avg_net_return_pct": avg_return,
        "win_rate": len(wins) / len(returns) if returns else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown,
        "compounded_return_pct": equity - 100,
        "return_stdev_pct": pstdev(returns) if len(returns) > 1 else 0.0,
    }


def _format_metric(value: float) -> str:
    if math.isinf(value):
        return "inf"
    return f"{value:.4f}"


async def fetch_candles(symbol: str, limit: int = 1000) -> list[Candle]:
    async with httpx.AsyncClient(base_url=BYBIT_BASE_URL, timeout=12.0) as client:
        response = await client.get(
            "/v5/market/kline",
            params={"category": "linear", "symbol": symbol, "interval": "5", "limit": str(limit)},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit returned {payload.get('retCode')}: {payload.get('retMsg')}")
        rows = payload["result"]["list"]
    candles = [
        Candle(
            start_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in reversed(rows)
    ]
    if len(candles) < 200:
        raise RuntimeError(f"{symbol} returned too few candles for chronological validation: {len(candles)}")
    return candles


def _markdown_table(rows: list[tuple[str, dict[str, float]]]) -> str:
    lines = [
        "| Strategy | Trades | Avg net return | Win rate | Profit factor | Max drawdown | Compounded return |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    str(int(metrics["trades"])),
                    f"{metrics['avg_net_return_pct']:.4f}%",
                    f"{metrics['win_rate']:.2%}",
                    _format_metric(metrics["profit_factor"]),
                    f"{metrics['max_drawdown_pct']:.4f}%",
                    f"{metrics['compounded_return_pct']:.4f}%",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_report(
    *,
    fetched_at: datetime,
    per_symbol_counts: dict[str, int],
    train_rows: list[tuple[str, dict[str, float]]],
    validation_rows: list[tuple[str, dict[str, float]]],
    baseline_rejections: int,
    candidate_safety_rejections: int,
    candidate_cost_rejections: int,
    decision: str,
    criteria: dict[str, bool],
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": fetched_at.isoformat(),
        "symbols": SYMBOLS,
        "per_symbol_candles": per_symbol_counts,
        "cost_model": {
            "taker_fee_bps_per_side": TAKER_FEE_BPS_PER_SIDE,
            "extra_market_cost_bps": EXTRA_MARKET_COST_BPS,
            "candidate_required_recent_move_multiple": COST_MULTIPLE_REQUIRED,
        },
        "train": {name: metrics for name, metrics in train_rows},
        "validation": {name: metrics for name, metrics in validation_rows},
        "criteria": criteria,
        "decision": decision,
    }
    content = f"""# Experiment: Cost-Aware Backtest Gate

Date: {fetched_at.date().isoformat()}

## Pre-Registered Hypothesis

H1: The existing RSI + momentum rolling backtest is too optimistic because it evaluates gross 20-minute returns. A cost-aware candidate that subtracts round-trip trading costs and skips setups when recent 20-minute movement is too small to clear those costs will improve out-of-sample net robustness.

## Success Criteria

Keep the candidate only if chronological holdout validation shows:

1. OOS net average return per trade improves by at least 5 bps versus unchanged baseline.
2. OOS max drawdown is no worse than baseline.
3. OOS profit factor is at least as good as baseline.
4. Candidate keeps at least 30% of baseline OOS trades and at least 20 OOS trades total.

## Data And Leakage Controls

- Source: Bybit public 5-minute linear perpetual candles.
- Symbols: {", ".join(SYMBOLS)}.
- Split: first {TRAIN_FRACTION:.0%} of each symbol is development context, final {1 - TRAIN_FRACTION:.0%} is holdout validation.
- Candidate rule uses only candles available at or before entry.
- Exit return uses the next {HOLD_CANDLES} candles only as the validation label.
- No thresholds were changed after seeing validation results.

## Trading Cost Model

- Taker fee: {TAKER_FEE_BPS_PER_SIDE:.1f} bps per side.
- Extra round-trip spread/slippage bps by symbol: `{json.dumps(EXTRA_MARKET_COST_BPS, sort_keys=True)}`.
- Candidate rejects a setup unless the trailing median absolute {HOLD_CANDLES}-candle move is at least `{COST_MULTIPLE_REQUIRED:.1f}x` the estimated round-trip cost.

## In-Sample Development Context

{_markdown_table(train_rows)}

## Out-Of-Sample Holdout

{_markdown_table(validation_rows)}

## Rejections

- Baseline safety rejections: {baseline_rejections}
- Candidate safety rejections: {candidate_safety_rejections}
- Candidate cost-gate rejections: {candidate_cost_rejections}

## Implementation Notes And Failures

{chr(10).join(f"- {note}" for note in IMPLEMENTATION_NOTES)}

## Criteria Result

{chr(10).join(f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in criteria.items())}

## Decision

**{decision.upper()}**

## Machine-Readable Results

```json
{json.dumps(payload, indent=2, sort_keys=True)}
```
"""
    REPORT_PATH.write_text(content)


async def main() -> int:
    fetched_at = datetime.now(UTC)
    all_baseline: list[Trade] = []
    all_candidate: list[Trade] = []
    per_symbol_counts: dict[str, int] = {}
    baseline_safety_rejections = 0
    candidate_safety_rejections = 0
    candidate_cost_rejections = 0

    for symbol in SYMBOLS:
        candles = await fetch_candles(symbol)
        per_symbol_counts[symbol] = len(candles)
        split_index = int(len(candles) * TRAIN_FRACTION)
        baseline = simulate_strategy(symbol=symbol, candles=candles, split_index=split_index, strategy="baseline")
        candidate = simulate_strategy(symbol=symbol, candles=candles, split_index=split_index, strategy="candidate")
        all_baseline.extend(baseline.trades)
        all_candidate.extend(candidate.trades)
        baseline_safety_rejections += baseline.rejected_by_safety
        candidate_safety_rejections += candidate.rejected_by_safety
        candidate_cost_rejections += candidate.rejected_by_cost_gate

    train_baseline = summarize([trade for trade in all_baseline if trade.split == "train"])
    train_candidate = summarize([trade for trade in all_candidate if trade.split == "train"])
    validation_baseline = summarize([trade for trade in all_baseline if trade.split == "validation"])
    validation_candidate = summarize([trade for trade in all_candidate if trade.split == "validation"])

    baseline_validation_trades = validation_baseline["trades"]
    candidate_validation_trades = validation_candidate["trades"]
    criteria = {
        "avg_net_return_improves_by_5_bps": (
            validation_candidate["avg_net_return_pct"] >= validation_baseline["avg_net_return_pct"] + 0.05
        ),
        "max_drawdown_no_worse": validation_candidate["max_drawdown_pct"] <= validation_baseline["max_drawdown_pct"],
        "profit_factor_no_worse": validation_candidate["profit_factor"] >= validation_baseline["profit_factor"],
        "keeps_minimum_trade_count": (
            candidate_validation_trades >= 20
            and (candidate_validation_trades / baseline_validation_trades if baseline_validation_trades else 0) >= 0.30
        ),
    }
    decision = "keep" if all(criteria.values()) else "reject"

    train_rows = [("unchanged_baseline", train_baseline), ("cost_aware_candidate", train_candidate)]
    validation_rows = [("unchanged_baseline", validation_baseline), ("cost_aware_candidate", validation_candidate)]
    write_report(
        fetched_at=fetched_at,
        per_symbol_counts=per_symbol_counts,
        train_rows=train_rows,
        validation_rows=validation_rows,
        baseline_rejections=baseline_safety_rejections,
        candidate_safety_rejections=candidate_safety_rejections,
        candidate_cost_rejections=candidate_cost_rejections,
        decision=decision,
        criteria=criteria,
    )

    print(f"wrote {REPORT_PATH}")
    print(f"decision={decision}")
    print("validation_baseline", json.dumps(validation_baseline, sort_keys=True))
    print("validation_candidate", json.dumps(validation_candidate, sort_keys=True))
    print("criteria", json.dumps(criteria, sort_keys=True))
    return 0 if decision == "keep" else 2


if __name__ == "__main__":
    import asyncio
    import sys

    sys.exit(asyncio.run(main()))
