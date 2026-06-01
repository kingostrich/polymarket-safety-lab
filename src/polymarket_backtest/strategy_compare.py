from __future__ import annotations

import argparse
import csv
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .report_summary import safe_float, safe_int, safe_str


@dataclass(frozen=True)
class StrategyComparison:
    scenario: str
    run_timestamp: str
    state: str
    initial_bankroll: float
    final_equity: float
    return_on_investment: float
    event_max_drawdown: float
    timestamp_close_max_drawdown: float
    forecast_cost_total: float
    forecast_calls: int
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
    drawdown_policy: str
    legacy_mdd_fields: bool
    mixed_history: bool
    risk_flags: str
    screening_rank: int


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_summary_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def filter_rows_by_scenario_prefix(rows: list[dict[str, str]], scenario_prefix: str) -> list[dict[str, str]]:
    if not scenario_prefix:
        return rows
    return [row for row in rows if safe_str(row.get("scenario")).startswith(scenario_prefix)]


def run_sort_key(row: dict[str, str]) -> tuple[str, str]:
    return safe_str(row.get("run_timestamp")), safe_str(row.get("report_path"))


def latest_rows_by_scenario(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        scenario = safe_str(row.get("scenario"))
        if not scenario:
            continue
        if scenario not in latest or run_sort_key(row) > run_sort_key(latest[scenario]):
            latest[scenario] = row
    return list(latest.values())


def scenario_mixed_history(rows: list[dict[str, str]]) -> dict[str, bool]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(safe_str(row.get("scenario")), []).append(row)
    mixed: dict[str, bool] = {}
    for scenario, scenario_rows in grouped.items():
        signatures = {
            (
                safe_str(row.get("forecast_model")),
                safe_str(row.get("drawdown_policy")),
                safe_str(row.get("initial_bankroll")),
                safe_str(row.get("rows_processed")),
                safe_str(row.get("forecast_cost_total")),
                safe_str(row.get("positions_opened")),
                safe_str(row.get("exit_liquidity_skips")),
                safe_str(row.get("slippage_cost_total")),
            )
            for row in scenario_rows
        }
        mixed[scenario] = len(signatures) > 1
    return mixed


def risk_flags(row: dict[str, str], mixed_history: bool) -> str:
    flags: list[str] = []
    if safe_str(row.get("state")) != "ALIVE":
        flags.append("dead")
    if safe_int(row.get("positions_opened")) == 0:
        flags.append("no_trades")
    if safe_bool(row.get("legacy_mdd_fields")):
        flags.append("legacy_mdd")
    if mixed_history:
        flags.append("mixed_history")
    if safe_int(row.get("liquidity_skips")) > 0:
        flags.append("entry_liquidity")
    if safe_int(row.get("partial_entries")) > 0:
        flags.append("partial_entry")
    if safe_int(row.get("open_positions")) > 0:
        flags.append("open_positions")
    if safe_int(row.get("exit_liquidity_skips")) > 0:
        flags.append("exit_liquidity")
    if safe_int(row.get("partial_exits")) > 0:
        flags.append("partial_exit")
    if safe_float(row.get("unfilled_exit_notional")) > 0:
        flags.append("unfilled_exit")
    if safe_float(row.get("slippage_cost_total")) > 0:
        flags.append("slippage_cost")
    if safe_str(row.get("missing_fields")):
        flags.append("missing_fields")
    return ";".join(flags)


def comparison_sort_key(row: StrategyComparison, rank_mode: str = "triage") -> tuple[int, int, float, float, str]:
    if rank_mode == "performance":
        return (
            0 if row.state == "ALIVE" else 1,
            -row.return_on_investment,
            row.event_max_drawdown,
            1 if row.positions_opened > 0 else 0,
            row.scenario,
        )
    if rank_mode != "triage":
        raise ValueError(f"unknown rank mode: {rank_mode}")
    return (
        0 if row.state == "ALIVE" else 1,
        0 if row.positions_opened > 0 else 1,
        -row.return_on_investment,
        row.event_max_drawdown,
        row.scenario,
    )


def build_comparisons(
    rows: list[dict[str, str]],
    latest_only: bool = True,
    rank_mode: str = "triage",
) -> list[StrategyComparison]:
    source_rows = latest_rows_by_scenario(rows) if latest_only else rows
    mixed = scenario_mixed_history(rows)
    comparisons: list[StrategyComparison] = []
    for row in source_rows:
        scenario = safe_str(row.get("scenario"))
        comparisons.append(
            StrategyComparison(
                scenario=scenario,
                run_timestamp=safe_str(row.get("run_timestamp")),
                state=safe_str(row.get("state")),
                initial_bankroll=safe_float(row.get("initial_bankroll")),
                final_equity=safe_float(row.get("final_equity")),
                return_on_investment=safe_float(row.get("return_on_investment")),
                event_max_drawdown=safe_float(row.get("event_max_drawdown")),
                timestamp_close_max_drawdown=safe_float(row.get("timestamp_close_max_drawdown")),
                forecast_cost_total=safe_float(row.get("forecast_cost_total")),
                forecast_calls=safe_int(row.get("forecast_calls")),
                positions_opened=safe_int(row.get("positions_opened")),
                positions_closed=safe_int(row.get("positions_closed")),
                open_positions=safe_int(row.get("open_positions")),
                liquidity_skips=safe_int(row.get("liquidity_skips")),
                partial_entries=safe_int(row.get("partial_entries")),
                unfilled_entry_notional=safe_float(row.get("unfilled_entry_notional")),
                exit_liquidity_skips=safe_int(row.get("exit_liquidity_skips")),
                partial_exits=safe_int(row.get("partial_exits")),
                unfilled_exit_notional=safe_float(row.get("unfilled_exit_notional")),
                slippage_cost_total=safe_float(row.get("slippage_cost_total")),
                realized_pnl=safe_float(row.get("realized_pnl")),
                forecast_model=safe_str(row.get("forecast_model")),
                drawdown_policy=safe_str(row.get("drawdown_policy")),
                legacy_mdd_fields=safe_bool(row.get("legacy_mdd_fields")),
                mixed_history=mixed.get(scenario, False),
                risk_flags=risk_flags(row, mixed.get(scenario, False)),
                screening_rank=0,
            )
        )
    ranked = sorted(comparisons, key=lambda row: comparison_sort_key(row, rank_mode))
    return [
        StrategyComparison(**{**asdict(row), "screening_rank": index + 1})
        for index, row in enumerate(ranked)
    ]


def write_comparison_csv(rows: list[StrategyComparison], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(StrategyComparison.__dataclass_fields__.keys())
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    os.replace(tmp_path, output_path)


def write_markdown(rows: list[StrategyComparison], output_path: Path, rank_mode: str = "triage") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rank_mode == "performance":
        rank_description = "Screening rank is performance-oriented: ALIVE before DEAD, higher ROI, lower event MDD, then no-trade baselines before active loss-making runs when returns are otherwise similar. It is not an investment recommendation."
        rank_note = "`screening_rank` is performance-oriented, but it still does not prove a deployable strategy."
    else:
        rank_description = "Screening rank is a review heuristic: ALIVE before DEAD, scenarios with opened positions before no-trade baselines, higher ROI, then lower event MDD. It is not an investment recommendation."
        rank_note = "`screening_rank` is for active-strategy review triage only. It does not prove a deployable strategy."
    lines = [
        "# Survival Strategy Comparison",
        "",
        rank_description,
        "",
        "| rank | scenario | run | state | ROI | event MDD | forecast calls | opened | open | entry skips | partial entries | exit skips | unfilled exit | slippage cost | risk flags |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.screening_rank} | {row.scenario} | {row.run_timestamp} | {row.state} | "
            f"{row.return_on_investment:.2%} | {row.event_max_drawdown:.2%} | {row.forecast_calls} | "
            f"{row.positions_opened} | {row.open_positions} | {row.liquidity_skips} | "
            f"{row.partial_entries} | {row.exit_liquidity_skips} | {row.unfilled_exit_notional:.2f} | "
            f"{row.slippage_cost_total:.4f} | {row.risk_flags or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            f"- {rank_note}",
            "- Use `--rank-mode performance` when you want no-trade baselines and lower-loss runs to appear according to financial outcome rather than active-strategy debugging priority.",
            "- Prefer `event_max_drawdown` for conservative risk review; `timestamp_close_max_drawdown` can hide intra-timestamp stress.",
            "- `legacy_mdd` and `missing_fields` rows are weaker evidence because older reports lack some modern risk fields.",
            "- `open_positions`, `exit_liquidity`, `unfilled_exit`, `entry_liquidity`, `partial_entry`, `partial_exit`, and `slippage_cost` indicate execution-risk areas that require deeper event-level review.",
            "- Current depth and slippage models are top-3 aggregate approximations, not full order-book market-impact simulations.",
            "- Current forward logs are short samples; use this table to choose the next stress tests, not to infer live-trading performance.",
        ]
    )
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines) + "\n")
    os.replace(tmp_path, output_path)


def print_table(rows: list[StrategyComparison], limit: int) -> None:
    selected = rows[:limit] if limit > 0 else rows
    print("rank,scenario,run_timestamp,state,roi,event_mdd,timestamp_close_mdd,risk_flags")
    for row in selected:
        print(
            f"{row.screening_rank},{row.scenario},{row.run_timestamp},{row.state},"
            f"{row.return_on_investment:.6f},{row.event_max_drawdown:.6f},"
            f"{row.timestamp_close_max_drawdown:.6f},{row.risk_flags}"
        )
    if limit > 0 and len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare survival strategy scenarios from survival_report_summary.csv.")
    parser.add_argument("--summary-csv", default="data/paper/survival_report_summary.csv")
    parser.add_argument("--output-csv", default="data/paper/survival_strategy_comparison.csv")
    parser.add_argument("--output-md", default="docs/survival_strategy_comparison.md")
    parser.add_argument("--all-runs", action="store_true", help="Compare every run instead of only the latest run per scenario.")
    parser.add_argument("--scenario-prefix", default="", help="Only compare scenarios whose name starts with this prefix.")
    parser.add_argument("--rank-mode", default="triage", choices=["triage", "performance"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    rows = filter_rows_by_scenario_prefix(load_summary_rows(Path(args.summary_csv)), args.scenario_prefix)
    comparisons = build_comparisons(rows, latest_only=not args.all_runs, rank_mode=args.rank_mode)
    write_comparison_csv(comparisons, Path(args.output_csv))
    write_markdown(comparisons, Path(args.output_md), rank_mode=args.rank_mode)
    print_table(comparisons, args.limit)
    print(f"comparison_rows={len(comparisons)}")
    print(f"csv_path={args.output_csv}")
    print(f"markdown_path={args.output_md}")


if __name__ == "__main__":
    main()
