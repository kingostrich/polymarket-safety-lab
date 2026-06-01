import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from polymarket_backtest import paper_subset
from polymarket_backtest.paper_subset import run_subset

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
]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


class PaperSubsetTest(unittest.TestCase):
    def test_run_subset_writes_latest_files_and_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            out_dir = root / "out"
            write_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m2",
                        "question": "Q2",
                        "yes_bid": "0.49",
                        "yes_ask": "0.51",
                        "no_bid": "0.48",
                        "no_ask": "0.52",
                        "fair_yes": "0.50",
                        "action": "skip",
                    },
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Q1",
                        "yes_bid": "0.40",
                        "yes_ask": "0.42",
                        "no_bid": "0.56",
                        "no_ask": "0.58",
                        "fair_yes": "0.50",
                        "action": "paper_signal",
                    },
                    {
                        "logged_at": "2026-01-01T00:01:00+00:00",
                        "market_id": "m3",
                        "question": "Q3",
                        "yes_bid": "0.20",
                        "yes_ask": "0.22",
                        "no_bid": "0.76",
                        "no_ask": "0.78",
                        "fair_yes": "0.30",
                        "action": "skip",
                    },
                ],
            )

            manifest = run_subset(input_dir=input_dir, out_dir=out_dir, limit=2)

            self.assertEqual(manifest["source_records"], 3)
            self.assertEqual(manifest["records"], 2)
            self.assertEqual(manifest["signals"], 1)
            self.assertTrue((out_dir / "latest_paper_signals.csv").exists())
            self.assertTrue((out_dir / "latest_paper_signals.jsonl").exists())
            self.assertTrue((out_dir / "latest_manifest.json").exists())
            latest = (out_dir / "latest_paper_signals.csv").read_text()
            self.assertIn("m1", latest)
            self.assertIn("m2", latest)
            self.assertNotIn("m3", latest)

    def test_run_subset_rejects_empty_selection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            out_dir = root / "out"
            write_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Q1",
                        "yes_bid": "0.40",
                        "yes_ask": "0.42",
                        "no_bid": "0.56",
                        "no_ask": "0.58",
                        "fair_yes": "0.50",
                        "action": "skip",
                    }
                ],
            )

            with self.assertRaisesRegex(ValueError, "no source rows selected"):
                run_subset(input_dir=input_dir, out_dir=out_dir, start_index=3, limit=2)

    def test_run_subset_removes_prior_generated_subset_files_from_output_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            out_dir = root / "out"
            write_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Q1",
                        "yes_bid": "0.40",
                        "yes_ask": "0.42",
                        "no_bid": "0.56",
                        "no_ask": "0.58",
                        "fair_yes": "0.50",
                        "action": "skip",
                    }
                ],
            )
            out_dir.mkdir(parents=True)
            old_csv = out_dir / "paper_signals_subset_20250101T000000Z.csv"
            old_jsonl = out_dir / "paper_signals_subset_20250101T000000Z.jsonl"
            old_csv.write_text("old\n")
            old_jsonl.write_text("{}\n")
            user_file = out_dir / "paper_signals_subset_analysis.csv"
            user_file.write_text("manual\n")

            run_subset(input_dir=input_dir, out_dir=out_dir, limit=1)

            self.assertFalse(old_csv.exists())
            self.assertFalse(old_jsonl.exists())
            self.assertTrue(user_file.exists())
            generated_csvs = [
                path
                for path in out_dir.glob("paper_signals_subset_*.csv")
                if path.name != "paper_signals_subset_analysis.csv"
            ]
            self.assertEqual(len(generated_csvs), 1)

    def test_failed_run_preserves_prior_generated_subset_file(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            out_dir = root / "out"
            write_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Q1",
                        "yes_bid": "0.40",
                        "yes_ask": "0.42",
                        "no_bid": "0.56",
                        "no_ask": "0.58",
                        "fair_yes": "0.50",
                        "action": "skip",
                    }
                ],
            )
            out_dir.mkdir(parents=True)
            old_csv = out_dir / "paper_signals_subset_20250101T000000Z.csv"
            old_csv.write_text("old\n")
            original_atomic_write_text = paper_subset.atomic_write_text

            def fail_jsonl(path: Path, content: str) -> None:
                if path.suffix == ".jsonl":
                    raise RuntimeError("forced jsonl failure")
                original_atomic_write_text(path, content)

            with patch("polymarket_backtest.paper_subset.atomic_write_text", side_effect=fail_jsonl):
                with self.assertRaisesRegex(RuntimeError, "forced jsonl failure"):
                    run_subset(input_dir=input_dir, out_dir=out_dir, limit=1)

            self.assertTrue(old_csv.exists())
            self.assertFalse(list(out_dir.glob("*.tmp")))

    def test_failed_latest_write_restores_prior_latest_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            out_dir = root / "out"
            write_rows(
                input_dir / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Q1",
                        "yes_bid": "0.40",
                        "yes_ask": "0.42",
                        "no_bid": "0.56",
                        "no_ask": "0.58",
                        "fair_yes": "0.50",
                        "action": "skip",
                    }
                ],
            )
            out_dir.mkdir(parents=True)
            (out_dir / "latest_paper_signals.csv").write_text("old csv\n")
            (out_dir / "latest_paper_signals.jsonl").write_text("old jsonl\n")
            (out_dir / "latest_manifest.json").write_text('{"old": true}\n')
            original_atomic_write_text = paper_subset.atomic_write_text
            failed = False

            def fail_latest_jsonl(path: Path, content: str) -> None:
                nonlocal failed
                if path.name == "latest_paper_signals.jsonl" and not failed:
                    failed = True
                    raise RuntimeError("forced latest failure")
                original_atomic_write_text(path, content)

            with patch("polymarket_backtest.paper_subset.atomic_write_text", side_effect=fail_latest_jsonl):
                with self.assertRaisesRegex(RuntimeError, "forced latest failure"):
                    run_subset(input_dir=input_dir, out_dir=out_dir, limit=1)

            self.assertEqual((out_dir / "latest_paper_signals.csv").read_text(), "old csv\n")
            self.assertEqual((out_dir / "latest_paper_signals.jsonl").read_text(), "old jsonl\n")
            self.assertEqual((out_dir / "latest_manifest.json").read_text(), '{"old": true}\n')
            self.assertFalse(list(out_dir.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
