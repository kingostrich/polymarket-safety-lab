from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.sample_validate import validate_sample


class SampleValidateTest(unittest.TestCase):
    def test_mock_sample_passes_validation(self) -> None:
        report = validate_sample(Path("data/mock/snapshots.csv"))

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["rows"], 8)
        self.assertEqual(report["markets"], 3)
        self.assertGreater(report["resolved_rows"], 0)

    def test_missing_required_column_fails_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "timestamp,market_id,question,yes_price,no_price,fair_yes,liquidity,volume_24h,resolved_outcome\n"
                "2026-05-01T00:00:00+00:00,m1,q,0.5,0.5,0.6,100,50,\n",
                encoding="utf-8",
            )

            report = validate_sample(path)

        self.assertEqual(report["status"], "FAIL")
        required = next(check for check in report["checks"] if check["name"] == "required_columns")
        self.assertEqual(required["status"], "FAIL")
        self.assertIn("fee_rate", required["detail"])

    def test_invalid_binary_price_sum_fails_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "timestamp,market_id,question,yes_price,no_price,fair_yes,liquidity,volume_24h,resolved_outcome,fee_rate\n"
                "2026-05-01T00:00:00+00:00,m1,q,0.8,0.8,0.6,100,50,,0\n",
                encoding="utf-8",
            )

            report = validate_sample(path)

        price_sum = next(check for check in report["checks"] if check["name"] == "binary_price_sums_near_one")
        self.assertEqual(price_sum["status"], "FAIL")

    def test_malformed_numeric_value_fails_without_raising(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "timestamp,market_id,question,yes_price,no_price,fair_yes,liquidity,volume_24h,resolved_outcome,fee_rate\n"
                "2026-05-01T00:00:00+00:00,m1,q,not-a-number,0.5,0.6,100,50,,0\n",
                encoding="utf-8",
            )

            report = validate_sample(path)

        self.assertEqual(report["status"], "FAIL")
        loadable = next(check for check in report["checks"] if check["name"] == "loadable_csv")
        self.assertEqual(loadable["status"], "FAIL")

    def test_negative_fee_rate_fails_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "timestamp,market_id,question,yes_price,no_price,fair_yes,liquidity,volume_24h,resolved_outcome,fee_rate\n"
                "2026-05-01T00:00:00+00:00,m1,q,0.5,0.5,0.6,100,50,,0\n"
                "2026-05-01T00:00:00+00:00,m2,q,0.5,0.5,0.6,100,50,,-0.01\n"
                "2026-05-02T00:00:00+00:00,m1,q,1,0,1,0,0,YES,0\n",
                encoding="utf-8",
            )

            report = validate_sample(path)

        fee_rate = next(check for check in report["checks"] if check["name"] == "fee_rates_in_unit_interval")
        self.assertEqual(fee_rate["status"], "FAIL")

    def test_out_of_order_rows_within_market_fail_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "timestamp,market_id,question,yes_price,no_price,fair_yes,liquidity,volume_24h,resolved_outcome,fee_rate\n"
                "2026-05-02T00:00:00+00:00,m1,q,0.5,0.5,0.6,100,50,,0\n"
                "2026-05-01T00:00:00+00:00,m1,q,0.5,0.5,0.6,100,50,,0\n"
                "2026-05-02T00:00:00+00:00,m2,q,1,0,1,0,0,YES,0\n",
                encoding="utf-8",
            )

            report = validate_sample(path)

        chronological = next(check for check in report["checks"] if check["name"] == "market_timestamps_chronological")
        self.assertEqual(chronological["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
