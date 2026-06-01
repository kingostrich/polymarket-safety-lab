import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.forecast_providers import ForecastFileProvider, RuleBaselineForecastProvider
from polymarket_backtest.forecast_runner import build_forecast_records, row_input_hash, write_forecast_records
from polymarket_backtest.survival import simulate_survival


ROW = {
    "logged_at": "2026-01-01T00:00:00+00:00",
    "market_id": "m1",
    "question": "Will it happen?",
    "yes_ask": "0.52",
    "no_ask": "0.50",
    "yes_bid": "0.48",
    "no_bid": "0.47",
    "fair_yes": "0.52",
    "liquidity": "1000",
    "volume_24h": "100",
}


class ForecastRunnerTest(unittest.TestCase):
    def test_rule_baseline_uses_yes_midpoint(self) -> None:
        forecast = RuleBaselineForecastProvider().forecast(ROW)
        self.assertAlmostEqual(forecast.fair_yes, 0.50)
        self.assertEqual(forecast.cost, 0.0)

    def test_input_hash_is_stable_for_same_fields(self) -> None:
        changed = dict(ROW)
        changed["skip_reason"] = "ignored"
        self.assertEqual(row_input_hash(ROW), row_input_hash(changed))

    def test_writes_forecast_records_and_survival_consumes_jsonl(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            records = build_forecast_records([ROW], provider_mode="rule_baseline")
            manifest = write_forecast_records(records, out_dir)

            self.assertEqual(manifest["records"], 1)
            provider = ForecastFileProvider(out_dir / "latest_forecasts.jsonl")
            result, events = simulate_survival([ROW], provider, initial_bankroll=50)

            self.assertEqual(result.positions_opened, 0)
            self.assertEqual(events, [])

    def test_forecast_file_provider_reads_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "forecasts.csv"
            records = build_forecast_records([ROW], provider_mode="rule_baseline")
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0].__dict__.keys()))
                writer.writeheader()
                writer.writerow(records[0].__dict__)

            forecast = ForecastFileProvider(path).forecast(ROW)
            self.assertAlmostEqual(forecast.fair_yes, 0.50)

    def test_forecast_file_provider_accepts_uppercase_jsonl_suffix(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            records = build_forecast_records([ROW], provider_mode="rule_baseline")
            write_forecast_records(records, out_dir)
            uppercase_path = out_dir / "FORECASTS.JSONL"
            uppercase_path.write_text((out_dir / "latest_forecasts.jsonl").read_text())

            forecast = ForecastFileProvider(uppercase_path).forecast(ROW)
            self.assertAlmostEqual(forecast.fair_yes, 0.50)

    def test_forecast_file_provider_normalizes_timestamp_keys(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            records = build_forecast_records([ROW], provider_mode="rule_baseline")
            write_forecast_records(records, out_dir)
            row = dict(ROW)
            row["logged_at"] = "2026-01-01T09:00:00+09:00"

            forecast = ForecastFileProvider(out_dir / "latest_forecasts.jsonl").forecast(row)
            self.assertAlmostEqual(forecast.fair_yes, 0.50)


if __name__ == "__main__":
    unittest.main()
