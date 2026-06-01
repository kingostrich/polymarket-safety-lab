from __future__ import annotations

from .models import MarketSnapshot, Side, Signal


def clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def kelly_fraction(probability: float, price: float, max_fraction: float = 0.06) -> float:
    """Kelly fraction for a binary token that pays 1.0 if it wins."""
    probability = clamp_probability(probability)
    if price <= 0.0 or price >= 1.0:
        return 0.0
    raw_fraction = (probability - price) / (1.0 - price)
    return max(0.0, min(raw_fraction, max_fraction))


def build_signal(
    snapshot: MarketSnapshot,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
) -> Signal | None:
    """Translate the PDF strategy into a YES/NO trading signal.

    The PDF compares YES fair value to current YES price. For sizing, each side is
    treated as its own binary token so NO uses (1 - fair_yes) and no_price.
    """
    fair_yes = clamp_probability(snapshot.fair_yes)
    yes_edge = fair_yes - snapshot.yes_price
    no_probability = 1.0 - fair_yes
    no_edge = no_probability - snapshot.no_price

    if yes_edge >= edge_threshold:
        fraction = kelly_fraction(fair_yes, snapshot.yes_price, max_fraction)
        if fraction <= 0:
            return None
        return Signal(
            market_id=snapshot.market_id,
            side=Side.YES,
            probability=fair_yes,
            price=snapshot.yes_price,
            edge=yes_edge,
            fraction=fraction,
        )

    if no_edge >= edge_threshold:
        fraction = kelly_fraction(no_probability, snapshot.no_price, max_fraction)
        if fraction <= 0:
            return None
        return Signal(
            market_id=snapshot.market_id,
            side=Side.NO,
            probability=no_probability,
            price=snapshot.no_price,
            edge=no_edge,
            fraction=fraction,
        )

    return None
