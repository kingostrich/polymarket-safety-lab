from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.simulator import load_snapshots


class SampleDatasetValidationTest(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def test_missing_required_columns_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.csv"
            self._write(
                path,
                "timestamp,market_id\n"
                "2026-01-01T00:00:00+00:00,m1\n",
            )
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_snapshots(path)

    def test_invalid_probability_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.csv"
            self._write(
                path,
                "timestamp,market_id,question,yes_price,no_price,fair_yes\n"
                "2026-01-01T00:00:00+00:00,m1,Q,1.2,0.0,0.5\n",
            )
            with self.assertRaisesRegex(ValueError, "yes_price must be in \\[0, 1\\]"):
                load_snapshots(path)

    def test_malformed_market_id_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.csv"
            self._write(
                path,
                "timestamp,market_id,question,yes_price,no_price,fair_yes\n"
                "2026-01-01T00:00:00+00:00,bad id,Q,0.5,0.5,0.5\n",
            )
            with self.assertRaisesRegex(ValueError, "malformed market_id|must not contain whitespace"):
                load_snapshots(path)


if __name__ == "__main__":
    unittest.main()
