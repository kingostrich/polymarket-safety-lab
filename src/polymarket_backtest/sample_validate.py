from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Side
from .simulator import load_snapshots


REQUIRED_COLUMNS = {
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
}


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: str
    detail: str


def _check(name: str, passed: bool, detail: str) -> ValidationCheck:
    return ValidationCheck(name=name, status="PASS" if passed else "FAIL", detail=detail)


def _read_header(path: Path) -> list[str]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _raw_market_timestamps_are_sorted(rows: list[dict[str, str]]) -> bool:
    previous_by_market: dict[str, datetime] = {}
    for row in rows:
        market_id = row.get("market_id", "")
        timestamp = datetime.fromisoformat(row.get("timestamp", "").replace("Z", "+00:00"))
        previous = previous_by_market.get(market_id)
        if previous is not None and timestamp < previous:
            return False
        previous_by_market[market_id] = timestamp
    return True


def validate_sample(path: Path) -> dict[str, Any]:
    header = _read_header(path)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(header))
    if missing_columns:
        checks = [
            _check("required_columns", False, "missing=" + ",".join(missing_columns)),
        ]
        return {
            "path": str(path),
            "status": "FAIL",
            "rows": 0,
            "markets": 0,
            "resolved_rows": 0,
            "unresolved_rows": 0,
            "checks": [asdict(check) for check in checks],
        }
    rows = _read_rows(path)
    try:
        raw_timestamps_sorted = _raw_market_timestamps_are_sorted(rows)
        snapshots = load_snapshots(path)
    except (KeyError, TypeError, ValueError) as exc:
        checks = [
            _check("loadable_csv", False, f"{type(exc).__name__}: {exc}"),
        ]
        return {
            "path": str(path),
            "status": "FAIL",
            "rows": len(rows),
            "markets": len({row.get("market_id", "") for row in rows if row.get("market_id", "")}),
            "resolved_rows": 0,
            "unresolved_rows": 0,
            "checks": [asdict(check) for check in checks],
        }
    market_ids = {snapshot.market_id for snapshot in snapshots}
    resolved = [snapshot for snapshot in snapshots if snapshot.resolved_outcome is not None]
    unresolved = [snapshot for snapshot in snapshots if snapshot.resolved_outcome is None]
    invalid_prices = [
        snapshot
        for snapshot in snapshots
        if not (
            0.0 <= snapshot.yes_price <= 1.0
            and 0.0 <= snapshot.no_price <= 1.0
            and 0.0 <= snapshot.fair_yes <= 1.0
        )
    ]
    invalid_price_sums = [
        snapshot
        for snapshot in snapshots
        if abs((snapshot.yes_price + snapshot.no_price) - 1.0) > 0.02
    ]
    invalid_resolutions = [
        snapshot
        for snapshot in resolved
        if snapshot.resolved_outcome not in (Side.YES, Side.NO)
    ]
    invalid_fee_rates = [
        snapshot
        for snapshot in snapshots
        if not (0.0 <= snapshot.fee_rate <= 1.0)
    ]

    checks = [
        _check(
            "required_columns",
            not missing_columns,
            "missing=" + ",".join(missing_columns) if missing_columns else "all required columns present",
        ),
        _check("loadable_csv", True, "CSV parsed into MarketSnapshot rows"),
        _check("has_rows", len(snapshots) > 0, f"rows={len(snapshots)}"),
        _check("has_multiple_markets", len(market_ids) >= 2, f"markets={len(market_ids)}"),
        _check("has_unresolved_entries", len(unresolved) > 0, f"unresolved_rows={len(unresolved)}"),
        _check("has_resolved_entries", len(resolved) > 0, f"resolved_rows={len(resolved)}"),
        _check("prices_in_unit_interval", not invalid_prices, f"invalid_rows={len(invalid_prices)}"),
        _check("binary_price_sums_near_one", not invalid_price_sums, f"invalid_rows={len(invalid_price_sums)}"),
        _check("valid_resolved_outcomes", not invalid_resolutions, f"invalid_rows={len(invalid_resolutions)}"),
        _check("fee_rates_in_unit_interval", not invalid_fee_rates, f"invalid_rows={len(invalid_fee_rates)}"),
        _check("market_timestamps_chronological", raw_timestamps_sorted, "raw rows are chronological within each market_id"),
    ]
    failures = [check for check in checks if check.status == "FAIL"]
    return {
        "path": str(path),
        "status": "PASS" if not failures else "FAIL",
        "rows": len(snapshots),
        "markets": len(market_ids),
        "resolved_rows": len(resolved),
        "unresolved_rows": len(unresolved),
        "checks": [asdict(check) for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a tiny reproducible sample dataset for the paper-only backtest scaffold.")
    parser.add_argument("--snapshots", default="data/mock/snapshots.csv", help="CSV snapshot fixture to validate")
    parser.add_argument("--json", action="store_true", help="Print the full validation report as JSON")
    args = parser.parse_args()

    report = validate_sample(Path(args.snapshots))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"status={report['status']}")
        print(f"rows={report['rows']}")
        print(f"markets={report['markets']}")
        print(f"resolved_rows={report['resolved_rows']}")
        print(f"unresolved_rows={report['unresolved_rows']}")
        for check in report["checks"]:
            print(f"{check['name']}={check['status']} {check['detail']}")
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
