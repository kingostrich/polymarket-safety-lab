from __future__ import annotations

import argparse

from .simulator import load_snapshots, run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Polymarket PDF-strategy backtest scaffold.")
    parser.add_argument("--snapshots", required=True, help="CSV snapshot path")
    parser.add_argument("--bankroll", type=float, default=100.0)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--max-fraction", type=float, default=0.06)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    args = parser.parse_args()

    snapshots = load_snapshots(args.snapshots)
    result = run_backtest(
        snapshots,
        initial_bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        max_fraction=args.max_fraction,
        slippage_bps=args.slippage_bps,
    )

    print(f"initial_bankroll={result.initial_bankroll:.2f}")
    print(f"final_equity={result.final_equity:.2f}")
    print(f"total_return={result.total_return:.2%}")
    print(f"max_drawdown={result.max_drawdown:.2%}")
    print(f"win_rate={result.win_rate:.2%}")
    print(f"closed_trades={len(result.closed_trades)}")


if __name__ == "__main__":
    main()
