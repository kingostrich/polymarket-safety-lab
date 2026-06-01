from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.strategy_readiness import assess_readiness, load_benchmark_manifest, load_json, write_markdown


class StrategyReadinessTest(unittest.TestCase):
    def test_blocks_live_when_model_loses_and_no_resolutions_exist(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "benchmark_name": "model",
                "source_rows": 100,
                "bankroll": 50,
                "final_equity": 46,
                "open_positions": 9,
                "positions_closed": 0,
                "resolutions_loaded": 0,
                "market_echo_share_1bp": 0,
                "actionable_rows": 53,
                "event_max_drawdown": 0.1,
            },
            baseline_manifest={"benchmark_name": "baseline", "final_equity": 50},
            resolution_manifest={"resolution_eligible": 0},
            resolution_cycle_manifest={"replay_ran": False},
            oracle_metrics={"closed_trades": 9},
        )

        self.assertEqual(readiness["decision"], "NO_LIVE_TRADING")
        self.assertGreaterEqual(readiness["blocker_count"], 4)
        failed = {check["name"] for check in readiness["checks"] if check["status"] == "FAIL"}
        self.assertIn("beats_no_trade_baseline", failed)
        self.assertIn("official_forward_resolutions", failed)
        self.assertIn("closed_trade_count", failed)

    def test_passes_blockers_for_completed_profitable_forward_sample(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "benchmark_name": "model",
                "source_rows": 150,
                "bankroll": 50,
                "final_equity": 56,
                "open_positions": 0,
                "positions_closed": 35,
                "resolutions_loaded": 35,
                "market_echo_share_1bp": 0.1,
                "actionable_rows": 70,
                "event_max_drawdown": 0.1,
            },
            baseline_manifest={"benchmark_name": "baseline", "final_equity": 50},
            resolution_manifest={"resolution_eligible": 35},
            resolution_cycle_manifest={"replay_ran": True, "positions_closed": 35},
            oracle_metrics={"closed_trades": 9},
        )

        self.assertEqual(readiness["decision"], "PAPER_ONLY_REVIEW")
        self.assertEqual(readiness["blocker_count"], 0)

    def test_markdown_writer_and_loader(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "source_rows": 1,
                "bankroll": 50,
                "final_equity": 49,
                "open_positions": 1,
                "positions_closed": 0,
                "resolutions_loaded": 0,
                "market_echo_share_1bp": 1,
                "actionable_rows": 0,
                "event_max_drawdown": 0.4,
            },
            baseline_manifest={"final_equity": 50},
            resolution_manifest={"resolution_eligible": 0},
            resolution_cycle_manifest={"replay_ran": False},
            oracle_metrics={"closed_trades": 0},
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "readiness.md"
            write_markdown(path, readiness)
            text = path.read_text(encoding="utf-8")
            self.assertIn("NO_LIVE_TRADING", text)
            self.assertIn("beats_no_trade_baseline", text)

    def test_missing_open_positions_is_blocker(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "source_rows": 100,
                "bankroll": 50,
                "final_equity": 56,
                "positions_closed": 35,
                "resolutions_loaded": 35,
                "market_echo_share_1bp": 0.1,
                "actionable_rows": 70,
                "event_max_drawdown": 0.1,
            },
            baseline_manifest={"final_equity": 50},
            resolution_manifest={"resolution_eligible": 35},
            resolution_cycle_manifest={"replay_ran": True, "positions_closed": 35},
            oracle_metrics={"closed_trades": 9},
        )

        no_open_check = next(check for check in readiness["checks"] if check["name"] == "no_open_positions")
        self.assertEqual(no_open_check["status"], "FAIL")
        self.assertEqual(readiness["decision"], "NO_LIVE_TRADING")

    def test_null_open_positions_is_blocker(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "source_rows": 150,
                "bankroll": 50,
                "final_equity": 56,
                "open_positions": None,
                "positions_closed": 35,
                "resolutions_loaded": 35,
                "market_echo_share_1bp": 0.1,
                "actionable_rows": 70,
                "event_max_drawdown": 0.1,
            },
            baseline_manifest={"final_equity": 50},
            resolution_manifest={"resolution_eligible": 35},
            resolution_cycle_manifest={"replay_ran": True, "positions_closed": 35},
            oracle_metrics={"closed_trades": 9},
        )

        no_open_check = next(check for check in readiness["checks"] if check["name"] == "no_open_positions")
        self.assertEqual(no_open_check["status"], "FAIL")

    def test_resolution_eligible_without_replay_does_not_pass_official_resolution_gate(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "source_rows": 150,
                "bankroll": 50,
                "final_equity": 56,
                "open_positions": 0,
                "positions_closed": 35,
                "resolutions_loaded": 0,
                "market_echo_share_1bp": 0.1,
                "actionable_rows": 70,
                "event_max_drawdown": 0.1,
            },
            baseline_manifest={"final_equity": 50},
            resolution_manifest={"resolution_eligible": 35},
            resolution_cycle_manifest={"replay_ran": False, "positions_closed": 0},
            oracle_metrics={"closed_trades": 9},
        )

        resolution_check = next(check for check in readiness["checks"] if check["name"] == "official_forward_resolutions")
        self.assertEqual(resolution_check["status"], "FAIL")

    def test_missing_drawdown_is_blocker(self) -> None:
        readiness = assess_readiness(
            model_manifest={
                "source_rows": 150,
                "bankroll": 50,
                "final_equity": 56,
                "open_positions": 0,
                "positions_closed": 35,
                "resolutions_loaded": 35,
                "market_echo_share_1bp": 0.1,
                "actionable_rows": 70,
            },
            baseline_manifest={"final_equity": 50},
            resolution_manifest={"resolution_eligible": 35},
            resolution_cycle_manifest={"replay_ran": True, "positions_closed": 35},
            oracle_metrics={"closed_trades": 9},
        )

        drawdown_check = next(check for check in readiness["checks"] if check["name"] == "max_drawdown_under_limit")
        self.assertEqual(drawdown_check["status"], "FAIL")

    def test_benchmark_loader_merges_survival_report_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "survival.json"
            report.write_text(
                '{"open_positions": 3, "positions_closed": 2, "realized_pnl": 1.5, "event_max_drawdown": 0.2}',
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                '{"benchmark_name": "x", "open_positions": 0, "survival_report_path": "' + str(report) + '"}',
                encoding="utf-8",
            )

            loaded = load_benchmark_manifest(manifest)

        self.assertEqual(loaded["open_positions"], 3)
        self.assertEqual(loaded["positions_closed"], 2)
        self.assertEqual(loaded["event_max_drawdown"], 0.2)

    def test_benchmark_loader_resolves_manifest_relative_survival_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            report = artifacts / "survival.json"
            report.write_text('{"open_positions": 5}', encoding="utf-8")
            manifest = artifacts / "manifest.json"
            manifest.write_text('{"survival_report_path": "survival.json"}', encoding="utf-8")

            loaded = load_benchmark_manifest(manifest)

        self.assertEqual(loaded["open_positions"], 5)

    def test_load_json_raises_for_missing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_json(Path(tmp) / "missing.json")


if __name__ == "__main__":
    unittest.main()
