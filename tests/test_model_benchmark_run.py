from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import unittest

from polymarket_backtest.forecast_runner import row_input_hash
from polymarket_backtest.model_benchmark_run import run_model_benchmark


FIELDNAMES = [
    "logged_at",
    "market_id",
    "question",
    "yes_bid",
    "yes_ask",
    "no_bid",
    "no_ask",
    "fair_yes",
    "action",
    "liquidity",
    "volume_24h",
]


def write_paper_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


class ModelBenchmarkRunTest(unittest.TestCase):
    def test_run_model_benchmark_imports_audits_replays_and_summarizes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            forecast_root = root / "forecasts"
            survival_root = root / "survival"
            summary_csv = root / "summary.csv"
            summary_md = root / "summary.md"
            paper_row = {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_bid": "0.49",
                "yes_ask": "0.51",
                "no_bid": "0.48",
                "no_ask": "0.52",
                "fair_yes": "0.50",
                "action": "skip",
                "liquidity": "1000",
                "volume_24h": "100",
            }
            write_paper_rows(input_dir / "paper_signals_subset_20260101T000000Z.csv", [paper_row])
            model_file = root / "model_minimal.jsonl"
            write_jsonl(
                model_file,
                [
                    {
                        "logged_at": paper_row["logged_at"],
                        "market_id": paper_row["market_id"],
                        "input_hash": row_input_hash(paper_row),
                        "fair_yes": 0.50,
                        "cost": 0,
                        "reasoning": "midpoint smoke",
                    }
                ],
            )

            manifest = run_model_benchmark(
                input_dir=input_dir,
                model_forecasts_file=model_file,
                benchmark_name="unit_smoke",
                provider="unit",
                model="unit-model",
                forecast_root=forecast_root,
                survival_root=survival_root,
                summary_csv=summary_csv,
                summary_md=summary_md,
                scenario_prefix="custom_survival_",
            )

            self.assertEqual(manifest["audit_status"], "PASS")
            self.assertEqual(manifest["survival_state"], "ALIVE")
            self.assertEqual(manifest["scenario_prefix"], "custom_survival_")
            self.assertEqual(manifest["resolutions_csv"], "")
            self.assertEqual(manifest["resolutions_loaded"], 0)
            self.assertEqual(manifest["bankroll"], 50.0)
            self.assertEqual(manifest["edge_threshold"], 0.08)
            self.assertEqual(manifest["exit_policy"], "none")
            self.assertEqual(manifest["drawdown_policy"], "event")
            self.assertEqual(manifest["rank_mode"], "quality")
            self.assertTrue(summary_csv.exists())
            self.assertTrue(summary_md.exists())
            self.assertIn("unit_smoke/imported", summary_md.read_text())
            self.assertTrue((forecast_root / "unit_smoke" / "latest_benchmark_manifest.json").exists())
            self.assertTrue((survival_root / "custom_survival_unit_smoke" / "latest_survival_report.json").exists())

    def test_run_model_benchmark_rejects_missing_model_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            paper_rows = [
                {
                    "logged_at": "2026-01-01T00:00:00+00:00",
                    "market_id": "m1",
                    "question": "Will it happen?",
                    "yes_bid": "0.49",
                    "yes_ask": "0.51",
                    "no_bid": "0.48",
                    "no_ask": "0.52",
                    "fair_yes": "0.50",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
                {
                    "logged_at": "2026-01-01T00:01:00+00:00",
                    "market_id": "m2",
                    "question": "Will it not happen?",
                    "yes_bid": "0.39",
                    "yes_ask": "0.41",
                    "no_bid": "0.58",
                    "no_ask": "0.60",
                    "fair_yes": "0.40",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
            ]
            write_paper_rows(input_dir / "paper_signals_subset_20260101T000000Z.csv", paper_rows)
            model_file = root / "model_minimal.jsonl"
            write_jsonl(
                model_file,
                [
                    {
                        "logged_at": paper_rows[0]["logged_at"],
                        "market_id": paper_rows[0]["market_id"],
                        "input_hash": row_input_hash(paper_rows[0]),
                        "fair_yes": 0.50,
                        "cost": 0,
                        "reasoning": "only one row",
                    }
                ],
            )

            with self.assertRaisesRegex(ValueError, "missing 1 source rows"):
                run_model_benchmark(
                    input_dir=input_dir,
                    model_forecasts_file=model_file,
                    benchmark_name="bad_smoke",
                    provider="unit",
                    model="unit-model",
                    forecast_root=root / "forecasts",
                    survival_root=root / "survival",
                    summary_csv=root / "summary.csv",
                    summary_md=root / "summary.md",
                )

    def test_run_model_benchmark_passes_exit_options_to_survival(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            forecast_root = root / "forecasts"
            survival_root = root / "survival"
            rows = [
                {
                    "logged_at": "2026-01-01T00:00:00+00:00",
                    "market_id": "m1",
                    "question": "Will it happen?",
                    "yes_bid": "0.49",
                    "yes_ask": "0.50",
                    "no_bid": "0.49",
                    "no_ask": "0.50",
                    "fair_yes": "0.50",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
                {
                    "logged_at": "2026-01-01T00:01:00+00:00",
                    "market_id": "m1",
                    "question": "Will it happen?",
                    "yes_bid": "0.49",
                    "yes_ask": "0.50",
                    "no_bid": "0.49",
                    "no_ask": "0.50",
                    "fair_yes": "0.50",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
            ]
            write_paper_rows(input_dir / "paper_signals_subset_20260101T000000Z.csv", rows)
            model_file = root / "model_minimal.jsonl"
            write_jsonl(
                model_file,
                [
                    {
                        "logged_at": rows[0]["logged_at"],
                        "market_id": rows[0]["market_id"],
                        "input_hash": row_input_hash(rows[0]),
                        "fair_yes": 0.65,
                        "cost": 0,
                        "reasoning": "open",
                    },
                    {
                        "logged_at": rows[1]["logged_at"],
                        "market_id": rows[1]["market_id"],
                        "input_hash": row_input_hash(rows[1]),
                        "fair_yes": 0.55,
                        "cost": 0,
                        "reasoning": "exit",
                    },
                ],
            )

            manifest = run_model_benchmark(
                input_dir=input_dir,
                model_forecasts_file=model_file,
                benchmark_name="exit_smoke",
                provider="unit",
                model="unit-model",
                forecast_root=forecast_root,
                survival_root=survival_root,
                summary_csv=root / "summary.csv",
                summary_md=root / "summary.md",
                scenario_prefix="custom_survival_",
                exit_policy="edge_below",
                exit_edge_threshold=0.08,
            )

            self.assertEqual(manifest["exit_policy"], "edge_below")
            self.assertEqual(manifest["exit_edge_threshold"], 0.08)
            self.assertEqual(manifest["positions_opened"], 1)
            self.assertEqual(manifest["positions_closed"], 1)
            self.assertEqual(manifest["open_positions"], 0)

    def test_run_model_benchmark_loads_resolutions_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            forecast_root = root / "forecasts"
            survival_root = root / "survival"
            rows = [
                {
                    "logged_at": "2026-01-01T00:00:00+00:00",
                    "market_id": "m1",
                    "question": "Will it happen?",
                    "yes_bid": "0.49",
                    "yes_ask": "0.50",
                    "no_bid": "0.49",
                    "no_ask": "0.50",
                    "fair_yes": "0.50",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
                {
                    "logged_at": "2026-01-02T00:00:00+00:00",
                    "market_id": "m2",
                    "question": "Later row",
                    "yes_bid": "0.49",
                    "yes_ask": "0.50",
                    "no_bid": "0.49",
                    "no_ask": "0.50",
                    "fair_yes": "0.50",
                    "action": "skip",
                    "liquidity": "1000",
                    "volume_24h": "100",
                },
            ]
            write_paper_rows(input_dir / "paper_signals_subset_20260101T000000Z.csv", rows)
            model_file = root / "model_minimal.jsonl"
            write_jsonl(
                model_file,
                [
                    {
                        "logged_at": rows[0]["logged_at"],
                        "market_id": rows[0]["market_id"],
                        "input_hash": row_input_hash(rows[0]),
                        "fair_yes": 0.65,
                        "cost": 0,
                        "reasoning": "open",
                    },
                    {
                        "logged_at": rows[1]["logged_at"],
                        "market_id": rows[1]["market_id"],
                        "input_hash": row_input_hash(rows[1]),
                        "fair_yes": 0.50,
                        "cost": 0,
                        "reasoning": "later",
                    },
                ],
            )
            resolutions = root / "resolutions.csv"
            resolutions.write_text(
                "market_id,resolved_at,resolved_outcome\n"
                "m1,2026-01-01T00:30:00+00:00,YES\n"
            )

            manifest = run_model_benchmark(
                input_dir=input_dir,
                model_forecasts_file=model_file,
                benchmark_name="resolution_smoke",
                provider="unit",
                model="unit-model",
                forecast_root=forecast_root,
                survival_root=survival_root,
                summary_csv=root / "summary.csv",
                summary_md=root / "summary.md",
                scenario_prefix="custom_survival_",
                resolutions_csv=resolutions,
            )

            self.assertEqual(manifest["resolutions_csv"], str(resolutions))
            self.assertEqual(manifest["resolutions_loaded"], 1)
            self.assertEqual(manifest["positions_opened"], 1)
            self.assertEqual(manifest["positions_closed"], 1)
            self.assertEqual(manifest["open_positions"], 0)


if __name__ == "__main__":
    unittest.main()
