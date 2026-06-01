from __future__ import annotations

import argparse
from pathlib import Path

from .collectors import collect_historical_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect recent resolved binary Polymarket data for backtest ingestion.")
    parser.add_argument("--out-dir", default="data/normalized/polymarket_recent_binary")
    parser.add_argument("--markets", type=int, default=30)
    parser.add_argument("--interval", default="1d", choices=["1m", "1w", "1d", "6h", "1h"])
    parser.add_argument("--fidelity", type=int, default=60)
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    manifest = collect_historical_dataset(
        out_dir=Path(args.out_dir),
        markets_count=args.markets,
        interval=args.interval,
        fidelity=args.fidelity,
        max_pages=args.max_pages,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
