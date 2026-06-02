from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from polymarket_backtest.forecast_providers import ForecastFileProvider, create_forecast_provider
from polymarket_backtest.survival import (
    SurvivalEvent,
    load_paper_rows,
    load_resolutions,
    simulate_survival,
)


@dataclass(frozen=True)
class ExitThresholdRow:
    rank: int
    exit_edge_threshold: float
    state: str
    death_reason: str
    roi: float
    event_sharpe_smoke: float
    max_drawdown: float
    event_max_drawdown: float
    timestamp_close_max_drawdown: float
    initial_bankroll: float
    final_equity: float
    mark_pnl: float
    realized_pnl: float
    forecast_cost_total: float
    slippage_cost_total: float
    total_cost_paid: float
    rows_processed: int
    forecast_calls: int
    positions_opened: int
    positions_closed: int
    open_positions: int
    exit_liquidity_skips: int
    partial_exits: int
    unfilled_exit_notional: float


def threshold_range(start: float, stop: float, step: float) -> list[float]:
    start_value = Decimal(str(start))
    stop_value = Decimal(str(stop))
    step_value = Decimal(str(step))
    if step_value <= 0:
        raise ValueError("step must be positive")
    if stop_value < start_value:
        raise ValueError("stop must be greater than or equal to start")
    values: list[float] = []
    current = start_value
    while current <= stop_value:
        values.append(round(float(current), 10))
        if len(values) > 10_000:
            raise ValueError("threshold range is too large")
        current += step_value
    return values


def event_equity_returns(initial_bankroll: float, events: list[SurvivalEvent]) -> list[float]:
    equity_values = [initial_bankroll]
    equity_values.extend(event.equity for event in events if event.equity > 0 or event.event_type == "DEAD")
    returns: list[float] = []
    for before, after in zip(equity_values, equity_values[1:]):
        if before > 0:
            returns.append((after - before) / before)
    return returns


def event_sharpe_smoke(initial_bankroll: float, events: list[SurvivalEvent]) -> float:
    returns = event_equity_returns(initial_bankroll, events)
    if len(returns) < 2:
        return 0.0
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    stdev = math.sqrt(variance)
    if stdev <= 1e-12:
        return 0.0
    return mean_return / stdev


def rank_rows(rows: list[ExitThresholdRow]) -> list[ExitThresholdRow]:
    ranked = sorted(
        rows,
        key=lambda row: (
            0 if row.state == "ALIVE" else 1,
            -row.roi,
            row.max_drawdown,
            row.open_positions,
            -row.realized_pnl,
            row.exit_edge_threshold,
        ),
    )
    return [ExitThresholdRow(**{**asdict(row), "rank": index + 1}) for index, row in enumerate(ranked)]


def write_csv_rows(path: Path, rows: list[ExitThresholdRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(ExitThresholdRow.__dataclass_fields__.keys())
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    os.replace(tmp_path, path)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp_path, path)


def write_markdown(path: Path, rows: list[ExitThresholdRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Exit Threshold Sweep",
        "",
        "This report compares paper-only survival replays across `edge_below` exit thresholds. It is not investment advice and does not authorize live trading.",
        "",
        "Rows are ranked by survival state, higher marked ROI, lower max drawdown, fewer open positions, higher realized P&L, then lower threshold.",
        "",
        "| rank | exit threshold | state | ROI | event Sharpe smoke | MDD | final equity | mark P&L | realized P&L | costs | calls | opened | closed | open | exit skips |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.rank} | {row.exit_edge_threshold:.4f} | {row.state} | {row.roi:.2%} | "
            f"{row.event_sharpe_smoke:.4f} | {row.max_drawdown:.2%} | {row.final_equity:.2f} | "
            f"{row.mark_pnl:.2f} | {row.realized_pnl:.2f} | {row.total_cost_paid:.4f} | "
            f"{row.forecast_calls} | {row.positions_opened} | {row.positions_closed} | {row.open_positions} | "
            f"{row.exit_liquidity_skips} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `costs` is `forecast_cost_total + slippage_cost_total`; it is not gas, exchange fees, or live execution cost.",
            "- `event Sharpe smoke` is computed over irregular replay event-equity returns. It is a smoke metric for comparing the same replay rows, not a production portfolio statistic.",
            "- Prefer settled P&L and official-resolution replay before treating any threshold as a strategy improvement.",
        ]
    )
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines) + "\n")
    os.replace(tmp_path, path)


def run_sweep(
    input_dir: Path,
    out_dir: Path,
    thresholds: list[float],
    bankroll: float = 50.0,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
    max_positions: int = 10,
    death_threshold: float = 0.0,
    resolutions_csv: Path | None = None,
    liquidity_model: str = "none",
    max_depth_fraction: float = 0.25,
    entry_fill_policy: str = "all_or_none",
    exit_liquidity_model: str = "none",
    max_exit_depth_fraction: float = 0.25,
    slippage_model: str = "none",
    max_slippage_bps: float = 50.0,
    missing_quote_policy: str = "zero",
    forecast_call_policy: str = "always",
    timestamp_order_policy: str = "sequential",
    drawdown_policy: str = "event",
    forecast_mode: str = "recorded",
    forecasts_file: Path | None = None,
    allow_missing_forecasts: bool = False,
    forecast_cost: float = 0.0,
    synthetic_edge: float = 0.12,
    synthetic_side: str = "YES",
) -> dict[str, str | int | float]:
    rows = load_paper_rows(input_dir)
    if not rows:
        raise ValueError(f"no paper rows found in {input_dir}")
    resolutions = load_resolutions(resolutions_csv) if resolutions_csv else {}
    if forecasts_file:
        provider = ForecastFileProvider(forecasts_file, allow_missing=allow_missing_forecasts)
    else:
        provider = create_forecast_provider(
            forecast_mode,
            cost_per_forecast=forecast_cost,
            synthetic_edge=synthetic_edge,
            synthetic_side=synthetic_side,
        )
    sweep_rows: list[ExitThresholdRow] = []
    for threshold in thresholds:
        result, events = simulate_survival(
            rows,
            provider=provider,
            resolutions=resolutions,
            initial_bankroll=bankroll,
            edge_threshold=edge_threshold,
            max_fraction=max_fraction,
            max_positions=max_positions,
            death_threshold=death_threshold,
            exit_policy="edge_below",
            exit_edge_threshold=threshold,
            liquidity_model=liquidity_model,
            max_depth_fraction=max_depth_fraction,
            entry_fill_policy=entry_fill_policy,
            exit_liquidity_model=exit_liquidity_model,
            max_exit_depth_fraction=max_exit_depth_fraction,
            slippage_model=slippage_model,
            max_slippage_bps=max_slippage_bps,
            missing_quote_policy=missing_quote_policy,
            forecast_call_policy=forecast_call_policy,
            timestamp_order_policy=timestamp_order_policy,
            drawdown_policy=drawdown_policy,
        )
        mark_pnl = result.final_equity - result.initial_bankroll
        total_cost_paid = result.forecast_cost_total + result.slippage_cost_total
        roi = mark_pnl / result.initial_bankroll if result.initial_bankroll > 0 else 0.0
        sweep_rows.append(
            ExitThresholdRow(
                rank=0,
                exit_edge_threshold=threshold,
                state=result.state,
                death_reason=result.death_reason,
                roi=roi,
                event_sharpe_smoke=event_sharpe_smoke(result.initial_bankroll, events),
                max_drawdown=result.max_drawdown,
                event_max_drawdown=result.event_max_drawdown,
                timestamp_close_max_drawdown=result.timestamp_close_max_drawdown,
                initial_bankroll=result.initial_bankroll,
                final_equity=result.final_equity,
                mark_pnl=mark_pnl,
                realized_pnl=result.realized_pnl,
                forecast_cost_total=result.forecast_cost_total,
                slippage_cost_total=result.slippage_cost_total,
                total_cost_paid=total_cost_paid,
                rows_processed=result.rows_processed,
                forecast_calls=result.forecast_calls,
                positions_opened=result.positions_opened,
                positions_closed=result.positions_closed,
                open_positions=result.open_positions,
                exit_liquidity_skips=result.exit_liquidity_skips,
                partial_exits=result.partial_exits,
                unfilled_exit_notional=result.unfilled_exit_notional,
            )
        )

    ranked_rows = rank_rows(sweep_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "exit_threshold_sweep.csv"
    md_path = out_dir / "exit_threshold_sweep.md"
    manifest_path = out_dir / "exit_threshold_sweep_manifest.json"
    write_csv_rows(csv_path, ranked_rows)
    write_markdown(md_path, ranked_rows)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "rows_loaded": len(rows),
        "thresholds": thresholds,
        "best_threshold": ranked_rows[0].exit_edge_threshold if ranked_rows else None,
        "best_roi": ranked_rows[0].roi if ranked_rows else None,
        "best_realized_pnl": ranked_rows[0].realized_pnl if ranked_rows else None,
        "production_safe": False,
        "readiness_decision": "NO_LIVE_TRADING",
        "csv_path": str(csv_path),
        "md_path": str(md_path),
        "note": "Paper-only threshold sweep. No orders were placed, signed, or submitted.",
    }
    write_json(manifest_path, manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep paper-only edge_below exit thresholds.")
    parser.add_argument("--input-dir", default="data/paper/model_bench_100")
    parser.add_argument("--out-dir", default="data/paper/exit_threshold_sweep")
    parser.add_argument("--threshold-start", type=float, default=0.01)
    parser.add_argument("--threshold-stop", type=float, default=0.20)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--bankroll", type=float, default=50.0)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--max-fraction", type=float, default=0.06)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--death-threshold", type=float, default=0.0)
    parser.add_argument("--resolutions-csv")
    parser.add_argument("--liquidity-model", default="none", choices=["none", "top3_ask"])
    parser.add_argument("--max-depth-fraction", type=float, default=0.25)
    parser.add_argument("--entry-fill-policy", default="all_or_none", choices=["all_or_none", "partial"])
    parser.add_argument("--exit-liquidity-model", default="none", choices=["none", "top3_bid"])
    parser.add_argument("--max-exit-depth-fraction", type=float, default=0.25)
    parser.add_argument("--slippage-model", default="none", choices=["none", "depth_utilization"])
    parser.add_argument("--max-slippage-bps", type=float, default=50.0)
    parser.add_argument("--missing-quote-policy", default="zero", choices=["zero", "last_valid_bid"])
    parser.add_argument("--forecast-call-policy", default="always", choices=["always", "actionable"])
    parser.add_argument("--timestamp-order-policy", default="sequential", choices=["sequential", "history_first", "position_first"])
    parser.add_argument("--drawdown-policy", default="event", choices=["event", "timestamp_close"])
    parser.add_argument("--forecast-mode", default="recorded", choices=["recorded", "rule_baseline", "synthetic_edge"])
    parser.add_argument("--forecasts-file")
    parser.add_argument("--allow-missing-forecasts", action="store_true")
    parser.add_argument("--forecast-cost", type=float, default=0.0)
    parser.add_argument("--synthetic-edge", type=float, default=0.12)
    parser.add_argument("--synthetic-side", default="YES", choices=["YES", "NO"])
    args = parser.parse_args()

    manifest = run_sweep(
        input_dir=Path(args.input_dir),
        out_dir=Path(args.out_dir),
        thresholds=threshold_range(args.threshold_start, args.threshold_stop, args.threshold_step),
        bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        max_fraction=args.max_fraction,
        max_positions=args.max_positions,
        death_threshold=args.death_threshold,
        resolutions_csv=Path(args.resolutions_csv) if args.resolutions_csv else None,
        liquidity_model=args.liquidity_model,
        max_depth_fraction=args.max_depth_fraction,
        entry_fill_policy=args.entry_fill_policy,
        exit_liquidity_model=args.exit_liquidity_model,
        max_exit_depth_fraction=args.max_exit_depth_fraction,
        slippage_model=args.slippage_model,
        max_slippage_bps=args.max_slippage_bps,
        missing_quote_policy=args.missing_quote_policy,
        forecast_call_policy=args.forecast_call_policy,
        timestamp_order_policy=args.timestamp_order_policy,
        drawdown_policy=args.drawdown_policy,
        forecast_mode=args.forecast_mode,
        forecasts_file=Path(args.forecasts_file) if args.forecasts_file else None,
        allow_missing_forecasts=args.allow_missing_forecasts,
        forecast_cost=args.forecast_cost,
        synthetic_edge=args.synthetic_edge,
        synthetic_side=args.synthetic_side,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
