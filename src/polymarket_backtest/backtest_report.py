from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict
from pathlib import Path

from .simulator import load_snapshots, run_backtest


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)


def run_and_write_report(
    snapshots_path: Path,
    out_dir: Path,
    bankroll: float = 100.0,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
    slippage_bps: float = 0.0,
) -> dict[str, str | float | int]:
    snapshots = load_snapshots(snapshots_path)
    result = run_backtest(
        snapshots,
        initial_bankroll=bankroll,
        edge_threshold=edge_threshold,
        max_fraction=max_fraction,
        slippage_bps=slippage_bps,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        "snapshots_path": str(snapshots_path),
        "snapshots": len(snapshots),
        "initial_bankroll": result.initial_bankroll,
        "final_equity": result.final_equity,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "closed_trades": len(result.closed_trades),
        "bankroll": bankroll,
        "edge_threshold": edge_threshold,
        "max_fraction": max_fraction,
        "slippage_bps": slippage_bps,
        "note": "Backtest report only. No orders were placed, signed, or submitted.",
    }
    metrics_path = out_dir / "metrics.json"
    trades_path = out_dir / "closed_trades.csv"
    equity_path = out_dir / "equity_curve.csv"
    atomic_write_text(metrics_path, json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
    trade_rows = [
        {
            **asdict(trade),
            "side": trade.side.value,
            "entry_time": trade.entry_time.isoformat(),
            "exit_time": trade.exit_time.isoformat(),
        }
        for trade in result.closed_trades
    ]
    write_csv(
        trades_path,
        trade_rows,
        ["market_id", "side", "entry_time", "exit_time", "shares", "entry_price", "exit_price", "pnl", "fees_paid"],
    )
    equity_rows = [{"timestamp": timestamp.isoformat(), "equity": equity} for timestamp, equity in result.equity_curve]
    write_csv(equity_path, equity_rows, ["timestamp", "equity"])
    return {
        **metrics,
        "metrics_path": str(metrics_path),
        "trades_path": str(trades_path),
        "equity_path": str(equity_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run simulator backtest and write metrics, closed trades, and equity curve.")
    parser.add_argument("--snapshots", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bankroll", type=float, default=100.0)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--max-fraction", type=float, default=0.06)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    args = parser.parse_args()

    manifest = run_and_write_report(
        snapshots_path=Path(args.snapshots),
        out_dir=Path(args.out_dir),
        bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        max_fraction=args.max_fraction,
        slippage_bps=args.slippage_bps,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
