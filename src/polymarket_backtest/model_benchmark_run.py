from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .forecast_audit import atomic_write_json, audit_forecasts
from .forecast_diagnostics import diagnose_forecasts
from .forecast_import import build_external_forecast_records, load_model_rows, write_minimal_model_csv
from .forecast_providers import ForecastFileProvider
from .forecast_runner import write_forecast_records
from .model_benchmark_summary import build_benchmark_rows
from .model_benchmark_summary import write_csv as write_summary_csv
from .model_benchmark_summary import write_markdown as write_summary_markdown
from .survival import load_paper_rows, load_resolutions, simulate_survival, write_survival_outputs


def source_rows_fingerprint(source_rows: list[dict[str, Any]]) -> str:
    from .forecast_runner import row_input_hash

    row_hashes = sorted(row_input_hash(row) for row in source_rows)
    payload = json.dumps(row_hashes, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_model_benchmark(
    input_dir: Path,
    model_forecasts_file: Path,
    benchmark_name: str,
    provider: str,
    model: str,
    forecast_root: Path = Path("data/forecasts"),
    survival_root: Path = Path("data/paper"),
    summary_csv: Path = Path("data/forecasts/model_benchmark_summary.csv"),
    summary_md: Path = Path("docs/model_benchmark_summary.md"),
    resolutions_csv: Path | None = None,
    default_cost: float = 0.0,
    scenario_prefix: str = "model_bench_20_survival_",
    bankroll: float = 50.0,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
    max_positions: int = 10,
    death_threshold: float = 0.0,
    exit_policy: str = "none",
    exit_edge_threshold: float = 0.0,
    exit_liquidity_model: str = "none",
    max_exit_depth_fraction: float = 0.25,
    missing_quote_policy: str = "zero",
    forecast_call_policy: str = "always",
    timestamp_order_policy: str = "sequential",
    drawdown_policy: str = "event",
    summary_source_rows_filter: int = 0,
    rank_mode: str = "quality",
) -> dict[str, Any]:
    source_rows = load_paper_rows(input_dir)
    if not source_rows:
        raise ValueError(f"no paper rows found in {input_dir}")
    if not benchmark_name:
        raise ValueError("benchmark_name is required")

    imported_dir = forecast_root / benchmark_name / "imported"
    survival_dir = survival_root / f"{scenario_prefix}{benchmark_name}"

    model_rows = load_model_rows(model_forecasts_file)
    records = build_external_forecast_records(
        source_rows,
        model_rows,
        provider=provider,
        model=model,
        default_cost=default_cost,
    )
    write_forecast_records(records, imported_dir)
    minimal_csv_path = imported_dir / "latest_model_minimal.csv"
    write_minimal_model_csv(records, minimal_csv_path)

    audit = audit_forecasts(source_rows, [asdict(record) for record in records])
    audit_path = imported_dir / "latest_audit.json"
    atomic_write_json(audit_path, asdict(audit))
    if audit.status != "PASS":
        raise RuntimeError(f"forecast audit failed for {benchmark_name}: {audit_path}")
    diagnostics = diagnose_forecasts(
        [asdict(record) for record in records],
        edge_threshold=edge_threshold,
        outcome_rows=source_rows,
    )
    diagnostics_path = imported_dir / "latest_diagnostics.json"
    atomic_write_json(diagnostics_path, asdict(diagnostics))

    forecast_file = imported_dir / "latest_forecasts.jsonl"
    resolutions = load_resolutions(resolutions_csv) if resolutions_csv else {}
    survival_result, survival_events = simulate_survival(
        source_rows,
        provider=ForecastFileProvider(forecast_file),
        resolutions=resolutions,
        initial_bankroll=bankroll,
        edge_threshold=edge_threshold,
        max_fraction=max_fraction,
        max_positions=max_positions,
        death_threshold=death_threshold,
        exit_policy=exit_policy,
        exit_edge_threshold=exit_edge_threshold,
        exit_liquidity_model=exit_liquidity_model,
        max_exit_depth_fraction=max_exit_depth_fraction,
        missing_quote_policy=missing_quote_policy,
        forecast_call_policy=forecast_call_policy,
        timestamp_order_policy=timestamp_order_policy,
        drawdown_policy=drawdown_policy,
    )
    survival_paths = write_survival_outputs(survival_result, survival_events, survival_dir)

    rows = build_benchmark_rows(
        forecast_root=forecast_root,
        survival_root=survival_root,
        scenario_prefix=scenario_prefix,
        source_rows_filter=summary_source_rows_filter or len(source_rows),
        rank_mode=rank_mode,
    )
    write_summary_csv(rows, summary_csv)
    write_summary_markdown(rows, summary_md, rank_mode=rank_mode)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_name": benchmark_name,
        "provider": provider,
        "model": model,
        "source_rows": len(source_rows),
        "source_rows_fingerprint": source_rows_fingerprint(source_rows),
        "comparison_invariant": "source_rows_fingerprint must match before comparing providers on identical paper rows",
        "model_rows": len(model_rows),
        "imported_records": len(records),
        "default_cost": default_cost,
        "resolutions_csv": str(resolutions_csv) if resolutions_csv else "",
        "resolutions_loaded": len(resolutions),
        "scenario_prefix": scenario_prefix,
        "bankroll": bankroll,
        "edge_threshold": edge_threshold,
        "max_fraction": max_fraction,
        "max_positions": max_positions,
        "death_threshold": death_threshold,
        "exit_policy": exit_policy,
        "exit_edge_threshold": exit_edge_threshold,
        "exit_liquidity_model": exit_liquidity_model,
        "max_exit_depth_fraction": max_exit_depth_fraction,
        "missing_quote_policy": missing_quote_policy,
        "forecast_call_policy": forecast_call_policy,
        "timestamp_order_policy": timestamp_order_policy,
        "drawdown_policy": drawdown_policy,
        "summary_source_rows_filter": summary_source_rows_filter or len(source_rows),
        "rank_mode": rank_mode,
        "audit_status": audit.status,
        "diagnostics_path": str(diagnostics_path),
        "diagnosis_flags": diagnostics.diagnosis_flags,
        "market_echo_share_1bp": diagnostics.market_echo_share_1bp,
        "actionable_rows": diagnostics.actionable_rows,
        "brier_score": diagnostics.brier_score,
        "brier_resolved_rows": diagnostics.brier_resolved_rows,
        "brier_excluded_rows": diagnostics.brier_excluded_rows,
        "survival_state": survival_result.state,
        "final_equity": survival_result.final_equity,
        "positions_opened": survival_result.positions_opened,
        "positions_closed": survival_result.positions_closed,
        "open_positions": survival_result.open_positions,
        "realized_pnl": survival_result.realized_pnl,
        "forecast_dir": str(imported_dir),
        "forecasts_file": str(forecast_file),
        "audit_path": str(audit_path),
        "minimal_csv_path": str(minimal_csv_path),
        "survival_report_path": survival_paths["report_path"],
        "survival_events_path": survival_paths["events_path"],
        "summary_csv": str(summary_csv),
        "summary_md": str(summary_md),
        "note": "Benchmark replay only. No orders were placed, signed, or submitted.",
    }
    atomic_write_json(forecast_root / benchmark_name / "latest_benchmark_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run import, audit, survival replay, and summary refresh for one model benchmark file.")
    parser.add_argument("--input-dir", default="data/paper/model_bench_20")
    parser.add_argument("--model-forecasts-file", required=True)
    parser.add_argument("--benchmark-name", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--forecast-root", default="data/forecasts")
    parser.add_argument("--survival-root", default="data/paper")
    parser.add_argument("--scenario-prefix", default="model_bench_20_survival_")
    parser.add_argument("--summary-csv", default="data/forecasts/model_benchmark_summary.csv")
    parser.add_argument("--summary-md", default="docs/model_benchmark_summary.md")
    parser.add_argument("--resolutions-csv", default="")
    parser.add_argument("--default-cost", type=float, default=0.0)
    parser.add_argument("--bankroll", type=float, default=50.0)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--max-fraction", type=float, default=0.06)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--death-threshold", type=float, default=0.0)
    parser.add_argument("--exit-policy", default="none", choices=["none", "edge_below"])
    parser.add_argument("--exit-edge-threshold", type=float, default=0.0)
    parser.add_argument("--exit-liquidity-model", default="none", choices=["none", "top3_bid"])
    parser.add_argument("--max-exit-depth-fraction", type=float, default=0.25)
    parser.add_argument("--missing-quote-policy", default="zero", choices=["zero", "last_valid_bid"])
    parser.add_argument("--forecast-call-policy", default="always", choices=["always", "actionable"])
    parser.add_argument("--timestamp-order-policy", default="sequential", choices=["sequential", "history_first", "position_first"])
    parser.add_argument("--drawdown-policy", default="event", choices=["event", "timestamp_close"])
    parser.add_argument("--source-rows", type=int, default=0, help="Summary filter only; input rows are controlled by --input-dir.")
    parser.add_argument("--rank-mode", choices=["quality", "performance"], default="quality")
    args = parser.parse_args()

    manifest = run_model_benchmark(
        input_dir=Path(args.input_dir),
        model_forecasts_file=Path(args.model_forecasts_file),
        benchmark_name=args.benchmark_name,
        provider=args.provider,
        model=args.model,
        forecast_root=Path(args.forecast_root),
        survival_root=Path(args.survival_root),
        summary_csv=Path(args.summary_csv),
        summary_md=Path(args.summary_md),
        resolutions_csv=Path(args.resolutions_csv) if args.resolutions_csv else None,
        default_cost=args.default_cost,
        scenario_prefix=args.scenario_prefix,
        bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        max_fraction=args.max_fraction,
        max_positions=args.max_positions,
        death_threshold=args.death_threshold,
        exit_policy=args.exit_policy,
        exit_edge_threshold=args.exit_edge_threshold,
        exit_liquidity_model=args.exit_liquidity_model,
        max_exit_depth_fraction=args.max_exit_depth_fraction,
        missing_quote_policy=args.missing_quote_policy,
        forecast_call_policy=args.forecast_call_policy,
        timestamp_order_policy=args.timestamp_order_policy,
        drawdown_policy=args.drawdown_policy,
        summary_source_rows_filter=args.source_rows,
        rank_mode=args.rank_mode,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
