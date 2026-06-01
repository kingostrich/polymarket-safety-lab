from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Side(StrEnum):
    YES = "YES"
    NO = "NO"


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    market_id: str
    question: str
    yes_price: float
    no_price: float
    fair_yes: float
    liquidity: float = 0.0
    volume_24h: float = 0.0
    resolved_outcome: Side | None = None
    fee_rate: float = 0.0


@dataclass(frozen=True)
class Signal:
    market_id: str
    side: Side
    probability: float
    price: float
    edge: float
    fraction: float


@dataclass
class Position:
    market_id: str
    side: Side
    shares: float
    entry_price: float
    entry_time: datetime
    cost: float
    fees_paid: float = 0.0


@dataclass(frozen=True)
class ClosedTrade:
    market_id: str
    side: Side
    entry_time: datetime
    exit_time: datetime
    shares: float
    entry_price: float
    exit_price: float
    pnl: float
    fees_paid: float


@dataclass(frozen=True)
class BacktestResult:
    initial_bankroll: float
    final_equity: float
    total_return: float
    max_drawdown: float
    win_rate: float
    closed_trades: tuple[ClosedTrade, ...]
    equity_curve: tuple[tuple[datetime, float], ...]
