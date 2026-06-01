from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SurvivalReportSummary:
    scenario: str
    report_path: str
    run_timestamp: str
    state: str
    death_reason: str
    initial_bankroll: float
    final_equity: float
    final_cash: float
    return_on_investment: float
    max_drawdown: float
    event_max_drawdown: float
    timestamp_close_max_drawdown: float
    drawdown_policy: str
    rows_processed: int
    signals_seen: int
    forecast_calls: int
    forecast_cost_total: float
    positions_opened: int
    positions_closed: int
    open_positions: int
    liquidity_skips: int
    partial_entries: int
    unfilled_entry_notional: float
    exit_liquidity_skips: int
    partial_exits: int
    unfilled_exit_notional: float
    slippage_cost_total: float
    realized_pnl: float
    forecast_model: str
    legacy_mdd_fields: bool
    missing_fields: str


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value)


def run_timestamp_from_path(path: Path) -> str:
    prefix = "survival_report_"
    if path.name.startswith(prefix) and path.suffix == ".json":
        return path.name[len(prefix) : -len(path.suffix)]
    if path.name == "latest_survival_report.json":
        return "latest"
    return ""


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"report is not a JSON object: {path}")
    return loaded


def survival_report_paths(input_dir: Path, include_latest: bool = False) -> list[Path]:
    pattern = "**/*.json" if include_latest else "**/survival_report_*.json"
    paths = sorted(path for path in input_dir.glob(pattern) if path.is_file())
    if include_latest:
        paths = [path for path in paths if path.name.startswith(("survival_report_", "latest_survival_report"))]
    return paths


def normalize_survival_report(path: Path, input_dir: Path) -> SurvivalReportSummary:
    report = load_json(path)
    max_dd = safe_float(report.get("max_drawdown"))
    legacy_mdd_fields = "event_max_drawdown" not in report or "timestamp_close_max_drawdown" not in report
    event_max_dd = safe_float(report.get("event_max_drawdown"), max_dd)
    timestamp_close_max_dd = safe_float(report.get("timestamp_close_max_drawdown"), max_dd)
    initial_bankroll = safe_float(report.get("initial_bankroll"))
    return_on_investment = ((safe_float(report.get("final_equity")) - initial_bankroll) / initial_bankroll) if initial_bankroll > 0 else 0.0
    tracked_fields = [
        "death_reason",
        "initial_bankroll",
        "signals_seen",
        "liquidity_skips",
        "partial_entries",
        "unfilled_entry_notional",
        "exit_liquidity_skips",
        "partial_exits",
        "unfilled_exit_notional",
        "slippage_cost_total",
        "event_max_drawdown",
        "timestamp_close_max_drawdown",
        "drawdown_policy",
    ]
    missing_fields = sorted(field for field in tracked_fields if field not in report or report.get(field) is None)
    try:
        scenario = path.parent.relative_to(input_dir).as_posix()
    except ValueError:
        scenario = path.parent.name
    if scenario in {"", "."}:
        scenario = path.parent.name

    return SurvivalReportSummary(
        scenario=scenario,
        report_path=str(path),
        run_timestamp=run_timestamp_from_path(path),
        state=safe_str(report.get("state")),
        death_reason=safe_str(report.get("death_reason")),
        initial_bankroll=initial_bankroll,
        final_equity=safe_float(report.get("final_equity")),
        final_cash=safe_float(report.get("final_cash")),
        return_on_investment=return_on_investment,
        max_drawdown=max_dd,
        event_max_drawdown=event_max_dd,
        timestamp_close_max_drawdown=timestamp_close_max_dd,
        drawdown_policy=safe_str(report.get("drawdown_policy"), "event_legacy" if legacy_mdd_fields else "event"),
        rows_processed=safe_int(report.get("rows_processed")),
        signals_seen=safe_int(report.get("signals_seen")),
        forecast_calls=safe_int(report.get("forecast_calls")),
        forecast_cost_total=safe_float(report.get("forecast_cost_total")),
        positions_opened=safe_int(report.get("positions_opened")),
        positions_closed=safe_int(report.get("positions_closed")),
        open_positions=safe_int(report.get("open_positions")),
        liquidity_skips=safe_int(report.get("liquidity_skips")),
        partial_entries=safe_int(report.get("partial_entries")),
        unfilled_entry_notional=safe_float(report.get("unfilled_entry_notional")),
        exit_liquidity_skips=safe_int(report.get("exit_liquidity_skips")),
        partial_exits=safe_int(report.get("partial_exits")),
        unfilled_exit_notional=safe_float(report.get("unfilled_exit_notional")),
        slippage_cost_total=safe_float(report.get("slippage_cost_total")),
        realized_pnl=safe_float(report.get("realized_pnl")),
        forecast_model=safe_str(report.get("forecast_model")),
        legacy_mdd_fields=legacy_mdd_fields,
        missing_fields=";".join(missing_fields),
    )


def summarize_survival_reports(input_dir: Path, include_latest: bool = False) -> list[SurvivalReportSummary]:
    return [
        normalize_survival_report(path, input_dir)
        for path in survival_report_paths(input_dir, include_latest=include_latest)
    ]


def write_csv(rows: list[SurvivalReportSummary], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(SurvivalReportSummary.__dataclass_fields__.keys())
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    os.replace(tmp_path, output_path)


def print_table(rows: list[SurvivalReportSummary], limit: int) -> None:
    selected = rows[:limit] if limit > 0 else rows
    print("scenario,run_timestamp,state,roi,final_equity,max_drawdown,event_max_drawdown,timestamp_close_max_drawdown,legacy_mdd_fields")
    for row in selected:
        print(
            f"{row.scenario},{row.run_timestamp},{row.state},{row.return_on_investment:.6f},"
            f"{row.final_equity:.6f},{row.max_drawdown:.6f},"
            f"{row.event_max_drawdown:.6f},{row.timestamp_close_max_drawdown:.6f},{str(row.legacy_mdd_fields).lower()}"
        )
    if limit > 0 and len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize survival report JSON files with legacy MDD compatibility.")
    parser.add_argument("--input-dir", default="data/paper")
    parser.add_argument("--output-csv", default="data/paper/survival_report_summary.csv")
    parser.add_argument("--include-latest", action="store_true", help="Include latest_survival_report.json duplicates.")
    parser.add_argument("--limit", type=int, default=20, help="Rows to print; use 0 for all rows.")
    args = parser.parse_args()

    rows = summarize_survival_reports(Path(args.input_dir), include_latest=args.include_latest)
    rows = sorted(rows, key=lambda row: (row.scenario, row.report_path))
    write_csv(rows, Path(args.output_csv))
    print_table(rows, args.limit)
    print(f"reports={len(rows)}")
    print(f"legacy_mdd_reports={sum(1 for row in rows if row.legacy_mdd_fields)}")
    print(f"csv_path={args.output_csv}")


if __name__ == "__main__":
    main()
