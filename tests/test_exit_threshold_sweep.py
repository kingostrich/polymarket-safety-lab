import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.optimize_exit_threshold import run_sweep, threshold_range

FIELDNAMES = [
    "logged_at",
    "market_id",
    "question",
    "yes_ask",
    "no_ask",
    "yes_bid",
    "no_bid",
    "fair_yes",
    "liquidity",
    "volume_24h",
]


def write_paper_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class ExitThresholdSweepTest(unittest.TestCase):
    def test_threshold_range_includes_stop(self) -> None:
        self.assertEqual(threshold_range(0.01, 0.03, 0.01), [0.01, 0.02, 0.03])
        with self.assertRaisesRegex(ValueError, "step must be positive"):
            threshold_range(0.01, 0.03, 0.0)
        with self.assertRaisesRegex(ValueError, "stop must be greater"):
            threshold_range(0.03, 0.01, 0.01)

    def test_run_sweep_writes_ranked_csv_markdown_and_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            out_dir = root / "sweep"
            write_paper_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.49",
                        "no_bid": "0.49",
                        "fair_yes": "0.62",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    },
                    {
                        "logged_at": "2026-01-01T00:01:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.49",
                        "no_bid": "0.49",
                        "fair_yes": "0.62",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    },
                ],
            )

            manifest = run_sweep(
                input_dir=input_dir,
                out_dir=out_dir,
                thresholds=[0.10, 0.20],
                forecast_mode="synthetic_edge",
                synthetic_edge=0.12,
            )

            csv_path = Path(str(manifest["csv_path"]))
            md_path = Path(str(manifest["md_path"]))
            manifest_path = Path(str(manifest["manifest_path"]))
            rows = list(csv.DictReader(csv_path.open()))
            manifest_json = json.loads(manifest_path.read_text())
            md = md_path.read_text()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["exit_edge_threshold"], "0.2")
        self.assertEqual(rows[0]["open_positions"], "0")
        self.assertEqual(rows[0]["positions_closed"], "1")
        self.assertIn("event_sharpe_smoke", rows[0])
        self.assertEqual(manifest_json["best_threshold"], 0.2)
        self.assertIs(manifest_json["production_safe"], False)
        self.assertEqual(manifest_json["readiness_decision"], "NO_LIVE_TRADING")
        self.assertIn("paper-only survival replays", md)
        self.assertIn("| rank | exit threshold |", md)

    def test_event_sharpe_smoke_includes_dead_event_return(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "paper"
            out_dir = root / "sweep"
            write_paper_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.00",
                        "no_bid": "0.00",
                        "fair_yes": "0.62",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    }
                ],
            )

            manifest = run_sweep(
                input_dir=input_dir,
                out_dir=out_dir,
                thresholds=[0.10],
                forecast_mode="synthetic_edge",
                synthetic_edge=0.12,
                death_threshold=50,
            )

            rows = list(csv.DictReader(Path(str(manifest["csv_path"])).open()))

        self.assertEqual(rows[0]["state"], "DEAD")
        self.assertEqual(rows[0]["event_sharpe_smoke"], "0.0")

    def test_run_sweep_rejects_empty_input(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "no paper rows"):
                run_sweep(
                    input_dir=Path(tmp) / "empty",
                    out_dir=Path(tmp) / "sweep",
                    thresholds=[0.10],
                )


if __name__ == "__main__":
    unittest.main()
