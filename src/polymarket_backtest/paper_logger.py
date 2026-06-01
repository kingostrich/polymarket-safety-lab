from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collectors import CLOB_API, GAMMA_API, as_float, fetch_json, parse_json_list
from .models import MarketSnapshot
from .strategy import build_signal


@dataclass(frozen=True)
class BookSummary:
    best_bid: float
    best_ask: float
    bid_size_at_best: float
    ask_size_at_best: float
    bid_depth_top3: float
    ask_depth_top3: float
    bid_levels: int
    ask_levels: int


@dataclass(frozen=True)
class PaperSignalRecord:
    logged_at: str
    market_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    yes_depth_top3: float
    no_depth_top3: float
    yes_bid_depth_top3: float
    yes_ask_depth_top3: float
    no_bid_depth_top3: float
    no_ask_depth_top3: float
    yes_bid_levels: int
    yes_ask_levels: int
    no_bid_levels: int
    no_ask_levels: int
    gamma_yes_price: float
    fair_yes: float
    edge_yes: float
    edge_no: float
    signal_side: str
    signal_fraction: float
    action: str
    skip_reason: str
    volume_24h: float
    liquidity: float
    spread: float
    neg_risk: bool
    fee_type: str
    fees_enabled: bool
    gamma_fetched_at: str
    yes_book_fetched_at: str
    no_book_fetched_at: str
    yes_book_latency_ms: float
    no_book_latency_ms: float


def _levels(book: dict[str, Any], side: str) -> list[dict[str, float]]:
    rows = book.get(side, []) or []
    parsed = [{"price": float(row["price"]), "size": float(row["size"])} for row in rows]
    reverse = side == "bids"
    return sorted(parsed, key=lambda row: row["price"], reverse=reverse)


def summarize_book(token_id: str) -> tuple[BookSummary, str, float]:
    started = time.perf_counter()
    book = fetch_json(f"{CLOB_API}/book", {"token_id": token_id})
    fetched_at = datetime.now(UTC).isoformat()
    latency_ms = (time.perf_counter() - started) * 1000.0
    bids = _levels(book, "bids")
    asks = _levels(book, "asks")
    best_bid = bids[0] if bids else {"price": 0.0, "size": 0.0}
    best_ask = asks[0] if asks else {"price": 0.0, "size": 0.0}
    return (
        BookSummary(
            best_bid=best_bid["price"],
            best_ask=best_ask["price"],
            bid_size_at_best=best_bid["size"],
            ask_size_at_best=best_ask["size"],
            bid_depth_top3=sum(row["size"] for row in bids[:3]),
            ask_depth_top3=sum(row["size"] for row in asks[:3]),
            bid_levels=len(bids),
            ask_levels=len(asks),
        ),
        fetched_at,
        latency_ms,
    )


def fetch_active_binary_markets(limit: int, exclude_neg_risk: bool = True) -> tuple[list[dict[str, Any]], str]:
    rows = fetch_json(
        f"{GAMMA_API}/markets",
        {
            "active": "true",
            "closed": "false",
            "enableOrderBook": "true",
            "limit": limit * 3,
            "order": "volume24hr",
            "ascending": "false",
        },
    )
    gamma_fetched_at = datetime.now(UTC).isoformat()
    markets: list[dict[str, Any]] = []
    for row in rows:
        if row.get("acceptingOrders") is not True:
            continue
        if parse_json_list(row.get("outcomes")) != ["Yes", "No"]:
            continue
        if exclude_neg_risk and row.get("negRisk") is True:
            continue
        if len(parse_json_list(row.get("clobTokenIds"))) != 2:
            continue
        markets.append(row)
        if len(markets) >= limit:
            return markets, gamma_fetched_at
    return markets, gamma_fetched_at


def neutral_fair_yes(row: dict[str, Any], yes_book: BookSummary) -> float:
    prices = parse_json_list(row.get("outcomePrices"))
    if len(prices) >= 1:
        return max(0.0, min(1.0, float(prices[0])))
    if yes_book.best_bid > 0 and yes_book.best_ask > 0:
        return (yes_book.best_bid + yes_book.best_ask) / 2.0
    return 0.5


def build_record(
    row: dict[str, Any],
    logged_at: str,
    edge_threshold: float,
    gamma_fetched_at: str,
    book_sleep_seconds: float,
) -> PaperSignalRecord:
    token_ids = parse_json_list(row.get("clobTokenIds"))
    yes_token_id = str(token_ids[0])
    no_token_id = str(token_ids[1])
    yes_book, yes_book_fetched_at, yes_book_latency_ms = summarize_book(yes_token_id)
    time.sleep(book_sleep_seconds)
    no_book, no_book_fetched_at, no_book_latency_ms = summarize_book(no_token_id)
    time.sleep(book_sleep_seconds)
    fair_yes = neutral_fair_yes(row, yes_book)
    yes_ask = yes_book.best_ask or as_float(parse_json_list(row.get("outcomePrices"))[0])
    no_ask = no_book.best_ask or as_float(parse_json_list(row.get("outcomePrices"))[1])
    snapshot = MarketSnapshot(
        timestamp=datetime.fromisoformat(logged_at),
        market_id=str(row["id"]),
        question=row.get("question") or "",
        yes_price=yes_ask,
        no_price=no_ask,
        fair_yes=fair_yes,
        liquidity=as_float(row.get("liquidityNum")),
        volume_24h=as_float(row.get("volume24hr")),
        fee_rate=0.0,
    )
    signal = build_signal(snapshot, edge_threshold=edge_threshold)
    edge_yes = fair_yes - yes_ask
    edge_no = (1.0 - fair_yes) - no_ask

    skip_reason = ""
    action = "paper_signal" if signal else "skip"
    if signal is None:
        if yes_ask <= 0 or no_ask <= 0:
            skip_reason = "missing_executable_ask"
        elif max(edge_yes, edge_no) < edge_threshold:
            skip_reason = "edge_below_threshold"
        else:
            skip_reason = "kelly_fraction_zero"

    return PaperSignalRecord(
        logged_at=logged_at,
        market_id=str(row["id"]),
        question=row.get("question") or "",
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_bid=yes_book.best_bid,
        yes_ask=yes_ask,
        no_bid=no_book.best_bid,
        no_ask=no_ask,
        yes_depth_top3=yes_book.ask_depth_top3,
        no_depth_top3=no_book.ask_depth_top3,
        yes_bid_depth_top3=yes_book.bid_depth_top3,
        yes_ask_depth_top3=yes_book.ask_depth_top3,
        no_bid_depth_top3=no_book.bid_depth_top3,
        no_ask_depth_top3=no_book.ask_depth_top3,
        yes_bid_levels=yes_book.bid_levels,
        yes_ask_levels=yes_book.ask_levels,
        no_bid_levels=no_book.bid_levels,
        no_ask_levels=no_book.ask_levels,
        gamma_yes_price=fair_yes,
        fair_yes=fair_yes,
        edge_yes=edge_yes,
        edge_no=edge_no,
        signal_side=signal.side.value if signal else "",
        signal_fraction=signal.fraction if signal else 0.0,
        action=action,
        skip_reason=skip_reason,
        volume_24h=as_float(row.get("volume24hr")),
        liquidity=as_float(row.get("liquidityNum")),
        spread=as_float(row.get("spread")),
        neg_risk=bool(row.get("negRisk")),
        fee_type=row.get("feeType") or "",
        fees_enabled=bool(row.get("feesEnabled")),
        gamma_fetched_at=gamma_fetched_at,
        yes_book_fetched_at=yes_book_fetched_at,
        no_book_fetched_at=no_book_fetched_at,
        yes_book_latency_ms=yes_book_latency_ms,
        no_book_latency_ms=no_book_latency_ms,
    )


def atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)


def atomic_copy_text(source: Path, destination: Path) -> None:
    atomic_write_text(destination, source.read_text())


def write_records(records: list[PaperSignalRecord], out_dir: Path, logged_at: str) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(logged_at).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out_dir / f"paper_signals_{stamp}.csv"
    jsonl_path = out_dir / f"paper_signals_{stamp}.jsonl"
    rows = [asdict(record) for record in records]
    if rows:
        tmp_csv_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
        with tmp_csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_csv_path, csv_path)
        jsonl_content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        atomic_write_text(jsonl_path, jsonl_content)
    latest_csv = out_dir / "latest_paper_signals.csv"
    latest_jsonl = out_dir / "latest_paper_signals.jsonl"
    if rows:
        atomic_copy_text(csv_path, latest_csv)
        atomic_copy_text(jsonl_path, latest_jsonl)
    manifest = {
        "logged_at": logged_at,
        "records": len(records),
        "signals": sum(1 for record in records if record.action == "paper_signal"),
        "skips": sum(1 for record in records if record.action == "skip"),
        "csv_path": str(csv_path),
        "jsonl_path": str(jsonl_path),
        "forecast_mode": "neutral_market_implied",
        "note": "No orders were placed. fair_yes is placeholder market-implied probability for forward logging plumbing.",
    }
    atomic_write_text(out_dir / "latest_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def run_paper_log(
    out_dir: Path,
    limit: int,
    edge_threshold: float,
    exclude_neg_risk: bool = True,
    book_sleep_seconds: float = 0.05,
) -> dict[str, Any]:
    logged_at = datetime.now(UTC).isoformat()
    markets, gamma_fetched_at = fetch_active_binary_markets(limit=limit, exclude_neg_risk=exclude_neg_risk)
    records = [
        build_record(
            row,
            logged_at=logged_at,
            edge_threshold=edge_threshold,
            gamma_fetched_at=gamma_fetched_at,
            book_sleep_seconds=book_sleep_seconds,
        )
        for row in markets
    ]
    return write_records(records, out_dir=out_dir, logged_at=logged_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Log one forward paper-trading snapshot without placing orders.")
    parser.add_argument("--out-dir", default="data/paper/live_snapshots")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--book-sleep-seconds", type=float, default=0.05)
    parser.add_argument("--include-neg-risk", action="store_true")
    args = parser.parse_args()
    manifest = run_paper_log(
        out_dir=Path(args.out_dir),
        limit=args.limit,
        edge_threshold=args.edge_threshold,
        exclude_neg_risk=not args.include_neg_risk,
        book_sleep_seconds=args.book_sleep_seconds,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
