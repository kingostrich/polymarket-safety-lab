from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model_variant_compare import build_report as build_variant_report
from .resolution_replay_cycle import run_resolution_replay_cycle
from .strategy_readiness import assess_readiness, load_benchmark_manifest, load_json
from .strategy_readiness import write_markdown as write_readiness_markdown


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def resolve_oracle_metrics_path(path: Path, backtest_root: Path = Path("data/backtests")) -> Path:
    if str(path) != "latest":
        return path
    candidates = sorted(backtest_root.glob("*/oracle_smoke/metrics.json"), key=lambda candidate: candidate.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"no oracle smoke metrics found under {backtest_root}")
    return candidates[-1]


def run_paper_gate_cycle(
    input_dir: Path,
    status_out_dir: Path,
    model_forecasts_file: Path,
    resolution_benchmark_name: str,
    provider: str,
    model: str,
    resolution_cycle_manifest: Path,
    model_manifest: Path,
    baseline_manifest: Path,
    oracle_metrics: Path,
    readiness_json: Path,
    readiness_md: Path,
    variant_csv: Path,
    variant_json: Path,
    variant_md: Path,
    forecast_root: Path = Path("data/forecasts"),
    survival_root: Path = Path("data/paper"),
    scenario_prefix: str = "model_bench_100_survival_",
    source_rows: int = 100,
    resolution_summary_csv: Path = Path("data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv"),
    resolution_summary_md: Path = Path("docs/model_bench_100_resolution_summary.md"),
    rank_mode: str = "quality",
    min_source_rows: int = 100,
    min_closed_trades: int = 30,
    max_drawdown_limit: float = 0.25,
) -> dict[str, Any]:
    resolution_manifest = run_resolution_replay_cycle(
        input_dir=input_dir,
        status_out_dir=status_out_dir,
        model_forecasts_file=model_forecasts_file,
        benchmark_name=resolution_benchmark_name,
        provider=provider,
        model=model,
        cycle_manifest_path=resolution_cycle_manifest,
        forecast_root=forecast_root,
        survival_root=survival_root,
        scenario_prefix=scenario_prefix,
        source_rows=source_rows,
        summary_csv=resolution_summary_csv,
        summary_md=resolution_summary_md,
        rank_mode=rank_mode,
    )

    readiness = assess_readiness(
        model_manifest=load_benchmark_manifest(model_manifest),
        baseline_manifest=load_benchmark_manifest(baseline_manifest),
        resolution_manifest=resolution_manifest,
        resolution_cycle_manifest=resolution_manifest,
        oracle_metrics=load_json(resolve_oracle_metrics_path(oracle_metrics)),
        min_source_rows=min_source_rows,
        min_closed_trades=min_closed_trades,
        max_drawdown_limit=max_drawdown_limit,
    )
    atomic_write_json(readiness_json, readiness)
    write_readiness_markdown(readiness_md, readiness)

    variant_report = build_variant_report(
        forecast_root=forecast_root,
        output_csv=variant_csv,
        output_json=variant_json,
        output_md=variant_md,
        source_rows_filter=source_rows,
        readiness_json=readiness_json,
        max_drawdown_limit=max_drawdown_limit,
    )

    cycle_manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "source_rows": source_rows,
        "resolution_cycle_manifest": str(resolution_cycle_manifest),
        "resolution_replay_ran": bool(resolution_manifest.get("replay_ran")),
        "resolution_eligible": int(resolution_manifest.get("resolution_eligible", 0)),
        "near_binary_but_open": int(resolution_manifest.get("near_binary_but_open", 0)),
        "near_binary_disputed_open": int(resolution_manifest.get("near_binary_disputed_open", 0)),
        "readiness_json": str(readiness_json),
        "readiness_md": str(readiness_md),
        "readiness_decision": readiness["decision"],
        "readiness_blockers": readiness["blocker_count"],
        "paper_collection_decision": "CONTINUE_PAPER_LOGGING",
        "stale_reason": "no_new_official_resolutions; reports rebuilt from existing benchmark artifacts"
        if not bool(resolution_manifest.get("replay_ran")) and int(resolution_manifest.get("resolution_eligible", 0)) == 0
        else "",
        "enforcement_mode": "report_only_no_live_execution",
        "variant_json": str(variant_json),
        "variant_md": str(variant_md),
        "variant_count": variant_report["variant_count"],
        "note": "Paper gate cycle only. No orders were placed, signed, or submitted.",
    }
    return cycle_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper-only resolution, readiness, and model-variant gate cycle.")
    parser.add_argument("--input-dir", default="data/paper/model_bench_100")
    parser.add_argument("--status-out-dir", default="data/paper/resolution_status/model_bench_100")
    parser.add_argument("--model-forecasts-file", default="data/forecasts/next_model_blind_100/model_minimal.jsonl")
    parser.add_argument("--resolution-benchmark-name", default="next_model_blind_100_resolution_cycle")
    parser.add_argument("--provider", default="agy")
    parser.add_argument("--model", default="Gemini 3.5 Flash High via agy blind resolution_cycle")
    parser.add_argument("--resolution-cycle-manifest", default="data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json")
    parser.add_argument("--model-manifest", default="data/forecasts/next_model_blind_100/latest_benchmark_manifest.json")
    parser.add_argument("--baseline-manifest", default="data/forecasts/rule_baseline_100/latest_benchmark_manifest.json")
    parser.add_argument("--oracle-metrics", default="latest", help="Use a path or 'latest' to auto-select the newest oracle smoke metrics file.")
    parser.add_argument("--readiness-json", default="data/readiness/latest_strategy_readiness.json")
    parser.add_argument("--readiness-md", default="docs/strategy_readiness_gate.md")
    parser.add_argument("--variant-csv", default="data/forecasts/model_variant_comparison_100.csv")
    parser.add_argument("--variant-json", default="data/forecasts/model_variant_comparison_100.json")
    parser.add_argument("--variant-md", default="docs/model_variant_comparison_100.md")
    parser.add_argument("--forecast-root", default="data/forecasts")
    parser.add_argument("--survival-root", default="data/paper")
    parser.add_argument("--scenario-prefix", default="model_bench_100_survival_")
    parser.add_argument("--source-rows", type=int, default=100)
    parser.add_argument("--resolution-summary-csv", default="data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv")
    parser.add_argument("--resolution-summary-md", default="docs/model_bench_100_resolution_summary.md")
    parser.add_argument("--rank-mode", choices=["quality", "performance"], default="quality")
    parser.add_argument("--min-source-rows", type=int, default=100)
    parser.add_argument("--min-closed-trades", type=int, default=30)
    parser.add_argument("--max-drawdown-limit", type=float, default=0.25)
    parser.add_argument("--out-json", default="data/paper/paper_gate_cycle/latest_paper_gate_cycle.json")
    args = parser.parse_args()

    manifest = run_paper_gate_cycle(
        input_dir=Path(args.input_dir),
        status_out_dir=Path(args.status_out_dir),
        model_forecasts_file=Path(args.model_forecasts_file),
        resolution_benchmark_name=args.resolution_benchmark_name,
        provider=args.provider,
        model=args.model,
        resolution_cycle_manifest=Path(args.resolution_cycle_manifest),
        model_manifest=Path(args.model_manifest),
        baseline_manifest=Path(args.baseline_manifest),
        oracle_metrics=Path(args.oracle_metrics),
        readiness_json=Path(args.readiness_json),
        readiness_md=Path(args.readiness_md),
        variant_csv=Path(args.variant_csv),
        variant_json=Path(args.variant_json),
        variant_md=Path(args.variant_md),
        forecast_root=Path(args.forecast_root),
        survival_root=Path(args.survival_root),
        scenario_prefix=args.scenario_prefix,
        source_rows=args.source_rows,
        resolution_summary_csv=Path(args.resolution_summary_csv),
        resolution_summary_md=Path(args.resolution_summary_md),
        rank_mode=args.rank_mode,
        min_source_rows=args.min_source_rows,
        min_closed_trades=args.min_closed_trades,
        max_drawdown_limit=args.max_drawdown_limit,
    )
    atomic_write_json(Path(args.out_json), manifest)
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
