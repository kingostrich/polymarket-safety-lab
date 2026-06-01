from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenPositionEvent:
    timestamp: str
    market_id: str
    side: str
    cash_after: float
    equity_after: float
    edge: float
    fraction: float
    cost: float
    quoted_price: float
    entry_price: float
    slippage_cost: float


@dataclass(frozen=True)
class SurvivalEventSummary:
    events_path: str
    total_events: int
    event_counts: dict[str, int]
    positions_opened: int
    positions_closed_events: int
    skip_existing_position_events: int
    unique_open_markets: int
    reopened_markets: int
    repeated_open_events: int
    first_open_timestamp: str
    last_event_timestamp: str
    open_notional: float
    open_notional_to_min_equity: float
    mean_open_edge: float
    mean_entry_price: float
    min_equity: float
    final_event_equity: float
    note: str


def safe_float(value: str | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_detail(detail: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in detail.split(";"):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key] = value
    return parsed


def load_events(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_events(events_path: Path) -> tuple[SurvivalEventSummary, list[OpenPositionEvent]]:
    events = load_events(events_path)
    counts = Counter(row.get("event_type", "") for row in events)
    open_events: list[OpenPositionEvent] = []
    for row in events:
        if row.get("event_type") != "OPEN_POSITION":
            continue
        detail = parse_detail(row.get("detail", ""))
        open_events.append(
            OpenPositionEvent(
                timestamp=row.get("timestamp", ""),
                market_id=row.get("market_id", ""),
                side=row.get("side", ""),
                cash_after=safe_float(row.get("cash")),
                equity_after=safe_float(row.get("equity")),
                edge=safe_float(detail.get("edge")),
                fraction=safe_float(detail.get("fraction")),
                cost=safe_float(detail.get("cost")),
                quoted_price=safe_float(detail.get("quoted_price")),
                entry_price=safe_float(detail.get("entry_price")),
                slippage_cost=safe_float(detail.get("slippage_cost")),
            )
        )

    equities = [safe_float(row.get("equity")) for row in events if row.get("equity") not in (None, "")]
    open_notional = sum(event.cost for event in open_events)
    min_equity = min(equities) if equities else 0.0
    open_market_counts = Counter(event.market_id for event in open_events)
    repeated_open_events = sum(count - 1 for count in open_market_counts.values() if count > 1)
    summary = SurvivalEventSummary(
        events_path=str(events_path),
        total_events=len(events),
        event_counts=dict(sorted(counts.items())),
        positions_opened=len(open_events),
        positions_closed_events=sum(counts[event] for event in ("EXIT_POSITION", "PARTIAL_EXIT_POSITION", "SETTLE_POSITION")),
        skip_existing_position_events=counts.get("SKIP_EXISTING_POSITION", 0),
        unique_open_markets=len(open_market_counts),
        reopened_markets=sum(1 for count in open_market_counts.values() if count > 1),
        repeated_open_events=repeated_open_events,
        first_open_timestamp=open_events[0].timestamp if open_events else "",
        last_event_timestamp=events[-1].get("timestamp", "") if events else "",
        open_notional=open_notional,
        open_notional_to_min_equity=open_notional / min_equity if min_equity > 0 else 0.0,
        mean_open_edge=sum(event.edge for event in open_events) / len(open_events) if open_events else 0.0,
        mean_entry_price=sum(event.entry_price for event in open_events) / len(open_events) if open_events else 0.0,
        min_equity=min_equity,
        final_event_equity=equities[-1] if equities else 0.0,
        note=(
            "Event-level replay summary only. Open positions are mark-to-market exposure, "
            "not settled market P&L."
        ),
    )
    return summary, open_events


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def write_outputs(summary: SurvivalEventSummary, open_events: list[OpenPositionEvent], out_json: Path, out_csv: Path, out_md: Path) -> None:
    atomic_write_text(out_json, json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp_csv.open("w", newline="") as handle:
        fieldnames = list(OpenPositionEvent.__dataclass_fields__.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(event) for event in open_events)
    os.replace(tmp_csv, out_csv)

    lines = [
        "# Survival Event Summary",
        "",
        "This summarizes replay events for exposure debugging only. It is not investment advice.",
        "",
        f"- Events: {summary.total_events}",
        f"- Event counts: {summary.event_counts}",
        f"- Positions opened: {summary.positions_opened}",
        f"- Position-close/settlement events: {summary.positions_closed_events}",
        f"- Existing-position skips: {summary.skip_existing_position_events}",
        f"- Unique opened markets: {summary.unique_open_markets}",
        f"- Markets reopened after exit: {summary.reopened_markets}",
        f"- Repeated open events after prior opens: {summary.repeated_open_events}",
        f"- Gross opened notional: {summary.open_notional:.4f}",
        f"- Gross opened notional / min event equity: {summary.open_notional_to_min_equity:.2%}",
        f"- Mean open edge: {summary.mean_open_edge:.4f}",
        f"- Mean entry price: {summary.mean_entry_price:.4f}",
        f"- Min event equity: {summary.min_equity:.4f}",
        f"- Final event equity: {summary.final_event_equity:.4f}",
        "",
        "## Open Positions",
        "",
        "| timestamp | market_id | side | edge | cost | entry price | equity after |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for event in open_events:
        lines.append(
            f"| {event.timestamp} | {event.market_id} | {event.side} | "
            f"{event.edge:.4f} | {event.cost:.4f} | {event.entry_price:.4f} | {event.equity_after:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "If `positions_closed_events` is zero while `skip_existing_position_events` is high, the replay is primarily measuring mark-to-market exposure inside a short observation window rather than settled trade performance.",
        ]
    )
    atomic_write_text(out_md, "\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize survival event logs for open-position exposure analysis.")
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    summary, open_events = summarize_events(Path(args.events_csv))
    write_outputs(summary, open_events, Path(args.out_json), Path(args.out_csv), Path(args.out_md))
    for key, value in asdict(summary).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
