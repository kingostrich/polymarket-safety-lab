from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def resolved_outcomes(rows: list[dict[str, str]]) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for row in rows:
        outcome = (row.get("resolved_outcome") or "").upper()
        if outcome in {"YES", "NO"}:
            outcomes[row["market_id"]] = outcome
    return outcomes


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_oracle_smoke_rows(rows: list[dict[str, str]], edge: float = 0.12) -> list[dict[str, str]]:
    outcomes = resolved_outcomes(rows)
    output: list[dict[str, str]] = []
    for row in rows:
        copied = dict(row)
        outcome = outcomes.get(row["market_id"], "")
        yes_price = float(row["yes_price"])
        no_price = float(row["no_price"])
        is_resolution_row = (row.get("resolved_outcome") or "").upper() in {"YES", "NO"}
        if outcome == "YES" and not is_resolution_row:
            copied["fair_yes"] = f"{clamp(yes_price + edge):.6f}"
        elif outcome == "NO" and not is_resolution_row:
            copied["fair_yes"] = f"{clamp(1.0 - no_price - edge):.6f}"
        output.append(copied)
    return output


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
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
    ]
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a test-only oracle fair-value dataset to verify settlement accounting.")
    parser.add_argument("--input-snapshots", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--edge", type=float, default=0.12)
    args = parser.parse_args()

    source_rows = read_rows(Path(args.input_snapshots))
    output_rows = build_oracle_smoke_rows(source_rows, edge=args.edge)
    write_rows(Path(args.out_csv), output_rows)
    outcomes = resolved_outcomes(source_rows)
    changed = sum(1 for source, output in zip(source_rows, output_rows) if source.get("fair_yes") != output.get("fair_yes"))
    print(f"source_rows={len(source_rows)}")
    print(f"resolved_markets={len(outcomes)}")
    print(f"changed_rows={changed}")
    print(f"edge={args.edge}")
    print(f"out_csv={args.out_csv}")
    print("note=test-only oracle dataset; uses resolved outcomes and must not be used for alpha claims")


if __name__ == "__main__":
    main()
