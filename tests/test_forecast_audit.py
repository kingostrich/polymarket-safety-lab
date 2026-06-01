import unittest

from polymarket_backtest.forecast_audit import audit_forecasts
from polymarket_backtest.forecast_runner import row_input_hash

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


def forecast_row(**overrides):
    row = {
        "generated_at": "2026-01-01T00:01:00+00:00",
        "logged_at": ROW["logged_at"],
        "market_id": ROW["market_id"],
        "question": ROW["question"],
        "provider": "test_provider",
        "model": "test_model",
        "fair_yes": 0.50,
        "cost": 0.01,
        "reasoning": "test reasoning",
        "input_hash": row_input_hash(ROW),
        "yes_bid": 0.48,
        "yes_ask": 0.52,
        "no_bid": 0.47,
        "no_ask": 0.50,
        "liquidity": 1000,
        "volume_24h": 100,
    }
    row.update(overrides)
    return row


class ForecastAuditTest(unittest.TestCase):
    def test_valid_forecast_file_passes(self) -> None:
        result = audit_forecasts([ROW], [forecast_row()])

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.source_rows, 1)
        self.assertEqual(result.forecast_records, 1)
        self.assertEqual(result.matched_records, 1)
        self.assertAlmostEqual(result.coverage, 1.0)
        self.assertAlmostEqual(result.total_cost, 0.01)
        self.assertEqual(result.provider_counts, "test_provider:1")

    def test_missing_forecast_fails(self) -> None:
        result = audit_forecasts([ROW], [])

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.missing_forecasts, 1)
        self.assertEqual(result.coverage, 0.0)

    def test_extra_duplicate_invalid_and_hash_mismatch_fail(self) -> None:
        extra = forecast_row(market_id="m2", input_hash="bad", fair_yes=1.2, cost=-1, reasoning="")
        result = audit_forecasts([ROW], [forecast_row(input_hash="bad"), forecast_row(), extra])

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.duplicate_forecast_keys, 1)
        self.assertEqual(result.extra_forecasts, 1)
        self.assertEqual(result.input_hash_mismatches, 1)
        self.assertEqual(result.invalid_probabilities, 1)
        self.assertEqual(result.negative_costs, 1)
        self.assertEqual(result.nonfinite_costs, 0)
        self.assertEqual(result.blank_reasoning, 1)

    def test_nan_inf_and_missing_input_hash_fail(self) -> None:
        row = forecast_row(fair_yes="NaN", cost="Infinity")
        row.pop("input_hash")

        result = audit_forecasts([ROW], [row])

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.missing_input_hashes, 1)
        self.assertEqual(result.invalid_probabilities, 1)
        self.assertEqual(result.nonfinite_costs, 1)
        self.assertEqual(result.negative_costs, 0)
        self.assertAlmostEqual(result.total_cost, 0.0)

    def test_schema_invalid_cost_and_blank_model_provider_fail(self) -> None:
        bad_schema = forecast_row()
        bad_schema.pop("logged_at")
        bad_values = forecast_row(cost="abc", provider="", model="")

        result = audit_forecasts([ROW], [bad_schema, bad_values])

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.schema_errors, 1)
        self.assertEqual(result.invalid_costs, 1)
        self.assertEqual(result.blank_providers, 1)
        self.assertEqual(result.blank_models, 1)

    def test_timestamp_keys_normalize(self) -> None:
        row = forecast_row(logged_at="2026-01-01T09:00:00+09:00")

        result = audit_forecasts([ROW], [row])

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.matched_records, 1)
