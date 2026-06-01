from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collectors import GAMMA_API, fetch_json, parse_json_list, resolved_outcome
from .survival import load_paper_rows


@dataclass(frozen=True)
class MarketResolutionStatus:
    market_id: str
    question: str
    active: bool
    closed: bool
    archived: bool
    accepting_orders: bool
    uma_resolution_status: str
    end_date: str
    closed_time: str
    updated_at: str
    outcome_prices: str
    conservative_outcome: str
    resolution_eligible: bool
    reason: str


def unique_market_ids(input_dir: Path) -> list[str]:
    return sorted({row["market_id"] for row in load_paper_rows(input_dir)})


def market_row_for_id(market_id: str) -> dict[str, Any] | None:
    rows = fetch_json(f"{GAMMA_API}/markets", {"id": market_id})
    if not rows:
        return None
    return rows[0]


def parse_market_status(market_id: str, row: dict[str, Any] | None) -> MarketResolutionStatus:
    if row is None:
        return MarketResolutionStatus(
            market_id=market_id,
            question="",
            active=False,
            closed=False,
            archived=False,
            accepting_orders=False,
            uma_resolution_status="",
            end_date="",
            closed_time="",
            updated_at="",
            outcome_prices="",
            conservative_outcome="",
            resolution_eligible=False,
            reason="missing_gamma_market",
        )
    prices = parse_json_list(row.get("outcomePrices"))
    outcome = resolved_outcome(prices) or ""
    closed = bool(row.get("closed"))
    closed_time = row.get("closedTime") or ""
    updated_at = row.get("updatedAt") or ""
    reason = ""
    if not closed:
        reason = "market_not_closed"
    elif not outcome:
        reason = "no_conservative_binary_outcome"
    elif not (closed_time or updated_at):
        reason = "missing_resolution_timestamp"
    eligible = closed and bool(outcome) and bool(closed_time or updated_at)
    return MarketResolutionStatus(
        market_id=market_id,
        question=row.get("question") or "",
        active=bool(row.get("active")),
        closed=closed,
        archived=bool(row.get("archived")),
        accepting_orders=bool(row.get("acceptingOrders")),
        uma_resolution_status=row.get("umaResolutionStatus") or "",
        end_date=row.get("endDate") or "",
        closed_time=closed_time,
        updated_at=updated_at,
        outcome_prices=json.dumps(prices, ensure_ascii=False),
        conservative_outcome=outcome,
        resolution_eligible=eligible,
        reason=reason,
    )


def collect_statuses(input_dir: Path) -> list[MarketResolutionStatus]:
    statuses: list[MarketResolutionStatus] = []
    for market_id in unique_market_ids(input_dir):
        statuses.append(parse_market_status(market_id, market_row_for_id(market_id)))
    return statuses


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)


def write_outputs(statuses: list[MarketResolutionStatus], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "market_resolution_status.csv"
    resolutions_path = out_dir / "resolutions.csv"
    manifest_path = out_dir / "resolution_manifest.json"
    status_rows = [asdict(status) for status in statuses]
    write_csv(status_path, status_rows, list(MarketResolutionStatus.__dataclass_fields__.keys()))
    resolution_rows = [
        {
            "market_id": status.market_id,
            "resolved_at": status.closed_time or status.updated_at,
            "resolved_outcome": status.conservative_outcome,
        }
        for status in statuses
        if status.resolution_eligible
    ]
    write_csv(resolutions_path, resolution_rows, ["market_id", "resolved_at", "resolved_outcome"])
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "markets": len(statuses),
        "resolution_eligible": len(resolution_rows),
        "closed": sum(1 for status in statuses if status.closed),
        "near_binary_but_open": sum(
            1
            for status in statuses
            if not status.closed and status.conservative_outcome in {"YES", "NO"}
        ),
        "near_binary_disputed_open": sum(
            1
            for status in statuses
            if not status.closed
            and status.conservative_outcome in {"YES", "NO"}
            and status.uma_resolution_status.lower() == "disputed"
        ),
        "status_path": str(status_path),
        "resolutions_path": str(resolutions_path),
        "outcome_threshold_note": "conservative binary outcome requires YES>=0.999 and NO<=0.001, or NO>=0.999 and YES<=0.001",
        "fetch_note": "Gamma reads use the project fetch_json helper with certifi CA support and retry handling.",
        "note": "Only closed=true markets with conservative binary outcome are written to resolutions.csv.",
    }
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Gamma resolution status for forward paper markets.")
    parser.add_argument("--input-dir", default="data/paper/model_bench_100")
    parser.add_argument("--out-dir", default="data/paper/resolution_status/model_bench_100")
    args = parser.parse_args()

    statuses = collect_statuses(Path(args.input_dir))
    manifest = write_outputs(statuses, Path(args.out_dir))
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
