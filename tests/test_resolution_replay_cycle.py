import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from polymarket_backtest.paper_resolution_status import parse_market_status
from polymarket_backtest.resolution_replay_cycle import run_resolution_replay_cycle


class ResolutionReplayCycleTest(unittest.TestCase):
    def test_cycle_skips_when_no_resolution_eligible_markets(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = parse_market_status(
                "m1",
                {
                    "question": "Q",
                    "active": True,
                    "closed": False,
                    "archived": False,
                    "acceptingOrders": True,
                    "outcomePrices": '["0.0005","0.9995"]',
                    "updatedAt": "2026-01-01T00:00:00Z",
                },
            )
            with patch("polymarket_backtest.resolution_replay_cycle.collect_statuses", return_value=[status]):
                manifest = run_resolution_replay_cycle(
                    input_dir=root / "paper",
                    status_out_dir=root / "status",
                    model_forecasts_file=root / "model.jsonl",
                    benchmark_name="bench",
                    provider="unit",
                    model="unit-model",
                    cycle_manifest_path=root / "cycle.json",
                )

            self.assertFalse(manifest["replay_ran"])
            self.assertEqual(manifest["skip_reason"], "no_closed_resolution_eligible_markets")
            self.assertEqual(manifest["near_binary_but_open"], 1)
            self.assertTrue((root / "cycle.json").exists())

    def test_cycle_replays_when_resolution_is_eligible(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = parse_market_status(
                "m1",
                {
                    "question": "Q",
                    "active": False,
                    "closed": True,
                    "archived": False,
                    "acceptingOrders": False,
                    "outcomePrices": '["1","0"]',
                    "closedTime": "2026-01-01T00:00:00Z",
                },
            )
            replay = {
                "survival_report_path": str(root / "survival.json"),
                "positions_closed": 1,
                "open_positions": 0,
                "realized_pnl": 2.0,
                "final_equity": 52.0,
            }
            with patch("polymarket_backtest.resolution_replay_cycle.collect_statuses", return_value=[status]):
                with patch("polymarket_backtest.resolution_replay_cycle.run_model_benchmark", return_value=replay) as run_mock:
                    manifest = run_resolution_replay_cycle(
                        input_dir=root / "paper",
                        status_out_dir=root / "status",
                        model_forecasts_file=root / "model.jsonl",
                        benchmark_name="bench",
                        provider="unit",
                        model="unit-model",
                        cycle_manifest_path=root / "cycle.json",
                        forecast_root=root / "forecasts",
                    )

            self.assertTrue(manifest["replay_ran"])
            self.assertEqual(manifest["resolution_eligible"], 1)
            self.assertEqual(manifest["positions_closed"], 1)
            run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
