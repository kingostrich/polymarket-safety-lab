from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .forecast_providers import create_forecast_provider
from .survival import load_paper_rows


HASH_FIELDS = [
    "logged_at",
    "market_id",
    "question",
    "yes_bid",
    "yes_ask",
    "no_bid",
    "no_ask",
    "liquidity",
    "volume_24h",
]


@dataclass(frozen=True)
class ForecastRecord:
    generated_at: str
    logged_at: str
    market_id: str
    question: str
    provider: str
    model: str
    fair_yes: float
    cost: float
    reasoning: str
    input_hash: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    liquidity: float
    volume_24h: float


def row_input_hash(row: dict[str, str]) -> str:
    payload = {field: row.get(field, "") for field in HASH_FIELDS}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def build_forecast_records(
    rows: list[dict[str, str]],
    provider_mode: str,
    forecast_cost: float = 0.0,
    synthetic_edge: float = 0.12,
    synthetic_side: str = "YES",
) -> list[ForecastRecord]:
    provider = create_forecast_provider(
        provider_mode,
        cost_per_forecast=forecast_cost,
        synthetic_edge=synthetic_edge,
        synthetic_side=synthetic_side,
    )
    generated_at = datetime.now(UTC).isoformat()
    records: list[ForecastRecord] = []
    for row in rows:
        forecast = provider.forecast(row)
        records.append(
            ForecastRecord(
                generated_at=generated_at,
                logged_at=row["logged_at"],
                market_id=row["market_id"],
                question=row["question"],
                provider=provider_mode,
                model=forecast.model,
                fair_yes=forecast.fair_yes,
                cost=forecast.cost,
                reasoning=forecast.reasoning,
                input_hash=row_input_hash(row),
                yes_bid=as_float(row.get("yes_bid")),
                yes_ask=as_float(row.get("yes_ask")),
                no_bid=as_float(row.get("no_bid")),
                no_ask=as_float(row.get("no_ask")),
                liquidity=as_float(row.get("liquidity")),
                volume_24h=as_float(row.get("volume_24h")),
            )
        )
    return records


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)


def atomic_copy_text(source: Path, destination: Path) -> None:
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, tmp_path)
    os.replace(tmp_path, destination)


def write_forecast_records(records: list[ForecastRecord], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out_dir / f"forecasts_{stamp}.csv"
    jsonl_path = out_dir / f"forecasts_{stamp}.jsonl"
    rows = [asdict(record) for record in records]
    if rows:
        tmp_csv_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
        with tmp_csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_csv_path, csv_path)
        atomic_write_text(jsonl_path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        atomic_copy_text(csv_path, out_dir / "latest_forecasts.csv")
        atomic_copy_text(jsonl_path, out_dir / "latest_forecasts.jsonl")
    else:
        atomic_write_text(csv_path, "")
        atomic_write_text(jsonl_path, "")
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "records": len(records),
        "provider": records[0].provider if records else "",
        "model": records[0].model if records else "",
        "total_cost": sum(record.cost for record in records),
        "csv_path": str(csv_path),
        "jsonl_path": str(jsonl_path),
        "note": "Forecast records only. No orders were placed, signed, or submitted.",
    }
    atomic_write_text(out_dir / "latest_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate timestamped forecast records from paper logger rows.")
    parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    parser.add_argument("--out-dir", default="data/forecasts/rule_baseline")
    parser.add_argument("--provider", default="rule_baseline", choices=["recorded", "rule_baseline", "synthetic_edge"])
    parser.add_argument("--forecast-cost", type=float, default=0.0)
    parser.add_argument("--synthetic-edge", type=float, default=0.12)
    parser.add_argument("--synthetic-side", default="YES", choices=["YES", "NO"])
    args = parser.parse_args()

    rows = load_paper_rows(Path(args.input_dir))
    records = build_forecast_records(
        rows,
        provider_mode=args.provider,
        forecast_cost=args.forecast_cost,
        synthetic_edge=args.synthetic_edge,
        synthetic_side=args.synthetic_side,
    )
    manifest = write_forecast_records(records, Path(args.out_dir))
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
