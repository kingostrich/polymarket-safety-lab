from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .forecast_audit import load_forecast_rows, parse_float
from .forecast_providers import normalize_timestamp_key
from .forecast_runner import ForecastRecord, as_float, row_input_hash, write_forecast_records
from .survival import load_paper_rows


def source_key(row: dict[str, Any]) -> tuple[str, str]:
    return (normalize_timestamp_key(str(row["logged_at"])), str(row["market_id"]))


def load_model_rows(path: Path) -> list[dict[str, Any]]:
    return load_forecast_rows(path)


def build_external_forecast_records(
    source_rows: list[dict[str, str]],
    model_rows: list[dict[str, Any]],
    provider: str,
    model: str,
    default_cost: float = 0.0,
) -> list[ForecastRecord]:
    if not provider:
        raise ValueError("provider is required")
    if not model:
        raise ValueError("model is required")
    if not math.isfinite(default_cost) or default_cost < 0:
        raise ValueError("default_cost must be a finite non-negative number")

    source_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in source_rows:
        key = source_key(row)
        if key in source_by_key:
            raise ValueError(f"duplicate source row key: logged_at={key[0]} market_id={key[1]}")
        source_by_key[key] = row
    records: list[ForecastRecord] = []
    generated_at = datetime.now(UTC).isoformat()
    seen_keys: set[tuple[str, str]] = set()

    for model_row in model_rows:
        try:
            key = source_key(model_row)
        except (KeyError, ValueError) as exc:
            raise ValueError("model forecast row requires valid logged_at and market_id") from exc
        if key in seen_keys:
            raise ValueError(f"duplicate model forecast key: logged_at={key[0]} market_id={key[1]}")
        seen_keys.add(key)
        source_row = source_by_key.get(key)
        if source_row is None:
            raise ValueError(f"model forecast has no matching source row: logged_at={key[0]} market_id={key[1]}")
        expected_hash = row_input_hash(source_row)
        model_input_hash = str(model_row.get("input_hash") or "")
        if not model_input_hash:
            raise ValueError(f"input_hash is required for logged_at={key[0]} market_id={key[1]}")
        if model_input_hash != expected_hash:
            raise ValueError(f"input_hash mismatch for logged_at={key[0]} market_id={key[1]}")

        fair_yes, fair_yes_parsed = parse_float(model_row.get("fair_yes"))
        if not fair_yes_parsed or not math.isfinite(fair_yes) or fair_yes < 0.0 or fair_yes > 1.0:
            raise ValueError(f"invalid fair_yes for logged_at={key[0]} market_id={key[1]}")
        cost, cost_parsed = parse_float(model_row.get("cost", default_cost))
        if not cost_parsed:
            cost = default_cost
        if not math.isfinite(cost) or cost < 0:
            raise ValueError(f"invalid cost for logged_at={key[0]} market_id={key[1]}")
        reasoning = str(model_row.get("reasoning") or "").strip()
        if not reasoning:
            raise ValueError(f"reasoning is required for logged_at={key[0]} market_id={key[1]}")

        records.append(
            ForecastRecord(
                generated_at=generated_at,
                logged_at=source_row["logged_at"],
                market_id=source_row["market_id"],
                question=source_row["question"],
                provider=provider,
                model=model,
                fair_yes=fair_yes,
                cost=cost,
                reasoning=reasoning,
                input_hash=expected_hash,
                yes_bid=as_float(source_row.get("yes_bid")),
                yes_ask=as_float(source_row.get("yes_ask")),
                no_bid=as_float(source_row.get("no_bid")),
                no_ask=as_float(source_row.get("no_ask")),
                liquidity=as_float(source_row.get("liquidity")),
                volume_24h=as_float(source_row.get("volume_24h")),
            )
        )

    missing = sorted(set(source_by_key) - seen_keys)
    if missing:
        first_missing = missing[0]
        raise ValueError(
            f"model forecast is missing {len(missing)} source rows; "
            f"first logged_at={first_missing[0]} market_id={first_missing[1]}"
        )
    return records


def write_model_prompt_template(source_rows: list[dict[str, str]], output_path: Path, limit: int = 20) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in source_rows[:limit]:
        rows.append(
            {
                "logged_at": row["logged_at"],
                "market_id": row["market_id"],
                "question": row["question"],
                "yes_bid": row.get("yes_bid", ""),
                "yes_ask": row.get("yes_ask", ""),
                "no_bid": row.get("no_bid", ""),
                "no_ask": row.get("no_ask", ""),
                "liquidity": row.get("liquidity", ""),
                "volume_24h": row.get("volume_24h", ""),
                "input_hash": row_input_hash(row),
                "required_output_fields": ["logged_at", "market_id", "input_hash", "fair_yes", "cost", "reasoning"],
            }
        )
    output_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""))


def write_minimal_model_csv(records: list[ForecastRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    fieldnames = ["logged_at", "market_id", "input_hash", "fair_yes", "cost", "reasoning"]
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({field: getattr(record, field) for field in fieldnames})
    tmp_path.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import external/LLM model forecasts into the canonical forecast replay schema.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template_parser = subparsers.add_parser("template", help="Write a JSONL prompt/input template for external models.")
    template_parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    template_parser.add_argument("--out-jsonl", default="data/forecasts/model_prompt_template.jsonl")
    template_parser.add_argument("--limit", type=int, default=20)

    import_parser = subparsers.add_parser("import", help="Import minimal model forecast rows into canonical forecasts.")
    import_parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    import_parser.add_argument("--model-forecasts-file", required=True)
    import_parser.add_argument("--out-dir", required=True)
    import_parser.add_argument("--provider", required=True)
    import_parser.add_argument("--model", required=True)
    import_parser.add_argument("--default-cost", type=float, default=0.0)

    args = parser.parse_args()
    source_rows = load_paper_rows(Path(args.input_dir))

    if args.command == "template":
        write_model_prompt_template(source_rows, Path(args.out_jsonl), limit=args.limit)
        print(f"template_rows={min(len(source_rows), args.limit)}")
        print(f"jsonl_path={args.out_jsonl}")
        return

    model_rows = load_model_rows(Path(args.model_forecasts_file))
    records = build_external_forecast_records(
        source_rows,
        model_rows,
        provider=args.provider,
        model=args.model,
        default_cost=args.default_cost,
    )
    manifest = write_forecast_records(records, Path(args.out_dir))
    minimal_csv_path = Path(args.out_dir) / "latest_model_minimal.csv"
    write_minimal_model_csv(records, minimal_csv_path)
    for key, value in manifest.items():
        print(f"{key}={value}")
    print(f"minimal_csv_path={minimal_csv_path}")


if __name__ == "__main__":
    main()
