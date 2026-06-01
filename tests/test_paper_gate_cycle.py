from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from polymarket_backtest.paper_gate_cycle import resolve_oracle_metrics_path, run_paper_gate_cycle


class PaperGateCycleTest(unittest.TestCase):
    def test_cycle_runs_resolution_readiness_and_variant_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_dir = root / "status"
            status_dir.mkdir()
            resolution_manifest = status_dir / "resolution_manifest.json"
            resolution_manifest.write_text(
                '{"resolution_eligible": 0, "near_binary_but_open": 1, "near_binary_disputed_open": 0}',
                encoding="utf-8",
            )
            resolution_cycle = root / "latest_resolution_cycle.json"
            resolution_cycle.write_text('{"replay_ran": false, "positions_closed": 0}', encoding="utf-8")
            oracle = root / "oracle.json"
            oracle.write_text('{"closed_trades": 9}', encoding="utf-8")
            model_report = root / "model_survival.json"
            model_report.write_text(
                '{"open_positions": 2, "positions_closed": 0, "event_max_drawdown": 0.1}',
                encoding="utf-8",
            )
            baseline_report = root / "baseline_survival.json"
            baseline_report.write_text(
                '{"open_positions": 0, "positions_closed": 0, "event_max_drawdown": 0}',
                encoding="utf-8",
            )
            model_manifest = root / "model_manifest.json"
            model_manifest.write_text(
                '{"benchmark_name": "model", "provider": "agy", "source_rows": 100, "bankroll": 50, '
                '"final_equity": 49, "survival_state": "ALIVE", "positions_opened": 2, '
                '"market_echo_share_1bp": 0, "actionable_rows": 10, "survival_report_path": "'
                + str(model_report)
                + '"}',
                encoding="utf-8",
            )
            baseline_manifest = root / "baseline_manifest.json"
            baseline_manifest.write_text(
                '{"benchmark_name": "rule_baseline_100", "provider": "rule_baseline", "source_rows": 100, '
                '"bankroll": 50, "final_equity": 50, "survival_state": "ALIVE", "positions_opened": 0, '
                '"market_echo_share_1bp": 1, "actionable_rows": 0, "survival_report_path": "'
                + str(baseline_report)
                + '"}',
                encoding="utf-8",
            )
            forecast_root = root / "forecasts"
            forecast_model = forecast_root / "model"
            forecast_baseline = forecast_root / "rule_baseline_100"
            forecast_model.mkdir(parents=True)
            forecast_baseline.mkdir(parents=True)
            (forecast_model / "latest_benchmark_manifest.json").write_text(model_manifest.read_text(encoding="utf-8"), encoding="utf-8")
            (forecast_baseline / "latest_benchmark_manifest.json").write_text(baseline_manifest.read_text(encoding="utf-8"), encoding="utf-8")

            with patch("polymarket_backtest.paper_gate_cycle.run_resolution_replay_cycle") as replay:
                replay.return_value = {
                    "replay_ran": False,
                    "resolution_eligible": 0,
                    "near_binary_but_open": 1,
                    "near_binary_disputed_open": 0,
                }
                manifest = run_paper_gate_cycle(
                    input_dir=root / "paper",
                    status_out_dir=status_dir,
                    model_forecasts_file=root / "model.jsonl",
                    resolution_benchmark_name="resolution_cycle",
                    provider="agy",
                    model="unit",
                    resolution_cycle_manifest=resolution_cycle,
                    model_manifest=model_manifest,
                    baseline_manifest=baseline_manifest,
                    oracle_metrics=oracle,
                    readiness_json=root / "readiness.json",
                    readiness_md=root / "readiness.md",
                    variant_csv=root / "variants.csv",
                    variant_json=root / "variants.json",
                    variant_md=root / "variants.md",
                    forecast_root=forecast_root,
                    survival_root=root / "paper",
                )

        self.assertEqual(manifest["readiness_decision"], "NO_LIVE_TRADING")
        self.assertEqual(manifest["variant_count"], 2)
        self.assertFalse(manifest["resolution_replay_ran"])
        self.assertEqual(manifest["paper_collection_decision"], "CONTINUE_PAPER_LOGGING")
        self.assertEqual(manifest["enforcement_mode"], "report_only_no_live_execution")
        self.assertIn("no_new_official_resolutions", manifest["stale_reason"])

    def test_resolve_latest_oracle_metrics_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "old" / "oracle_smoke"
            newer = root / "new" / "oracle_smoke"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            old_metrics = older / "metrics.json"
            new_metrics = newer / "metrics.json"
            old_metrics.write_text("{}", encoding="utf-8")
            new_metrics.write_text("{}", encoding="utf-8")

            self.assertEqual(resolve_oracle_metrics_path(Path("latest"), backtest_root=root), new_metrics)

    def test_resolve_oracle_metrics_path_keeps_explicit_path(self) -> None:
        explicit = Path("data/backtests/custom/oracle_smoke/metrics.json")

        self.assertEqual(resolve_oracle_metrics_path(explicit), explicit)


if __name__ == "__main__":
    unittest.main()
