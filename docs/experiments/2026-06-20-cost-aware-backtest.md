# Experiment: Cost-Aware Backtest Gate

Date: 2026-06-20

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
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT, ADAUSDT, DOGEUSDT.
- Split: first 60% of each symbol is development context, final 40% is holdout validation.
- Candidate rule uses only candles available at or before entry.
- Exit return uses the next 4 candles only as the validation label.
- No thresholds were changed after seeing validation results.

## Trading Cost Model

- Taker fee: 5.5 bps per side.
- Extra round-trip spread/slippage bps by symbol: `{"ADAUSDT": 8.0, "BNBUSDT": 5.0, "BTCUSDT": 2.0, "DOGEUSDT": 10.0, "ETHUSDT": 3.0, "LINKUSDT": 8.0, "SOLUSDT": 5.0, "XRPUSDT": 8.0}`.
- Candidate rejects a setup unless the trailing median absolute 4-candle move is at least `2.0x` the estimated round-trip cost.

## In-Sample Development Context

| Strategy | Trades | Avg net return | Win rate | Profit factor | Max drawdown | Compounded return |
|---|---:|---:|---:|---:|---:|---:|
| unchanged_baseline | 2337 | -0.1757% | 26.23% | 0.2780 | 98.3954% | -98.3881% |
| cost_aware_candidate | 270 | -0.2012% | 31.85% | 0.2739 | 42.3325% | -42.1310% |

## Out-Of-Sample Holdout

| Strategy | Trades | Avg net return | Win rate | Profit factor | Max drawdown | Compounded return |
|---|---:|---:|---:|---:|---:|---:|
| unchanged_baseline | 1294 | -0.1668% | 25.43% | 0.2430 | 88.5463% | -88.5463% |
| cost_aware_candidate | 36 | -0.0796% | 47.22% | 0.5038 | 4.1659% | -2.8406% |

## Rejections

- Baseline safety rejections: 90
- Candidate safety rejections: 90
- Candidate cost-gate rejections: 3325

## Implementation Notes And Failures

- First validation harness run failed before evaluation because the script did not add the repository root to sys.path; fixed before collecting results.

## Criteria Result

- avg_net_return_improves_by_5_bps: PASS
- max_drawdown_no_worse: PASS
- profit_factor_no_worse: PASS
- keeps_minimum_trade_count: FAIL

## Decision

**REJECT**

## Machine-Readable Results

```json
{
  "cost_model": {
    "candidate_required_recent_move_multiple": 2.0,
    "extra_market_cost_bps": {
      "ADAUSDT": 8.0,
      "BNBUSDT": 5.0,
      "BTCUSDT": 2.0,
      "DOGEUSDT": 10.0,
      "ETHUSDT": 3.0,
      "LINKUSDT": 8.0,
      "SOLUSDT": 5.0,
      "XRPUSDT": 8.0
    },
    "taker_fee_bps_per_side": 5.5
  },
  "criteria": {
    "avg_net_return_improves_by_5_bps": true,
    "keeps_minimum_trade_count": false,
    "max_drawdown_no_worse": true,
    "profit_factor_no_worse": true
  },
  "decision": "reject",
  "fetched_at": "2026-06-20T15:10:59.273557+00:00",
  "per_symbol_candles": {
    "ADAUSDT": 1000,
    "BNBUSDT": 1000,
    "BTCUSDT": 1000,
    "DOGEUSDT": 1000,
    "ETHUSDT": 1000,
    "LINKUSDT": 1000,
    "SOLUSDT": 1000,
    "XRPUSDT": 1000
  },
  "symbols": [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "LINKUSDT",
    "ADAUSDT",
    "DOGEUSDT"
  ],
  "train": {
    "cost_aware_candidate": {
      "avg_net_return_pct": -0.2011707245460694,
      "compounded_return_pct": -42.13101337679226,
      "max_drawdown_pct": 42.332542946048605,
      "profit_factor": 0.27386619774614995,
      "return_stdev_pct": 0.49139453522154786,
      "trades": 270.0,
      "win_rate": 0.31851851851851853
    },
    "unchanged_baseline": {
      "avg_net_return_pct": -0.1757473998516398,
      "compounded_return_pct": -98.38812347678021,
      "max_drawdown_pct": 98.39542842838944,
      "profit_factor": 0.27799335920041224,
      "return_stdev_pct": 0.3800447939432552,
      "trades": 2337.0,
      "win_rate": 0.26230209670517757
    }
  },
  "validation": {
    "cost_aware_candidate": {
      "avg_net_return_pct": -0.0796223313044894,
      "compounded_return_pct": -2.8405899466134485,
      "max_drawdown_pct": 4.16585107192684,
      "profit_factor": 0.5038126215877691,
      "return_stdev_pct": 0.2802733323730962,
      "trades": 36.0,
      "win_rate": 0.4722222222222222
    },
    "unchanged_baseline": {
      "avg_net_return_pct": -0.16680182387050493,
      "compounded_return_pct": -88.54634569396316,
      "max_drawdown_pct": 88.54634569396316,
      "profit_factor": 0.24299923308087606,
      "return_stdev_pct": 0.31988363900237027,
      "trades": 1294.0,
      "win_rate": 0.2542503863987635
    }
  }
}
```
