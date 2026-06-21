from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from statistics import median
from typing import Any

import httpx

from .models import BookLevel, Candle, MarketSnapshot, Ticker

BYBIT_BASE_URL = "https://api.bybit.com"


class BybitFetchError(RuntimeError):
    pass


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


async def _get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(path, params=params)
    response.raise_for_status()
    payload = response.json()
    if payload.get("retCode") != 0:
        raise BybitFetchError(f"Bybit returned {payload.get('retCode')}: {payload.get('retMsg')}")
    return payload


async def fetch_bybit_snapshot(symbol: str, category: str = "linear") -> MarketSnapshot:
    normalized_symbol = symbol.upper().replace("/", "")
    normalized_category = category.lower()

    async with httpx.AsyncClient(base_url=BYBIT_BASE_URL, timeout=8.0) as client:
        kline_payload = await _get_json(
            client,
            "/v5/market/kline",
            {
                "category": normalized_category,
                "symbol": normalized_symbol,
                "interval": "5",
                "limit": 96,
            },
        )
        orderbook_payload = await _get_json(
            client,
            "/v5/market/orderbook",
            {
                "category": normalized_category,
                "symbol": normalized_symbol,
                "limit": 50,
            },
        )
        ticker_payload = await _get_json(
            client,
            "/v5/market/tickers",
            {
                "category": normalized_category,
                "symbol": normalized_symbol,
            },
        )

    candles = [
        Candle(
            start_ms=int(row[0]),
            open=_to_float(row[1]),
            high=_to_float(row[2]),
            low=_to_float(row[3]),
            close=_to_float(row[4]),
            volume=_to_float(row[5]),
        )
        for row in reversed(kline_payload["result"]["list"])
    ]
    if len(candles) < 20:
        raise BybitFetchError("Bybit returned too few candles for analysis")

    book = orderbook_payload["result"]
    bids = [BookLevel(price=_to_float(level[0]), size=_to_float(level[1])) for level in book.get("b", [])]
    asks = [BookLevel(price=_to_float(level[0]), size=_to_float(level[1])) for level in book.get("a", [])]
    if not bids or not asks:
        raise BybitFetchError("Bybit returned an empty order book")

    ticker_row = ticker_payload["result"]["list"][0]
    ticker = Ticker(
        last_price=_to_float(ticker_row.get("lastPrice"), candles[-1].close),
        bid_price=_to_float(ticker_row.get("bid1Price"), bids[0].price),
        ask_price=_to_float(ticker_row.get("ask1Price"), asks[0].price),
        mark_price=_to_float(ticker_row.get("markPrice"), candles[-1].close),
        index_price=_to_float(ticker_row.get("indexPrice"), candles[-1].close),
        price_24h_pct=_to_float(ticker_row.get("price24hPcnt")) * 100,
        volume_24h=_to_float(ticker_row.get("volume24h")),
        turnover_24h=_to_float(ticker_row.get("turnover24h")),
        funding_rate=_to_float(ticker_row.get("fundingRate")),
        open_interest=_to_float(ticker_row.get("openInterest")),
    )

    return MarketSnapshot(
        symbol=normalized_symbol,
        category=normalized_category,
        scenario="live",
        source="bybit:v5-public",
        generated_at=datetime.now(UTC),
        candles=candles,
        bids=bids,
        asks=asks,
        ticker=ticker,
    )


def fallback_snapshot(symbol: str = "BTCUSDT", category: str = "linear", scenario: str = "calm") -> MarketSnapshot:
    normalized_symbol = symbol.upper().replace("/", "")
    normalized_category = category.lower()
    normalized_scenario = scenario.lower()
    if normalized_scenario not in {"calm", "volatile", "manipulated"}:
        normalized_scenario = "calm"

    symbol_profiles = {
        "BTCUSDT": {"price": 66500.0, "liquidity": 1.0, "spread": 1.0, "volume": 1.0, "vol": 0.92, "funding": 0.0},
        "ETHUSDT": {"price": 3450.0, "liquidity": 0.93, "spread": 1.08, "volume": 0.96, "vol": 1.0, "funding": 0.00001},
        "SOLUSDT": {"price": 152.0, "liquidity": 0.78, "spread": 1.22, "volume": 1.08, "vol": 1.2, "funding": 0.00002},
        "BNBUSDT": {"price": 585.0, "liquidity": 0.72, "spread": 1.28, "volume": 0.72, "vol": 1.08, "funding": 0.00001},
        "XRPUSDT": {"price": 0.62, "liquidity": 0.44, "spread": 1.72, "volume": 0.88, "vol": 1.2, "funding": 0.00003},
        "LINKUSDT": {"price": 14.8, "liquidity": 0.5, "spread": 1.5, "volume": 0.66, "vol": 1.28, "funding": 0.00003},
        "ADAUSDT": {"price": 0.45, "liquidity": 0.38, "spread": 1.86, "volume": 0.7, "vol": 1.3, "funding": 0.00002},
        "DOGEUSDT": {"price": 0.12, "liquidity": 0.28, "spread": 2.35, "volume": 0.76, "vol": 1.52, "funding": 0.00005},
    }
    profile = symbol_profiles.get(
        normalized_symbol,
        {"price": 2500.0, "liquidity": 0.62, "spread": 1.35, "volume": 0.82, "vol": 1.12, "funding": 0.00002},
    )
    base_price = profile["price"]

    now_ms = int(time.time() * 1000)
    interval_ms = 5 * 60 * 1000
    candles: list[Candle] = []
    previous_close = base_price

    for index in range(96):
        age = 95 - index
        start_ms = now_ms - age * interval_ms
        wave = math.sin(index / 6.0) + 0.45 * math.sin(index / 15.0)

        if normalized_scenario == "calm":
            drift = index * 0.00018
            shock = wave * 0.0015 * profile["vol"]
            volume_base = (650 + 35 * math.sin(index / 8.0)) * profile["volume"]
            funding_rate = 0.00008 + profile["funding"]
            spread_bps = 1.7 * profile["spread"]
        elif normalized_scenario == "volatile":
            drift = -0.006 + index * 0.00005
            shock = wave * 0.009 * profile["vol"]
            if index > 82:
                shock -= (index - 82) * 0.0027
            volume_base = (1150 + 280 * abs(math.sin(index / 4.0))) * profile["volume"]
            funding_rate = 0.00062 + profile["funding"]
            spread_bps = 9.5 * profile["spread"]
        else:
            drift = 0.002 * math.sin(index / 13.0)
            shock = wave * 0.003 * profile["vol"]
            if 72 <= index <= 78:
                shock += 0.018
            if index > 88:
                shock -= 0.014
            volume_base = (760 + (1450 if index in {73, 74, 89, 90} else 80 * abs(math.sin(index)))) * profile["volume"]
            funding_rate = -0.00072 + profile["funding"]
            spread_bps = 14.0 * profile["spread"]

        close = base_price * (1 + drift + shock)
        open_price = previous_close
        body_high = max(open_price, close)
        body_low = min(open_price, close)
        wick = 0.0018 if normalized_scenario == "calm" else 0.006
        if normalized_scenario == "manipulated" and index in {73, 74, 89}:
            wick = 0.024
        high = body_high * (1 + wick * (1 + abs(math.sin(index))))
        low = body_low * (1 - wick * (1 + abs(math.cos(index / 2.0))))
        volume = max(100.0, volume_base * (1 + 0.05 * math.sin(index / 3.0)))
        candles.append(
            Candle(
                start_ms=start_ms,
                open=round(open_price, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=round(volume, 4),
            )
        )
        previous_close = close

    latest = candles[-1].close
    spread = latest * spread_bps / 10000
    bid_start = latest - spread / 2
    ask_start = latest + spread / 2

    bids: list[BookLevel] = []
    asks: list[BookLevel] = []
    for level in range(1, 51):
        step = latest * (0.00008 + level * 0.000025)
        base_size = max(0.01, ((135000 * profile["liquidity"]) / latest) / (level ** 0.62))
        if normalized_scenario == "volatile":
            base_size *= 0.45
        if normalized_scenario == "manipulated":
            bid_multiplier = 2.6 if level <= 4 else 0.35
            ask_multiplier = 0.25 if level <= 5 else 0.7
        else:
            bid_multiplier = 1.0 + 0.08 * math.sin(level)
            ask_multiplier = 1.0 + 0.08 * math.cos(level)
        bids.append(BookLevel(price=round(bid_start - step, 4), size=round(base_size * bid_multiplier, 6)))
        asks.append(BookLevel(price=round(ask_start + step, 4), size=round(base_size * ask_multiplier, 6)))

    recent_volumes = [c.volume for c in candles[-24:]]
    volume_24h = sum(c.volume for c in candles) * 3
    open_interest = median(recent_volumes) * (34 if normalized_scenario != "volatile" else 62)
    ticker = Ticker(
        last_price=latest,
        bid_price=bids[0].price,
        ask_price=asks[0].price,
        mark_price=latest * (1 + (0.0002 if normalized_scenario == "volatile" else 0.0)),
        index_price=latest,
        price_24h_pct=((candles[-1].close / candles[0].open) - 1) * 100,
        volume_24h=volume_24h,
        turnover_24h=volume_24h * latest,
        funding_rate=funding_rate,
        open_interest=open_interest,
    )

    return MarketSnapshot(
        symbol=normalized_symbol,
        category=normalized_category,
        scenario=normalized_scenario,
        source=f"fallback:{normalized_scenario}",
        generated_at=datetime.now(UTC),
        candles=candles,
        bids=bids,
        asks=asks,
        ticker=ticker,
    )
