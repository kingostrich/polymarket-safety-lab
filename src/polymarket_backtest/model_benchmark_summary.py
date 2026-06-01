from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .report_summary import safe_float, safe_int, safe_str


@dataclass(frozen=True)
class ModelBenchmarkRow:
    benchmark: str
    forecast_dir: str
    audit_status: str
    source_rows: int
    forecast_records: int
    matched_records: int
    coverage: float
    total_cost: float
    provider: str
    model: str
    survival_scenario: str
    survival_state: str
    rows_processed: int
    forecast_calls: int
    initial_bankroll: float
    final_equity: float
    max_drawdown: float
    signals_seen: int
    positions_opened: int
    open_positions: int
    market_echo_share_1bp: float
    actionable_rows: int
    mean_abs_diff_to_yes_mid: float
    diagnosis_flags: str
    risk_flags: str
    benchmark_rank: int


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def parse_count_label(value: str) -> str:
    if not value:
        return ""
    if "," in value:
        return ""
    return value.rsplit(":", 1)[0]


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def load_audit_rows(forecast_root: Path) -> list[tuple[Path, dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for audit_path in sorted(forecast_root.glob("**/latest_audit.json")):
        audit = read_json(audit_path)
        manifest_path = audit_path.parent / "latest_manifest.json"
        manifest = read_json(manifest_path) if manifest_path.exists() else {}
        rows.append((audit_path.parent, audit, manifest))
    return rows


def load_survival_reports(survival_root: Path, scenario_prefix: str) -> list[tuple[str, dict[str, Any]]]:
    reports: list[tuple[str, dict[str, Any]]] = []
    for report_path in sorted(survival_root.glob(f"{scenario_prefix}*/latest_survival_report.json")):
        scenario = report_path.parent.name
        reports.append((scenario, read_json(report_path)))
    return reports


def survival_by_model(reports: list[tuple[str, dict[str, Any]]]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    indexed: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for scenario, report in reports:
        model = safe_str(report.get("forecast_model"))
        if not model:
            continue
        indexed.setdefault(model, []).append((scenario, report))
    return indexed


def select_survival_report(
    reports: list[tuple[str, dict[str, Any]]],
    source_rows: int,
    forecast_records: int,
) -> tuple[str, dict[str, Any]]:
    for scenario, report in reports:
        if safe_int(report.get("rows_processed")) == source_rows and safe_int(report.get("forecast_calls")) == forecast_records:
            return scenario, report
    return "", {}


def build_risk_flags(
    audit: dict[str, Any],
    survival: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None = None,
    unmatched_survival_count: int = 0,
) -> str:
    flags: list[str] = []
    if "," in safe_str(audit.get("provider_counts")):
        flags.append("multi_provider_counts")
    if "," in safe_str(audit.get("model_counts")):
        flags.append("multi_model_counts")
    if safe_str(audit.get("status")) != "PASS":
        flags.append("audit_fail")
    if safe_float(audit.get("coverage")) < 1.0:
        flags.append("partial_coverage")
    if safe_int(audit.get("input_hash_mismatches")) > 0:
        flags.append("hash_mismatch")
    if safe_int(audit.get("invalid_probabilities")) > 0:
        flags.append("invalid_probability")
    if safe_int(audit.get("invalid_costs")) > 0 or safe_int(audit.get("negative_costs")) > 0:
        flags.append("invalid_cost")
    if survival is None:
        flags.append("missing_survival")
        if unmatched_survival_count > 0:
            flags.append("survival_row_mismatch")
    else:
        if safe_str(survival.get("state")) != "ALIVE":
            flags.append("dead")
        if safe_int(survival.get("positions_opened")) == 0:
            flags.append("no_trades")
        if safe_int(survival.get("open_positions")) > 0:
            flags.append("open_positions")
        initial_bankroll = safe_float(survival.get("initial_bankroll"))
        final_equity = safe_float(survival.get("final_equity"))
        if initial_bankroll > 0 and final_equity < initial_bankroll:
            flags.append("loss")
    if diagnostics:
        for flag in safe_str(diagnostics.get("diagnosis_flags")).split(";"):
            if flag:
                flags.append(flag)
    return ";".join(flags)


def benchmark_sort_key(row: ModelBenchmarkRow, rank_mode: str = "quality") -> tuple:
    if rank_mode == "performance":
        return (
            0 if row.audit_status == "PASS" else 1,
            0 if row.survival_state == "ALIVE" else 1,
            -(row.final_equity - row.initial_bankroll),
            row.max_drawdown,
            row.total_cost,
            row.forecast_dir,
        )
    if rank_mode != "quality":
        raise ValueError(f"unknown rank mode: {rank_mode}")
    return (
        0 if row.audit_status == "PASS" else 1,
        0 if row.survival_state == "ALIVE" else 1,
        -row.coverage,
        row.total_cost,
        row.forecast_dir,
    )


def build_benchmark_rows(
    forecast_root: Path,
    survival_root: Path,
    scenario_prefix: str,
    source_rows_filter: int = 0,
    rank_mode: str = "quality",
) -> list[ModelBenchmarkRow]:
    survivals = survival_by_model(load_survival_reports(survival_root, scenario_prefix))
    rows: list[ModelBenchmarkRow] = []
    for forecast_dir, audit, manifest in load_audit_rows(forecast_root):
        source_rows = safe_int(audit.get("source_rows"))
        forecast_records = safe_int(audit.get("forecast_records"))
        if source_rows_filter > 0 and source_rows != source_rows_filter:
            continue
        provider = safe_str(manifest.get("provider")) or parse_count_label(safe_str(audit.get("provider_counts")))
        model = safe_str(manifest.get("model")) or parse_count_label(safe_str(audit.get("model_counts")))
        candidate_survivals = survivals.get(model, [])
        scenario, survival = select_survival_report(
            candidate_survivals,
            source_rows=source_rows,
            forecast_records=forecast_records,
        )
        survival_data = survival or None
        diagnostics_path = forecast_dir / "latest_diagnostics.json"
        diagnostics = read_json(diagnostics_path) if diagnostics_path.exists() else {}
        benchmark = forecast_dir.relative_to(forecast_root).as_posix()
        rows.append(
            ModelBenchmarkRow(
                benchmark=benchmark,
                forecast_dir=str(forecast_dir),
                audit_status=safe_str(audit.get("status")),
                source_rows=source_rows,
                forecast_records=forecast_records,
                matched_records=safe_int(audit.get("matched_records")),
                coverage=safe_float(audit.get("coverage")),
                total_cost=safe_float(first_present(manifest.get("total_cost"), audit.get("total_cost"))),
                provider=provider,
                model=model,
                survival_scenario=scenario,
                survival_state=safe_str(survival.get("state")),
                rows_processed=safe_int(survival.get("rows_processed")),
                forecast_calls=safe_int(survival.get("forecast_calls")),
                initial_bankroll=safe_float(survival.get("initial_bankroll")),
                final_equity=safe_float(survival.get("final_equity")),
                max_drawdown=safe_float(survival.get("max_drawdown")),
                signals_seen=safe_int(survival.get("signals_seen")),
                positions_opened=safe_int(survival.get("positions_opened")),
                open_positions=safe_int(survival.get("open_positions")),
                market_echo_share_1bp=safe_float(diagnostics.get("market_echo_share_1bp")),
                actionable_rows=safe_int(diagnostics.get("actionable_rows")),
                mean_abs_diff_to_yes_mid=safe_float(diagnostics.get("mean_abs_diff_to_yes_mid")),
                diagnosis_flags=safe_str(diagnostics.get("diagnosis_flags")),
                risk_flags=build_risk_flags(
                    audit,
                    survival_data,
                    diagnostics=diagnostics or None,
                    unmatched_survival_count=len(candidate_survivals),
                ),
                benchmark_rank=0,
            )
        )
    ranked = sorted(rows, key=lambda row: benchmark_sort_key(row, rank_mode))
    return [
        ModelBenchmarkRow(**{**asdict(row), "benchmark_rank": index + 1})
        for index, row in enumerate(ranked)
    ]


def write_csv(rows: list[ModelBenchmarkRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(ModelBenchmarkRow.__dataclass_fields__.keys())
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    os.replace(tmp_path, output_path)


def write_markdown(rows: list[ModelBenchmarkRow], output_path: Path, rank_mode: str = "quality") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rank_mode == "performance":
        rank_note = "Rows are ranked by audit pass, survival state, higher P&L versus initial bankroll, lower drawdown, then lower forecast cost."
    else:
        rank_note = "Rows are ranked by audit pass, survival state, source coverage, lower forecast cost, then path. This is a quality screen, not a return ranking."
    lines = [
        "# Model Benchmark Summary",
        "",
        "This table compares forecast-file audit results and matching survival replay results. It is a pipeline and model-output quality screen, not investment advice.",
        "",
        rank_note,
        "",
        "| rank | benchmark | provider | model | audit | coverage | echo <=1bp | actionable | cost | survival | initial | mark equity | mark P&L | calls | opened | open | risk flags |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        pnl = row.final_equity - row.initial_bankroll
        lines.append(
            "| "
            f"{row.benchmark_rank} | {row.benchmark} | {row.provider} | {row.model} | "
            f"{row.audit_status} | {row.coverage:.2%} | {row.market_echo_share_1bp:.2%} | "
            f"{row.actionable_rows} | {row.total_cost:.4f} | "
            f"{row.survival_state or 'missing'} | {row.initial_bankroll:.2f} | {row.final_equity:.2f} | {pnl:.2f} | "
            f"{row.forecast_calls} | {row.positions_opened} | {row.open_positions} | {row.risk_flags or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `audit_status=PASS` means the forecast file has full source-row coverage, valid probabilities/costs, and matching input hashes.",
            "- `missing_survival` means a forecast file exists but no matching replay report was found for its model label.",
            "- `survival_row_mismatch` means a same-label survival report exists, but its row count or forecast-call count does not match the audit file.",
            "- `multi_provider_counts` and `multi_model_counts` require explicit manifest labels before model-to-survival matching can be trusted.",
            "- `market_echo` means most forecasts are effectively the YES bid/ask midpoint; that is useful for plumbing but weak evidence of independent predictive signal.",
            "- `actionable` counts forecasts whose YES or NO edge crosses the configured strategy threshold before liquidity and portfolio constraints.",
            "- `cost` is forecast/model cost from the imported forecast file; it is not gas, exchange fees, or order-execution slippage.",
            "- `calls` is the number of forecast lookups consumed by the replay; `opened` and `open` are opened positions and positions still unresolved at replay end.",
            "- `mark equity` is cash plus open-position mark value at the replay engine's effective bid price, using the last valid bid when configured. Treat it as provisional when `open > 0` because unresolved exposure can still move before market resolution.",
            "- `mark P&L` is `mark equity - initial`; `loss` and `open_positions` indicate the replay ended below starting bankroll or with unresolved exposure.",
            "- `no_trades` is not automatically bad in a smoke test; it means the imported fair values did not cross the strategy's edge threshold.",
            "- Use full-history runs, not 20-row smoke subsets, for ROI and drawdown claims.",
        ]
    )
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines) + "\n")
    os.replace(tmp_path, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize model forecast audit and survival replay outputs.")
    parser.add_argument("--forecast-root", default="data/forecasts")
    parser.add_argument("--survival-root", default="data/paper")
    parser.add_argument("--scenario-prefix", default="model_bench_20_survival_")
    parser.add_argument("--source-rows", type=int, default=0, help="Only include audits with this source row count; 0 includes all.")
    parser.add_argument("--rank-mode", choices=["quality", "performance"], default="quality")
    parser.add_argument("--output-csv", default="data/forecasts/model_benchmark_summary.csv")
    parser.add_argument("--output-md", default="docs/model_benchmark_summary.md")
    args = parser.parse_args()

    rows = build_benchmark_rows(
        forecast_root=Path(args.forecast_root),
        survival_root=Path(args.survival_root),
        scenario_prefix=args.scenario_prefix,
        source_rows_filter=args.source_rows,
        rank_mode=args.rank_mode,
    )
    write_csv(rows, Path(args.output_csv))
    write_markdown(rows, Path(args.output_md), rank_mode=args.rank_mode)
    print(f"rows={len(rows)}")
    print(f"csv_path={args.output_csv}")
    print(f"md_path={args.output_md}")
    if rows:
        print(f"top_benchmark={rows[0].benchmark}")
        print(f"top_audit_status={rows[0].audit_status}")
        print(f"top_survival_state={rows[0].survival_state or 'missing'}")


if __name__ == "__main__":
    main()
