import unittest

from polymarket_backtest.paper_logger import _levels


class PaperLoggerTest(unittest.TestCase):
    def test_levels_sort_bids_descending_and_asks_ascending(self) -> None:
        book = {
            "bids": [{"price": "0.01", "size": "5"}, {"price": "0.03", "size": "7"}],
            "asks": [{"price": "0.09", "size": "11"}, {"price": "0.04", "size": "13"}],
        }

        self.assertEqual(_levels(book, "bids")[0]["price"], 0.03)
        self.assertEqual(_levels(book, "asks")[0]["price"], 0.04)


if __name__ == "__main__":
    unittest.main()
