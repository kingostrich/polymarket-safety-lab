from __future__ import annotations

import csv
import json
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


@dataclass(frozen=True)
class CollectedMarket:
    id: str
    question: str
    closed_time: str
    resolved_outcome: str
    yes_token_id: str
    no_token_id: str
    final_yes_price: float
    final_no_price: float
    volume: float
    liquidity: float
    fee_type: str
    fees_enabled: bool
    order_min_size: float
    order_tick_size: float


@dataclass(frozen=True)
class PricePoint:
    market_id: str
    token_id: str
    side: str
    timestamp: int
    price: float


def fetch_json(url: str, params: dict[str, Any] | None = None, retries: int = 3) -> Any:
    full_url = f"{url}?{urlencode(params)}" if params else url
    last_error: Exception | None = None
    context = ssl_context()
    for attempt in range(retries):
        try:
            request = Request(full_url, headers={"User-Agent": "polymarket-backtest-research/0.1"})
            with urlopen(request, timeout=30, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failure path
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {full_url}: {last_error}")


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return json.loads(value)


def as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def resolved_outcome(outcome_prices: list[Any]) -> str | None:
    if len(outcome_prices) != 2:
        return None
    yes_price = float(outcome_prices[0])
    no_price = float(outcome_prices[1])
    if yes_price >= 0.999 and no_price <= 0.001:
        return "YES"
    if no_price >= 0.999 and yes_price <= 0.001:
        return "NO"
    return None


def collect_closed_binary_markets(target_count: int = 30, page_limit: int = 100, max_pages: int = 10) -> list[CollectedMarket]:
    markets: list[CollectedMarket] = []
    seen: set[str] = set()
    for page in range(max_pages):
        rows = fetch_json(
            f"{GAMMA_API}/markets",
            {
                "active": "false",
                "closed": "true",
                "enableOrderBook": "true",
                "limit": page_limit,
                "offset": page * page_limit,
                "order": "closedTime",
                "ascending": "false",
            },
        )
        if not rows:
            break
        for row in rows:
            market_id = str(row.get("id", ""))
            if not market_id or market_id in seen:
                continue
            seen.add(market_id)
            outcomes = parse_json_list(row.get("outcomes"))
            if outcomes != ["Yes", "No"]:
                continue
            if row.get("negRisk") is True:
                continue
            prices = parse_json_list(row.get("outcomePrices"))
            token_ids = parse_json_list(row.get("clobTokenIds"))
            outcome = resolved_outcome(prices)
            if outcome is None or len(token_ids) != 2:
                continue
            markets.append(
                CollectedMarket(
                    id=market_id,
                    question=row.get("question") or "",
                    closed_time=row.get("closedTime") or "",
                    resolved_outcome=outcome,
                    yes_token_id=str(token_ids[0]),
                    no_token_id=str(token_ids[1]),
                    final_yes_price=float(prices[0]),
                    final_no_price=float(prices[1]),
                    volume=as_float(row.get("volumeNum")),
                    liquidity=as_float(row.get("liquidityNum")),
                    fee_type=row.get("feeType") or "",
                    fees_enabled=bool(row.get("feesEnabled")),
                    order_min_size=as_float(row.get("orderMinSize")),
                    order_tick_size=as_float(row.get("orderPriceMinTickSize")),
                )
            )
            if len(markets) >= target_count:
                return markets
    return markets


def collect_price_history(
    market: CollectedMarket,
    interval: str = "1d",
    fidelity: int = 60,
    sleep_seconds: float = 0.05,
) -> list[PricePoint]:
    points: list[PricePoint] = []
    for side, token_id in (("YES", market.yes_token_id), ("NO", market.no_token_id)):
        data = fetch_json(
            f"{CLOB_API}/prices-history",
            {"market": token_id, "interval": interval, "fidelity": fidelity},
        )
        for row in data.get("history", []):
            points.append(
                PricePoint(
                    market_id=market.id,
                    token_id=token_id,
                    side=side,
                    timestamp=int(row["t"]),
                    price=float(row["p"]),
                )
            )
        time.sleep(sleep_seconds)
    return points


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_neutral_snapshots(markets: list[CollectedMarket], price_points: list[PricePoint]) -> list[dict[str, Any]]:
    by_market_side: dict[tuple[str, str], dict[int, float]] = {}
    for point in price_points:
        by_market_side.setdefault((point.market_id, point.side), {})[point.timestamp] = point.price

    rows: list[dict[str, Any]] = []
    market_by_id = {market.id: market for market in markets}
    for market in markets:
        yes_series = by_market_side.get((market.id, "YES"), {})
        no_series = by_market_side.get((market.id, "NO"), {})
        timestamps = sorted(yes_series)
        for index, ts in enumerate(timestamps):
            yes_price = yes_series[ts]
            no_price = no_series.get(ts, max(0.0, min(1.0, 1.0 - yes_price)))
            is_last = index == len(timestamps) - 1
            rows.append(
                {
                    "timestamp": datetime.fromtimestamp(ts, UTC).isoformat(),
                    "market_id": market.id,
                    "question": market.question,
                    "yes_price": f"{yes_price:.6f}",
                    "no_price": f"{no_price:.6f}",
                    "fair_yes": f"{yes_price:.6f}",
                    "liquidity": f"{market.liquidity:.6f}",
                    "volume_24h": f"{market.volume:.6f}",
                    "resolved_outcome": market_by_id[market.id].resolved_outcome if is_last else "",
                    "fee_rate": "0.00",
                }
            )
    return sorted(rows, key=lambda row: (row["timestamp"], row["market_id"]))


def collect_historical_dataset(
    out_dir: Path,
    markets_count: int = 30,
    interval: str = "1d",
    fidelity: int = 60,
    max_pages: int = 10,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    markets = collect_closed_binary_markets(target_count=markets_count, max_pages=max_pages)
    all_points: list[PricePoint] = []
    history_counts: dict[str, int] = {}
    for market in markets:
        points = collect_price_history(market, interval=interval, fidelity=fidelity)
        all_points.extend(points)
        history_counts[market.id] = len([point for point in points if point.side == "YES"])

    markets_with_history = [market for market in markets if history_counts.get(market.id, 0) > 0]
    market_ids_with_history = {market.id for market in markets_with_history}
    all_points = [point for point in all_points if point.market_id in market_ids_with_history]
    snapshots = build_neutral_snapshots(markets_with_history, all_points)

    write_csv(
        out_dir / "markets_closed_binary.csv",
        [asdict(market) for market in markets_with_history],
        list(asdict(markets_with_history[0]).keys()) if markets_with_history else [],
    )
    write_csv(
        out_dir / "token_price_history.csv",
        [asdict(point) for point in all_points],
        list(asdict(all_points[0]).keys()) if all_points else ["market_id", "token_id", "side", "timestamp", "price"],
    )
    write_csv(
        out_dir / "snapshots_neutral.csv",
        snapshots,
        [
            "timestamp",
            "market_id",
            "question",
            "yes_price",
            "no_price",
            "fair_yes",
            "liquidity",
            "volume_24h",
            "resolved_outcome",
            "fee_rate",
        ],
    )
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "markets_requested": markets_count,
        "markets_collected": len(markets),
        "markets_with_history": len(markets_with_history),
        "price_points": len(all_points),
        "snapshots": len(snapshots),
        "interval": interval,
        "fidelity": fidelity,
        "fair_value_mode": "neutral_market_price",
        "note": "fair_yes equals observed YES price; use this dataset to verify ingestion/backtest plumbing, not strategy alpha.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest
