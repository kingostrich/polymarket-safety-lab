from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .forecast_providers import normalize_timestamp_key
from .forecast_runner import row_input_hash
from .survival import load_paper_rows


@dataclass(frozen=True)
class ForecastAuditResult:
    status: str
    source_rows: int
    forecast_records: int
    matched_records: int
    schema_errors: int
    missing_forecasts: int
    extra_forecasts: int
    duplicate_forecast_keys: int
    missing_input_hashes: int
    input_hash_mismatches: int
    invalid_probabilities: int
    invalid_costs: int
    negative_costs: int
    nonfinite_costs: int
    blank_reasoning: int
    blank_providers: int
    blank_models: int
    total_cost: float
    unique_models: int
    unique_providers: int
    coverage: float
    provider_counts: str
    model_counts: str


def forecast_key(row: dict[str, Any]) -> tuple[str, str]:
    return (normalize_timestamp_key(str(row["logged_at"])), str(row["market_id"]))


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_float(value: Any) -> tuple[float, bool]:
    if value in (None, ""):
        return 0.0, False
    try:
        return float(value), True
    except (TypeError, ValueError):
        return 0.0, False


def load_forecast_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open() as handle:
            for line in handle:
                if line.strip():
                    loaded = json.loads(line)
                    if not isinstance(loaded, dict):
                        raise ValueError(f"forecast JSONL row is not an object: {path}")
                    rows.append(loaded)
        return rows
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def compact_counts(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        label = value or "<blank>"
        counts[label] = counts.get(label, 0) + 1
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def audit_forecasts(source_rows: list[dict[str, str]], forecast_rows: list[dict[str, Any]]) -> ForecastAuditResult:
    source_by_key = {forecast_key(row): row for row in source_rows}
    forecast_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    schema_errors = 0
    duplicate_forecast_keys = 0
    invalid_probabilities = 0
    invalid_costs = 0
    negative_costs = 0
    nonfinite_costs = 0
    blank_reasoning = 0
    blank_providers = 0
    blank_models = 0
    total_cost = 0.0
    providers: list[str] = []
    models: list[str] = []
    missing_input_hashes = 0
    input_hash_mismatches = 0

    for row in forecast_rows:
        try:
            key = forecast_key(row)
        except (KeyError, ValueError):
            schema_errors += 1
            continue
        if key in forecast_by_key:
            duplicate_forecast_keys += 1
        forecast_by_key[key] = row
        source_row = source_by_key.get(key)
        forecast_hash = row.get("input_hash")
        if source_row is not None:
            if not forecast_hash:
                missing_input_hashes += 1
            elif forecast_hash != row_input_hash(source_row):
                input_hash_mismatches += 1
        fair_yes = safe_float(row.get("fair_yes"), default=-1.0)
        if not math.isfinite(fair_yes) or fair_yes < 0.0 or fair_yes > 1.0:
            invalid_probabilities += 1
        cost, cost_parsed = parse_float(row.get("cost"))
        if not cost_parsed:
            invalid_costs += 1
        elif not math.isfinite(cost):
            nonfinite_costs += 1
        elif cost < 0.0:
            negative_costs += 1
        if math.isfinite(cost):
            total_cost += cost
        if not str(row.get("reasoning") or "").strip():
            blank_reasoning += 1
        provider = str(row.get("provider") or "")
        model = str(row.get("model") or "")
        if not provider:
            blank_providers += 1
        if not model:
            blank_models += 1
        providers.append(provider)
        models.append(model)

    source_keys = set(source_by_key)
    forecast_keys = set(forecast_by_key)
    matched_keys = source_keys & forecast_keys
    missing_forecasts = len(source_keys - forecast_keys)
    extra_forecasts = len(forecast_keys - source_keys)

    blocking_errors = (
        schema_errors
        + missing_forecasts
        + extra_forecasts
        + duplicate_forecast_keys
        + missing_input_hashes
        + input_hash_mismatches
        + invalid_probabilities
        + invalid_costs
        + negative_costs
        + nonfinite_costs
        + blank_providers
        + blank_models
    )
    status = "PASS" if blocking_errors == 0 else "FAIL"
    coverage = (len(matched_keys) / len(source_keys)) if source_keys else 1.0
    return ForecastAuditResult(
        status=status,
        source_rows=len(source_rows),
        forecast_records=len(forecast_rows),
        matched_records=len(matched_keys),
        schema_errors=schema_errors,
        missing_forecasts=missing_forecasts,
        extra_forecasts=extra_forecasts,
        duplicate_forecast_keys=duplicate_forecast_keys,
        missing_input_hashes=missing_input_hashes,
        input_hash_mismatches=input_hash_mismatches,
        invalid_probabilities=invalid_probabilities,
        invalid_costs=invalid_costs,
        negative_costs=negative_costs,
        nonfinite_costs=nonfinite_costs,
        blank_reasoning=blank_reasoning,
        blank_providers=blank_providers,
        blank_models=blank_models,
        total_cost=total_cost,
        unique_models=len(set(models)),
        unique_providers=len(set(providers)),
        coverage=coverage,
        provider_counts=compact_counts(providers),
        model_counts=compact_counts(models),
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit forecast file coverage and replay safety against paper rows.")
    parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    parser.add_argument("--forecasts-file", required=True)
    parser.add_argument("--out-json", default="data/forecasts/forecast_audit_latest.json")
    args = parser.parse_args()

    source_rows = load_paper_rows(Path(args.input_dir))
    forecast_rows = load_forecast_rows(Path(args.forecasts_file))
    result = audit_forecasts(source_rows, forecast_rows)
    atomic_write_json(Path(args.out_json), asdict(result))
    for key, value in asdict(result).items():
        print(f"{key}={value}")
    print(f"json_path={args.out_json}")


if __name__ == "__main__":
    main()
