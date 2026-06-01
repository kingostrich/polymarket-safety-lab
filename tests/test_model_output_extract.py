import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.model_output_extract import extract_json_objects, extract_model_output


class ModelOutputExtractTest(unittest.TestCase):
    def test_extracts_json_rows_and_counts_non_json_lines(self) -> None:
        row = {
            "logged_at": "2026-01-01T00:00:00+00:00",
            "market_id": "m1",
            "input_hash": "abc",
            "fair_yes": 0.4,
            "cost": 0.0,
            "reasoning": "no market prices supplied",
        }
        records, counters = extract_json_objects("commentary\n" + json.dumps(row) + "\n")

        self.assertEqual(records, [row])
        self.assertEqual(counters["raw_lines"], 2)
        self.assertEqual(counters["ignored_non_json_lines"], 1)
        self.assertEqual(counters["malformed_json_lines"], 0)
        self.assertEqual(counters["missing_required_key_rows"], 0)
        self.assertEqual(counters["unexpected_key_rows"], 0)

    def test_extract_model_output_writes_jsonl_and_manifest(self) -> None:
        row = {
            "logged_at": "2026-01-01T00:00:00+00:00",
            "market_id": "m1",
            "input_hash": "abc",
            "fair_yes": 0.4,
            "cost": 0.0,
            "reasoning": "no market prices supplied",
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw.txt"
            out = root / "model_minimal.jsonl"
            raw.write_text("note\n" + json.dumps(row) + "\n")

            result = extract_model_output(raw, out, expected_records=1)

            self.assertEqual(result.status, "PASS")
            self.assertEqual(result.records, 1)
            self.assertEqual(result.ignored_non_json_lines, 1)
            self.assertEqual(json.loads(out.read_text()), row)
            manifest = json.loads((root / "model_minimal.jsonl.manifest.json").read_text())
            self.assertEqual(manifest["records"], 1)
            self.assertEqual(manifest["expected_records"], 1)

    def test_strict_mode_rejects_wrong_count(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw.txt"
            raw.write_text("")

            with self.assertRaisesRegex(ValueError, "records=0 expected=1"):
                extract_model_output(raw, root / "out.jsonl", expected_records=1)


if __name__ == "__main__":
    unittest.main()
