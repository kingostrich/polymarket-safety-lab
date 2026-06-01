from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model_benchmark_run import run_model_benchmark
from .paper_resolution_status import collect_statuses, write_outputs


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def run_resolution_replay_cycle(
    input_dir: Path,
    status_out_dir: Path,
    model_forecasts_file: Path,
    benchmark_name: str,
    provider: str,
    model: str,
    cycle_manifest_path: Path,
    forecast_root: Path = Path("data/forecasts"),
    survival_root: Path = Path("data/paper"),
    scenario_prefix: str = "model_bench_100_survival_",
    source_rows: int = 100,
    summary_csv: Path = Path("data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv"),
    summary_md: Path = Path("docs/model_bench_100_resolution_summary.md"),
    rank_mode: str = "quality",
) -> dict[str, Any]:
    statuses = collect_statuses(input_dir)
    resolution_manifest = write_outputs(statuses, status_out_dir)
    resolutions_csv = Path(str(resolution_manifest["resolutions_path"]))
    should_replay = int(resolution_manifest["resolution_eligible"]) > 0

    cycle_manifest: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "status_out_dir": str(status_out_dir),
        "resolution_manifest_path": str(status_out_dir / "resolution_manifest.json"),
        "resolutions_csv": str(resolutions_csv),
        "resolution_eligible": int(resolution_manifest["resolution_eligible"]),
        "near_binary_but_open": int(resolution_manifest["near_binary_but_open"]),
        "near_binary_disputed_open": int(resolution_manifest.get("near_binary_disputed_open", 0)),
        "benchmark_name": benchmark_name,
        "provider": provider,
        "model": model,
        "replay_ran": False,
        "replay_manifest_path": "",
        "skip_reason": "",
        "note": "Resolution replay cycle only. No orders were placed, signed, or submitted.",
    }
    if should_replay:
        replay_manifest = run_model_benchmark(
            input_dir=input_dir,
            model_forecasts_file=model_forecasts_file,
            benchmark_name=benchmark_name,
            provider=provider,
            model=model,
            forecast_root=forecast_root,
            survival_root=survival_root,
            summary_csv=summary_csv,
            summary_md=summary_md,
            resolutions_csv=resolutions_csv,
            scenario_prefix=scenario_prefix,
            summary_source_rows_filter=source_rows,
            rank_mode=rank_mode,
        )
        replay_manifest_path = forecast_root / benchmark_name / "latest_benchmark_manifest.json"
        cycle_manifest.update(
            {
                "replay_ran": True,
                "replay_manifest_path": str(replay_manifest_path),
                "replay_survival_report_path": replay_manifest["survival_report_path"],
                "positions_closed": replay_manifest["positions_closed"],
                "open_positions": replay_manifest["open_positions"],
                "realized_pnl": replay_manifest["realized_pnl"],
                "mark_equity": replay_manifest["final_equity"],
            }
        )
    else:
        cycle_manifest["skip_reason"] = "no_closed_resolution_eligible_markets"

    atomic_write_json(cycle_manifest_path, cycle_manifest)
    return cycle_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Check official paper-market resolutions and replay only when closed resolutions exist.")
    parser.add_argument("--input-dir", default="data/paper/model_bench_100")
    parser.add_argument("--status-out-dir", default="data/paper/resolution_status/model_bench_100")
    parser.add_argument("--model-forecasts-file", default="data/forecasts/next_model_blind_100/model_minimal.jsonl")
    parser.add_argument("--benchmark-name", default="next_model_blind_100_resolution_cycle")
    parser.add_argument("--provider", default="agy")
    parser.add_argument("--model", default="Gemini 3.5 Flash High via agy blind resolution_cycle")
    parser.add_argument("--cycle-manifest", default="data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json")
    parser.add_argument("--forecast-root", default="data/forecasts")
    parser.add_argument("--survival-root", default="data/paper")
    parser.add_argument("--scenario-prefix", default="model_bench_100_survival_")
    parser.add_argument("--source-rows", type=int, default=100)
    parser.add_argument("--summary-csv", default="data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv")
    parser.add_argument("--summary-md", default="docs/model_bench_100_resolution_summary.md")
    parser.add_argument("--rank-mode", choices=["quality", "performance"], default="quality")
    args = parser.parse_args()

    manifest = run_resolution_replay_cycle(
        input_dir=Path(args.input_dir),
        status_out_dir=Path(args.status_out_dir),
        model_forecasts_file=Path(args.model_forecasts_file),
        benchmark_name=args.benchmark_name,
        provider=args.provider,
        model=args.model,
        cycle_manifest_path=Path(args.cycle_manifest),
        forecast_root=Path(args.forecast_root),
        survival_root=Path(args.survival_root),
        scenario_prefix=args.scenario_prefix,
        source_rows=args.source_rows,
        summary_csv=Path(args.summary_csv),
        summary_md=Path(args.summary_md),
        rank_mode=args.rank_mode,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
