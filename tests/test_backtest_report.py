import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.backtest_report import run_and_write_report


class BacktestReportTest(unittest.TestCase):
    def test_run_and_write_report_outputs_metrics_trades_and_equity(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots.csv"
            with snapshots.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "timestamp",
                        "market_id",
                        "question",
                        "yes_price",
                        "no_price",
                        "fair_yes",
                        "liquidity",
                        "volume_24h",
                        "resolved_outcome",
                        "fee_rate",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_price": "0.50",
                        "no_price": "0.50",
                        "fair_yes": "0.62",
                        "liquidity": "1000",
                        "volume_24h": "100",
                        "resolved_outcome": "",
                        "fee_rate": "0",
                    }
                )
                writer.writerow(
                    {
                        "timestamp": "2026-01-02T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_price": "1.00",
                        "no_price": "0.00",
                        "fair_yes": "1.00",
                        "liquidity": "1000",
                        "volume_24h": "100",
                        "resolved_outcome": "YES",
                        "fee_rate": "0",
                    }
                )

            manifest = run_and_write_report(snapshots, root / "report", bankroll=100)

            self.assertEqual(manifest["closed_trades"], 1)
            metrics = json.loads((root / "report" / "metrics.json").read_text())
            self.assertEqual(metrics["closed_trades"], 1)
            self.assertTrue((root / "report" / "closed_trades.csv").exists())
            self.assertTrue((root / "report" / "equity_curve.csv").exists())


if __name__ == "__main__":
    unittest.main()
