import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.model_benchmark_summary import build_benchmark_rows


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


class ModelBenchmarkSummaryTest(unittest.TestCase):
    def test_build_benchmark_rows_matches_audit_to_survival_by_model(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "agy_smoke" / "imported" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 20,
                    "forecast_records": 20,
                    "matched_records": 20,
                    "coverage": 1.0,
                    "total_cost": 0.0,
                    "provider_counts": "agy:20",
                    "model_counts": "agy-model:20",
                },
            )
            write_json(
                forecast_root / "agy_smoke" / "imported" / "latest_manifest.json",
                {"provider": "agy", "model": "agy-model", "total_cost": 0.0},
            )
            write_json(
                forecast_root / "agy_smoke" / "imported" / "latest_diagnostics.json",
                {
                    "market_echo_share_1bp": 1.0,
                    "actionable_rows": 0,
                    "mean_abs_diff_to_yes_mid": 0.0,
                    "diagnosis_flags": "market_echo;no_actionable_edges",
                },
            )
            write_json(
                survival_root / "model_bench_20_survival_agy_smoke" / "latest_survival_report.json",
                {
                    "forecast_model": "agy-model",
                    "state": "ALIVE",
                    "rows_processed": 20,
                    "forecast_calls": 20,
                    "initial_bankroll": 50.0,
                    "final_equity": 50.0,
                    "max_drawdown": 0.0,
                    "signals_seen": 0,
                    "positions_opened": 0,
                    "open_positions": 0,
                },
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].benchmark, "agy_smoke/imported")
        self.assertEqual(rows[0].audit_status, "PASS")
        self.assertEqual(rows[0].survival_state, "ALIVE")
        self.assertEqual(rows[0].market_echo_share_1bp, 1.0)
        self.assertEqual(rows[0].actionable_rows, 0)
        self.assertEqual(rows[0].risk_flags, "no_trades;market_echo;no_actionable_edges")

    def test_missing_survival_is_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "provider" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 1,
                    "forecast_records": 1,
                    "matched_records": 1,
                    "coverage": 1.0,
                    "provider_counts": "provider:1",
                    "model_counts": "model-x:1",
                },
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertEqual(rows[0].provider, "provider")
        self.assertEqual(rows[0].model, "model-x")
        self.assertIn("missing_survival", rows[0].risk_flags)

    def test_same_model_requires_matching_row_counts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "full" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 154,
                    "forecast_records": 154,
                    "matched_records": 154,
                    "coverage": 1.0,
                    "provider_counts": "rule:154",
                    "model_counts": "shared-model:154",
                },
            )
            write_json(
                survival_root / "model_bench_20_survival_rule" / "latest_survival_report.json",
                {
                    "forecast_model": "shared-model",
                    "state": "ALIVE",
                    "rows_processed": 20,
                    "forecast_calls": 20,
                    "final_equity": 50.0,
                    "positions_opened": 0,
                },
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertEqual(rows[0].survival_state, "")
        self.assertIn("missing_survival", rows[0].risk_flags)
        self.assertIn("survival_row_mismatch", rows[0].risk_flags)

    def test_multi_model_counts_are_not_parsed_as_single_model(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "ensemble" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 20,
                    "forecast_records": 20,
                    "matched_records": 20,
                    "coverage": 1.0,
                    "provider_counts": "p1:10,p2:10",
                    "model_counts": "m1:10,m2:10",
                },
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertEqual(rows[0].provider, "")
        self.assertEqual(rows[0].model, "")
        self.assertIn("multi_provider_counts", rows[0].risk_flags)
        self.assertIn("multi_model_counts", rows[0].risk_flags)

    def test_performance_rank_mode_uses_final_equity_after_safety_gates(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            for name, model, equity in [("b_low", "low-model", 25.0), ("a_high", "high-model", 75.0)]:
                write_json(
                    forecast_root / name / "latest_audit.json",
                    {
                        "status": "PASS",
                        "source_rows": 20,
                        "forecast_records": 20,
                        "matched_records": 20,
                        "coverage": 1.0,
                        "provider_counts": f"{name}:20",
                        "model_counts": f"{model}:20",
                    },
                )
                write_json(
                    survival_root / f"model_bench_20_survival_{name}" / "latest_survival_report.json",
                    {
                        "forecast_model": model,
                        "state": "ALIVE",
                        "rows_processed": 20,
                        "forecast_calls": 20,
                        "initial_bankroll": 50.0,
                        "final_equity": equity,
                        "max_drawdown": 0.0,
                        "open_positions": 0,
                    },
                )

            rows = build_benchmark_rows(
                forecast_root,
                survival_root,
                "model_bench_20_survival_",
                rank_mode="performance",
            )

        self.assertEqual(rows[0].model, "high-model")

    def test_loss_and_open_positions_are_flagged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "blind" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 20,
                    "forecast_records": 20,
                    "matched_records": 20,
                    "coverage": 1.0,
                    "provider_counts": "agy:20",
                    "model_counts": "blind-model:20",
                },
            )
            write_json(
                survival_root / "model_bench_20_survival_blind" / "latest_survival_report.json",
                {
                    "forecast_model": "blind-model",
                    "state": "ALIVE",
                    "rows_processed": 20,
                    "forecast_calls": 20,
                    "initial_bankroll": 50.0,
                    "final_equity": 48.75,
                    "positions_opened": 7,
                    "open_positions": 7,
                },
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertIn("loss", rows[0].risk_flags)
        self.assertIn("open_positions", rows[0].risk_flags)
        self.assertEqual(rows[0].open_positions, 7)

    def test_manifest_null_total_cost_falls_back_to_audit_cost(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            survival_root = root / "paper"
            write_json(
                forecast_root / "provider" / "latest_audit.json",
                {
                    "status": "PASS",
                    "source_rows": 1,
                    "forecast_records": 1,
                    "matched_records": 1,
                    "coverage": 1.0,
                    "total_cost": 0.12,
                    "provider_counts": "provider:1",
                    "model_counts": "model-x:1",
                },
            )
            write_json(
                forecast_root / "provider" / "latest_manifest.json",
                {"provider": "provider", "model": "model-x", "total_cost": None},
            )

            rows = build_benchmark_rows(forecast_root, survival_root, "model_bench_20_survival_")

        self.assertAlmostEqual(rows[0].total_cost, 0.12)


if __name__ == "__main__":
    unittest.main()
