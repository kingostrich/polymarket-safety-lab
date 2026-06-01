import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.forecast_audit import audit_forecasts
from polymarket_backtest.forecast_import import (
    build_external_forecast_records,
    write_model_prompt_template,
)
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


def model_row(**overrides):
    row = {
        "logged_at": ROW["logged_at"],
        "market_id": ROW["market_id"],
        "fair_yes": 0.55,
        "cost": 0.02,
        "reasoning": "External model estimate.",
        "input_hash": row_input_hash(ROW),
    }
    row.update(overrides)
    return row


class ForecastImportTest(unittest.TestCase):
    def test_imported_external_forecasts_audit_cleanly(self) -> None:
        records = build_external_forecast_records(
            [ROW],
            [model_row()],
            provider="external_llm",
            model="test-model-high",
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].provider, "external_llm")
        self.assertEqual(records[0].model, "test-model-high")
        self.assertEqual(records[0].question, ROW["question"])
        result = audit_forecasts([ROW], [records[0].__dict__])
        self.assertEqual(result.status, "PASS")

    def test_import_uses_default_cost_when_cost_missing(self) -> None:
        row = model_row()
        row.pop("cost")

        records = build_external_forecast_records(
            [ROW],
            [row],
            provider="external_llm",
            model="test-model-high",
            default_cost=0.03,
        )

        self.assertAlmostEqual(records[0].cost, 0.03)

    def test_import_rejects_missing_rows_duplicates_invalid_probability_and_blank_reasoning(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing 1 source rows"):
            build_external_forecast_records([ROW], [], provider="external_llm", model="test-model-high")
        with self.assertRaisesRegex(ValueError, "duplicate model forecast key"):
            build_external_forecast_records([ROW], [model_row(), model_row()], provider="external_llm", model="test-model-high")
        with self.assertRaisesRegex(ValueError, "invalid fair_yes"):
            build_external_forecast_records([ROW], [model_row(fair_yes="NaN")], provider="external_llm", model="test-model-high")
        with self.assertRaisesRegex(ValueError, "reasoning is required"):
            build_external_forecast_records([ROW], [model_row(reasoning="")], provider="external_llm", model="test-model-high")

    def test_import_rejects_missing_or_mismatched_input_hash_and_duplicate_source_rows(self) -> None:
        missing_hash = model_row()
        missing_hash.pop("input_hash")
        with self.assertRaisesRegex(ValueError, "input_hash is required"):
            build_external_forecast_records([ROW], [missing_hash], provider="external_llm", model="test-model-high")
        with self.assertRaisesRegex(ValueError, "input_hash mismatch"):
            build_external_forecast_records([ROW], [model_row(input_hash="bad")], provider="external_llm", model="test-model-high")
        with self.assertRaisesRegex(ValueError, "duplicate source row key"):
            build_external_forecast_records([ROW, dict(ROW)], [model_row()], provider="external_llm", model="test-model-high")

    def test_import_rejects_missing_model_key_with_clear_error(self) -> None:
        row = model_row()
        row.pop("logged_at")
        with self.assertRaisesRegex(ValueError, "requires valid logged_at and market_id"):
            build_external_forecast_records([ROW], [row], provider="external_llm", model="test-model-high")

    def test_template_writer_outputs_minimal_model_input(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.jsonl"

            write_model_prompt_template([ROW], path)

            content = path.read_text()
        self.assertIn('"market_id": "m1"', content)
        self.assertIn('"input_hash"', content)
        self.assertIn('"required_output_fields"', content)
