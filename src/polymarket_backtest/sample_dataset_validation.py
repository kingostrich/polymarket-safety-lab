from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime

REQUIRED_SNAPSHOT_COLUMNS = {
    "timestamp",
    "market_id",
    "question",
    "yes_price",
    "no_price",
    "fair_yes",
}

_MARKET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def validate_snapshot_header(fieldnames: Sequence[str] | None) -> None:
    if not fieldnames:
        raise ValueError("snapshot CSV has no header row")
    missing = REQUIRED_SNAPSHOT_COLUMNS.difference(set(fieldnames))
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"snapshot CSV missing required columns: {missing_list}")


def _parse_iso_timestamp(value: str, *, row_num: int) -> None:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"row {row_num}: timestamp is required")
    try:
        datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"row {row_num}: invalid timestamp: {cleaned!r}") from exc


def _parse_probability(value: str, *, row_num: int, field: str) -> None:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"row {row_num}: {field} is required")
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"row {row_num}: {field} must be a float: {cleaned!r}") from exc
    if not math.isfinite(parsed) or not (0.0 <= parsed <= 1.0):
        raise ValueError(f"row {row_num}: {field} must be in [0, 1], got {parsed!r}")


def _validate_market_id(value: str, *, row_num: int) -> None:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"row {row_num}: market_id is required")
    if " " in cleaned or "\t" in cleaned or "\n" in cleaned:
        raise ValueError(f"row {row_num}: market_id must not contain whitespace: {cleaned!r}")
    if not _MARKET_ID_RE.match(cleaned):
        raise ValueError(
            f"row {row_num}: malformed market_id {cleaned!r} (expected [A-Za-z0-9][A-Za-z0-9_-]...)"
        )


def validate_snapshot_row(row: Mapping[str, str], *, row_num: int) -> None:
    _parse_iso_timestamp(str(row.get("timestamp", "")), row_num=row_num)
    _validate_market_id(str(row.get("market_id", "")), row_num=row_num)

    _parse_probability(str(row.get("yes_price", "")), row_num=row_num, field="yes_price")
    _parse_probability(str(row.get("no_price", "")), row_num=row_num, field="no_price")
    _parse_probability(str(row.get("fair_yes", "")), row_num=row_num, field="fair_yes")

    resolved_outcome = str(row.get("resolved_outcome", "")).strip()
    if resolved_outcome:
        outcome = resolved_outcome.upper()
        if outcome not in {"YES", "NO"}:
            raise ValueError(f"row {row_num}: resolved_outcome must be YES or NO, got {resolved_outcome!r}")

    fee_rate = str(row.get("fee_rate", "")).strip()
    if fee_rate:
        _parse_probability(fee_rate, row_num=row_num, field="fee_rate")

