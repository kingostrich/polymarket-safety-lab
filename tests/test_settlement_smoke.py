import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.settlement_smoke import build_oracle_smoke_rows, write_rows


class SettlementSmokeTest(unittest.TestCase):
    def test_build_oracle_smoke_rows_moves_fair_value_toward_resolved_outcome(self) -> None:
        rows = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "market_id": "m_yes",
                "question": "Yes?",
                "yes_price": "0.40",
                "no_price": "0.60",
                "fair_yes": "0.40",
                "liquidity": "1",
                "volume_24h": "1",
                "resolved_outcome": "",
                "fee_rate": "0",
            },
            {
                "timestamp": "2026-01-02T00:00:00+00:00",
                "market_id": "m_yes",
                "question": "Yes?",
                "yes_price": "1.00",
                "no_price": "0.00",
                "fair_yes": "1.00",
                "liquidity": "1",
                "volume_24h": "1",
                "resolved_outcome": "YES",
                "fee_rate": "0",
            },
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "market_id": "m_no",
                "question": "No?",
                "yes_price": "0.40",
                "no_price": "0.60",
                "fair_yes": "0.40",
                "liquidity": "1",
                "volume_24h": "1",
                "resolved_outcome": "",
                "fee_rate": "0",
            },
            {
                "timestamp": "2026-01-02T00:00:00+00:00",
                "market_id": "m_no",
                "question": "No?",
                "yes_price": "0.00",
                "no_price": "1.00",
                "fair_yes": "0.00",
                "liquidity": "1",
                "volume_24h": "1",
                "resolved_outcome": "NO",
                "fee_rate": "0",
            },
        ]

        output = build_oracle_smoke_rows(rows, edge=0.12)

        self.assertEqual(output[0]["fair_yes"], "0.520000")
        self.assertEqual(output[1]["fair_yes"], "1.00")
        self.assertEqual(output[2]["fair_yes"], "0.280000")
        self.assertEqual(output[3]["fair_yes"], "0.00")

    def test_write_rows_round_trips_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.csv"
            rows = [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "market_id": "m",
                    "question": "Q",
                    "yes_price": "0.4",
                    "no_price": "0.6",
                    "fair_yes": "0.5",
                    "liquidity": "1",
                    "volume_24h": "1",
                    "resolved_outcome": "",
                    "fee_rate": "0",
                }
            ]

            write_rows(path, rows)

            with path.open(newline="") as handle:
                loaded = list(csv.DictReader(handle))
            self.assertEqual(loaded, rows)


if __name__ == "__main__":
    unittest.main()
