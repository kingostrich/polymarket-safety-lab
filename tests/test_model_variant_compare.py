from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.model_variant_compare import (
    build_report,
    build_variant_rows,
    discover_manifest_paths,
    is_baseline,
    load_manifests,
)


class ModelVariantCompareTest(unittest.TestCase):
    def test_build_variant_rows_ranks_profitable_review_above_losing_model(self) -> None:
        manifests = [
            (
                Path("baseline/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "rule_baseline_100",
                    "provider": "rule_baseline",
                    "source_rows": 100,
                    "bankroll": 50,
                    "final_equity": 50,
                    "survival_state": "ALIVE",
                    "positions_opened": 0,
                    "positions_closed": 0,
                    "open_positions": 0,
                    "resolutions_loaded": 0,
                    "market_echo_share_1bp": 1.0,
                    "event_max_drawdown": 0,
                },
            ),
            (
                Path("good/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "good_model",
                    "provider": "agy",
                    "source_rows": 100,
                    "bankroll": 50,
                    "final_equity": 55,
                    "survival_state": "ALIVE",
                    "positions_opened": 35,
                    "positions_closed": 35,
                    "open_positions": 0,
                    "resolutions_loaded": 35,
                    "market_echo_share_1bp": 0.1,
                    "actionable_rows": 35,
                    "event_max_drawdown": 0.1,
                },
            ),
            (
                Path("bad/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "bad_model",
                    "provider": "agy",
                    "source_rows": 100,
                    "bankroll": 50,
                    "final_equity": 46,
                    "survival_state": "ALIVE",
                    "positions_opened": 9,
                    "positions_closed": 0,
                    "open_positions": 9,
                    "resolutions_loaded": 0,
                    "market_echo_share_1bp": 0,
                    "actionable_rows": 53,
                    "event_max_drawdown": 0.09,
                },
            ),
        ]

        rows = build_variant_rows(manifests, source_rows_filter=100)

        self.assertEqual(rows[0].benchmark_name, "good_model")
        bad = next(row for row in rows if row.benchmark_name == "bad_model")
        self.assertEqual(bad.readiness_decision, "NO_LIVE_TRADING")
        self.assertIn("open_positions", bad.risk_flags)
        self.assertIn("under_baseline", bad.risk_flags)

    def test_baseline_comparison_uses_return_not_absolute_equity(self) -> None:
        manifests = [
            (
                Path("baseline/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "rule_baseline_100",
                    "provider": "rule_baseline",
                    "source_rows": 100,
                    "bankroll": 10000,
                    "final_equity": 10100,
                    "survival_state": "ALIVE",
                },
            ),
            (
                Path("active/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "active_model",
                    "provider": "agy",
                    "source_rows": 100,
                    "bankroll": 1000,
                    "final_equity": 1200,
                    "survival_state": "ALIVE",
                    "positions_opened": 40,
                    "positions_closed": 40,
                    "open_positions": 0,
                    "resolutions_loaded": 40,
                    "market_echo_share_1bp": 0,
                    "event_max_drawdown": 0.1,
                },
            ),
        ]

        active = next(row for row in build_variant_rows(manifests) if row.benchmark_name == "active_model")

        self.assertGreater(active.return_vs_baseline, 0)
        self.assertNotIn("under_baseline", active.risk_flags)

    def test_closed_market_exit_without_resolution_is_warning_not_live_blocker(self) -> None:
        manifests = [
            (
                Path("baseline/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "rule_baseline_100",
                    "provider": "rule_baseline",
                    "source_rows": 100,
                    "bankroll": 50,
                    "final_equity": 50,
                    "survival_state": "ALIVE",
                },
            ),
            (
                Path("exit/latest_benchmark_manifest.json"),
                {
                    "benchmark_name": "exit_model",
                    "provider": "agy",
                    "source_rows": 100,
                    "bankroll": 50,
                    "final_equity": 55,
                    "survival_state": "ALIVE",
                    "positions_opened": 10,
                    "positions_closed": 10,
                    "open_positions": 0,
                    "resolutions_loaded": 0,
                    "market_echo_share_1bp": 0,
                    "event_max_drawdown": 0.1,
                },
            ),
        ]

        exit_row = next(row for row in build_variant_rows(manifests) if row.benchmark_name == "exit_model")

        self.assertEqual(exit_row.readiness_decision, "PAPER_ONLY_REVIEW")
        self.assertIn("no_official_resolutions_after_market_exit", exit_row.risk_flags)
        self.assertNotIn("no_official_resolutions;", exit_row.risk_flags + ";")

    def test_baseline_detection_does_not_match_active_name_containing_baseline(self) -> None:
        active = {
            "benchmark_name": "active_variant_comparing_against_baseline_100",
            "provider": "agy",
            "model": "agy_model",
        }

        self.assertFalse(is_baseline(active))

    def test_loader_merges_survival_report_before_comparison(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast = root / "data" / "forecasts" / "model"
            forecast.mkdir(parents=True)
            report = root / "survival.json"
            report.write_text(
                '{"open_positions": 4, "positions_closed": 2, "event_max_drawdown": 0.15}',
                encoding="utf-8",
            )
            manifest = forecast / "latest_benchmark_manifest.json"
            manifest.write_text(
                '{"benchmark_name": "model", "source_rows": 100, "bankroll": 50, '
                '"final_equity": 49, "survival_state": "ALIVE", "survival_report_path": "'
                + str(report)
                + '"}',
                encoding="utf-8",
            )

            rows = build_variant_rows(load_manifests([manifest]))

        self.assertEqual(rows[0].open_positions, 4)
        self.assertEqual(rows[0].positions_closed, 2)
        self.assertEqual(rows[0].event_max_drawdown, 0.15)

    def test_build_report_writes_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            forecast_root = root / "forecasts"
            baseline = forecast_root / "rule_baseline_100"
            model = forecast_root / "model_100"
            baseline.mkdir(parents=True)
            model.mkdir(parents=True)
            (baseline / "latest_benchmark_manifest.json").write_text(
                '{"benchmark_name": "rule_baseline_100", "provider": "rule_baseline", '
                '"source_rows": 100, "bankroll": 50, "final_equity": 50, "survival_state": "ALIVE"}',
                encoding="utf-8",
            )
            (model / "latest_benchmark_manifest.json").write_text(
                '{"benchmark_name": "model_100", "provider": "agy", "source_rows": 100, '
                '"bankroll": 50, "final_equity": 49, "survival_state": "ALIVE"}',
                encoding="utf-8",
            )
            readiness = root / "readiness.json"
            readiness.write_text('{"decision": "NO_LIVE_TRADING", "blocker_count": 5}', encoding="utf-8")

            payload = build_report(
                forecast_root=forecast_root,
                output_csv=root / "comparison.csv",
                output_json=root / "comparison.json",
                output_md=root / "comparison.md",
                source_rows_filter=100,
                readiness_json=readiness,
            )

            self.assertEqual(payload["variant_count"], 2)
            self.assertTrue((root / "comparison.csv").exists())
            self.assertIn("NO_LIVE_TRADING", (root / "comparison.md").read_text(encoding="utf-8"))

    def test_discover_manifest_paths_can_filter_patterns(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep").mkdir()
            (root / "skip").mkdir()
            (root / "keep" / "latest_benchmark_manifest.json").write_text("{}", encoding="utf-8")
            (root / "skip" / "latest_benchmark_manifest.json").write_text("{}", encoding="utf-8")

            paths = discover_manifest_paths(root, include_patterns=["keep"])

        self.assertEqual([path.parent.name for path in paths], ["keep"])


if __name__ == "__main__":
    unittest.main()
