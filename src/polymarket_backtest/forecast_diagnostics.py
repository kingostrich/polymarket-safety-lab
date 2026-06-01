from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .forecast_audit import load_forecast_rows, safe_float


@dataclass(frozen=True)
class ForecastDiagnostics:
    records: int
    rows_with_yes_quotes: int
    rows_with_no_quotes: int
    mean_abs_diff_to_yes_mid: float
    max_abs_diff_to_yes_mid: float
    market_echo_rows_1bp: int
    market_echo_share_1bp: float
    mean_yes_spread: float
    mean_no_spread: float
    invalid_fair_yes_rows: int
    mean_yes_edge_to_ask: float
    mean_no_edge_to_ask: float
    mean_abs_yes_edge_to_ask: float
    mean_abs_no_edge_to_ask: float
    mean_positive_yes_edge_to_ask: float
    mean_positive_no_edge_to_ask: float
    yes_edge_ge_threshold: int
    no_edge_ge_threshold: int
    actionable_rows: int
    edge_threshold: float
    diagnosis_flags: str


def finite_or_none(value: Any) -> float | None:
    parsed = safe_float(value, default=float("nan"))
    return parsed if math.isfinite(parsed) else None


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def diagnose_forecasts(rows: list[dict[str, Any]], edge_threshold: float = 0.08) -> ForecastDiagnostics:
    diffs_to_mid: list[float] = []
    yes_spreads: list[float] = []
    no_spreads: list[float] = []
    yes_edges: list[float] = []
    no_edges: list[float] = []
    yes_edges_abs: list[float] = []
    no_edges_abs: list[float] = []
    positive_yes_edges: list[float] = []
    positive_no_edges: list[float] = []
    market_echo_rows = 0
    yes_edge_ge_threshold = 0
    no_edge_ge_threshold = 0
    rows_with_yes_quotes = 0
    rows_with_no_quotes = 0
    invalid_fair_yes_rows = 0

    for row in rows:
        fair_yes = finite_or_none(row.get("fair_yes"))
        yes_bid = finite_or_none(row.get("yes_bid"))
        yes_ask = finite_or_none(row.get("yes_ask"))
        no_bid = finite_or_none(row.get("no_bid"))
        no_ask = finite_or_none(row.get("no_ask"))
        if fair_yes is None:
            invalid_fair_yes_rows += 1
            continue
        if yes_bid is not None and yes_ask is not None and yes_bid > 0 and yes_ask > 0:
            rows_with_yes_quotes += 1
            yes_mid = (yes_bid + yes_ask) / 2.0
            diff = abs(fair_yes - yes_mid)
            diffs_to_mid.append(diff)
            yes_spreads.append(max(0.0, yes_ask - yes_bid))
            if diff <= 0.0001:
                market_echo_rows += 1
            yes_edge = fair_yes - yes_ask
            yes_edges.append(yes_edge)
            yes_edges_abs.append(abs(yes_edge))
            if yes_edge > 0:
                positive_yes_edges.append(yes_edge)
            if yes_edge >= edge_threshold:
                yes_edge_ge_threshold += 1
        if no_bid is not None and no_ask is not None and no_bid > 0 and no_ask > 0:
            rows_with_no_quotes += 1
            no_spreads.append(max(0.0, no_ask - no_bid))
            no_edge = (1.0 - fair_yes) - no_ask
            no_edges.append(no_edge)
            no_edges_abs.append(abs(no_edge))
            if no_edge > 0:
                positive_no_edges.append(no_edge)
            if no_edge >= edge_threshold:
                no_edge_ge_threshold += 1

    actionable_rows = yes_edge_ge_threshold + no_edge_ge_threshold
    records = len(rows)
    market_echo_share = market_echo_rows / rows_with_yes_quotes if rows_with_yes_quotes else 0.0
    flags: list[str] = []
    if rows_with_yes_quotes == 0:
        flags.append("missing_yes_quotes")
    if rows_with_no_quotes == 0:
        flags.append("missing_no_quotes")
    if invalid_fair_yes_rows > 0:
        flags.append("invalid_fair_yes_rows")
    if market_echo_share >= 0.8 and rows_with_yes_quotes > 0:
        flags.append("market_echo")
    if actionable_rows == 0:
        flags.append("no_actionable_edges")
    return ForecastDiagnostics(
        records=records,
        rows_with_yes_quotes=rows_with_yes_quotes,
        rows_with_no_quotes=rows_with_no_quotes,
        mean_abs_diff_to_yes_mid=mean(diffs_to_mid),
        max_abs_diff_to_yes_mid=max(diffs_to_mid) if diffs_to_mid else 0.0,
        market_echo_rows_1bp=market_echo_rows,
        market_echo_share_1bp=market_echo_share,
        mean_yes_spread=mean(yes_spreads),
        mean_no_spread=mean(no_spreads),
        invalid_fair_yes_rows=invalid_fair_yes_rows,
        mean_yes_edge_to_ask=mean(yes_edges),
        mean_no_edge_to_ask=mean(no_edges),
        mean_abs_yes_edge_to_ask=mean(yes_edges_abs),
        mean_abs_no_edge_to_ask=mean(no_edges_abs),
        mean_positive_yes_edge_to_ask=mean(positive_yes_edges),
        mean_positive_no_edge_to_ask=mean(positive_no_edges),
        yes_edge_ge_threshold=yes_edge_ge_threshold,
        no_edge_ge_threshold=no_edge_ge_threshold,
        actionable_rows=actionable_rows,
        edge_threshold=edge_threshold,
        diagnosis_flags=";".join(flags),
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose forecast files for market-midpoint echo and actionable edge counts.")
    parser.add_argument("--forecasts-file", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    args = parser.parse_args()

    rows = load_forecast_rows(Path(args.forecasts_file))
    diagnostics = diagnose_forecasts(rows, edge_threshold=args.edge_threshold)
    atomic_write_json(Path(args.out_json), asdict(diagnostics))
    for key, value in asdict(diagnostics).items():
        print(f"{key}={value}")
    print(f"json_path={args.out_json}")


if __name__ == "__main__":
    main()
