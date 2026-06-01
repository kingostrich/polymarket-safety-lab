import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.report_summary import safe_int, summarize_survival_reports, write_csv


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


class ReportSummaryTest(unittest.TestCase):
    def test_safe_int_falls_back_for_missing_or_invalid_values(self) -> None:
        self.assertEqual(safe_int(None), 0)
        self.assertEqual(safe_int(""), 0)
        self.assertEqual(safe_int("N/A"), 0)
        self.assertEqual(safe_int("7"), 7)

    def test_summarizes_legacy_and_current_survival_reports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "legacy" / "survival_report_20260101T000000Z.json",
                {
                    "state": "ALIVE",
                    "initial_bankroll": 50.0,
                    "final_equity": 49.0,
                    "final_cash": 48.0,
                    "max_drawdown": 0.10,
                    "rows_processed": 3,
                    "forecast_calls": 2,
                },
            )
            write_json(
                root / "current" / "survival_report_20260101T000001Z.json",
                {
                    "state": "DEAD",
                    "death_reason": None,
                    "initial_bankroll": 50.0,
                    "final_equity": 0.0,
                    "final_cash": 0.0,
                    "max_drawdown": 0.30,
                    "event_max_drawdown": 0.60,
                    "timestamp_close_max_drawdown": 0.30,
                    "drawdown_policy": "timestamp_close",
                    "rows_processed": 4,
                    "forecast_calls": 4,
                },
            )

            rows = summarize_survival_reports(root)

        self.assertEqual(len(rows), 2)
        legacy = next(row for row in rows if row.scenario == "legacy")
        current = next(row for row in rows if row.scenario == "current")
        self.assertTrue(legacy.legacy_mdd_fields)
        self.assertEqual(legacy.drawdown_policy, "event_legacy")
        self.assertEqual(legacy.run_timestamp, "20260101T000000Z")
        self.assertAlmostEqual(legacy.return_on_investment, -0.02)
        self.assertEqual(legacy.rows_processed, 3)
        self.assertEqual(legacy.forecast_calls, 2)
        self.assertAlmostEqual(legacy.event_max_drawdown, 0.10)
        self.assertAlmostEqual(legacy.timestamp_close_max_drawdown, 0.10)
        self.assertIn("event_max_drawdown", legacy.missing_fields)
        self.assertFalse(current.legacy_mdd_fields)
        self.assertEqual(current.death_reason, "")
        self.assertEqual(current.drawdown_policy, "timestamp_close")
        self.assertEqual(current.rows_processed, 4)
        self.assertEqual(current.forecast_calls, 4)
        self.assertAlmostEqual(current.event_max_drawdown, 0.60)
        self.assertIn("death_reason", current.missing_fields)

    def test_latest_reports_are_excluded_by_default(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"state": "ALIVE", "final_equity": 50, "max_drawdown": 0}
            write_json(root / "case" / "survival_report_20260101T000000Z.json", payload)
            write_json(root / "case" / "latest_survival_report.json", payload)

            default_rows = summarize_survival_reports(root)
            include_latest_rows = summarize_survival_reports(root, include_latest=True)

        self.assertEqual(len(default_rows), 1)
        self.assertEqual(len(include_latest_rows), 2)

    def test_write_csv_handles_empty_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "summary.csv"

            write_csv([], output_path)

            with output_path.open(newline="") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(rows[0][0], "scenario")
