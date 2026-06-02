from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Side


@dataclass(frozen=True)
class PortfolioLeg:
    market_id: str
    side: Side
    max_notional: float
    hedge_role: str = ""
    correlation: float = 0.0


@dataclass(frozen=True)
class PortfolioGroup:
    group_id: str
    legs: tuple[PortfolioLeg, ...]
    max_joint_notional: float
    description: str = ""
    max_correlation: float = 1.0


@dataclass(frozen=True)
class PortfolioSpec:
    portfolio_id: str
    groups: tuple[PortfolioGroup, ...]


@dataclass(frozen=True)
class PortfolioRiskReport:
    generated_at: str
    status: str
    validation_errors: tuple[str, ...]
    violations: tuple[str, ...]
    portfolio_id: str
    groups_checked: int
    production_safe: bool
    readiness_decision: str


def as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def parse_side(value: Any) -> Side:
    text = str(value or "").upper()
    if text not in {Side.YES.value, Side.NO.value}:
        raise ValueError(f"side must be YES or NO, got {value!r}")
    return Side(text)


def parse_portfolio_spec(payload: dict[str, Any]) -> PortfolioSpec:
    portfolio_id = str(payload.get("portfolio_id") or "").strip()
    if not portfolio_id:
        raise ValueError("portfolio_id is required")
    groups_payload = payload.get("groups")
    if not isinstance(groups_payload, list) or not groups_payload:
        raise ValueError("groups must be a non-empty list")

    groups: list[PortfolioGroup] = []
    for group_index, group_payload in enumerate(groups_payload, start=1):
        if not isinstance(group_payload, dict):
            raise ValueError(f"group {group_index}: must be an object")
        group_id = str(group_payload.get("group_id") or "").strip()
        if not group_id:
            raise ValueError(f"group {group_index}: group_id is required")
        legs_payload = group_payload.get("legs")
        if not isinstance(legs_payload, list) or len(legs_payload) < 2:
            raise ValueError(f"group {group_id}: at least two legs are required")
        max_joint_notional = as_float(group_payload.get("max_joint_notional"))
        if max_joint_notional <= 0:
            raise ValueError(f"group {group_id}: max_joint_notional must be positive")
        max_correlation = as_float(group_payload.get("max_correlation"), 1.0)
        if not 0.0 <= max_correlation <= 1.0:
            raise ValueError(f"group {group_id}: max_correlation must be between 0 and 1")

        legs: list[PortfolioLeg] = []
        seen_market_ids: set[str] = set()
        for leg_index, leg_payload in enumerate(legs_payload, start=1):
            if not isinstance(leg_payload, dict):
                raise ValueError(f"group {group_id} leg {leg_index}: must be an object")
            market_id = str(leg_payload.get("market_id") or "").strip()
            if not market_id:
                raise ValueError(f"group {group_id} leg {leg_index}: market_id is required")
            if market_id in seen_market_ids:
                raise ValueError(f"group {group_id}: duplicate market_id {market_id}")
            seen_market_ids.add(market_id)
            max_notional = as_float(leg_payload.get("max_notional"))
            if max_notional <= 0:
                raise ValueError(f"group {group_id} leg {market_id}: max_notional must be positive")
            correlation = as_float(leg_payload.get("correlation"), 0.0)
            if not -1.0 <= correlation <= 1.0:
                raise ValueError(f"group {group_id} leg {market_id}: correlation must be between -1 and 1")
            if abs(correlation) > max_correlation:
                raise ValueError(f"group {group_id} leg {market_id}: absolute correlation exceeds group max_correlation")
            legs.append(
                PortfolioLeg(
                    market_id=market_id,
                    side=parse_side(leg_payload.get("side")),
                    max_notional=max_notional,
                    hedge_role=str(leg_payload.get("hedge_role") or ""),
                    correlation=correlation,
                )
            )
        groups.append(
            PortfolioGroup(
                group_id=group_id,
                legs=tuple(legs),
                max_joint_notional=max_joint_notional,
                description=str(group_payload.get("description") or ""),
                max_correlation=max_correlation,
            )
        )
    return PortfolioSpec(portfolio_id=portfolio_id, groups=tuple(groups))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_exposures(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    payload = load_json(path)
    exposures_payload = payload.get("market_exposures", payload)
    if not isinstance(exposures_payload, dict):
        raise ValueError("exposures must be a JSON object or contain market_exposures object")
    return {str(market_id): as_float(value) for market_id, value in exposures_payload.items()}


def validate_portfolio_spec(spec: PortfolioSpec, exposures: dict[str, float] | None = None) -> PortfolioRiskReport:
    exposures = exposures or {}
    violations: list[str] = []
    for group in spec.groups:
        active_joint_notional = 0.0
        for leg in group.legs:
            active_notional = abs(exposures.get(leg.market_id, 0.0))
            if active_notional > leg.max_notional:
                violations.append(
                    f"group {group.group_id} leg {leg.market_id}: active exposure {active_notional:.6f} exceeds leg cap {leg.max_notional:.6f}"
                )
            active_joint_notional += active_notional
        if active_joint_notional > group.max_joint_notional:
            violations.append(
                f"group {group.group_id}: active exposure {active_joint_notional:.6f} exceeds joint cap {group.max_joint_notional:.6f}"
            )
    status = "PASS" if not violations else "FAIL"
    return PortfolioRiskReport(
        generated_at=datetime.now(UTC).isoformat(),
        status=status,
        validation_errors=(),
        violations=tuple(violations),
        portfolio_id=spec.portfolio_id,
        groups_checked=len(spec.groups),
        production_safe=False,
        readiness_decision="NO_LIVE_TRADING" if violations else "PAPER_ONLY_REVIEW",
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a paper-only multi-leg portfolio risk schema.")
    parser.add_argument("--spec", required=True, help="Portfolio JSON spec path.")
    parser.add_argument("--exposures-json", help="Optional market exposure JSON path.")
    parser.add_argument("--out-json", default="data/paper/portfolio_risk_report.json")
    args = parser.parse_args()

    try:
        spec = parse_portfolio_spec(load_json(Path(args.spec)))
        report = validate_portfolio_spec(spec, load_exposures(Path(args.exposures_json)) if args.exposures_json else {})
    except Exception as exc:
        report = PortfolioRiskReport(
            generated_at=datetime.now(UTC).isoformat(),
            status="FAIL",
            validation_errors=(str(exc),),
            violations=(),
            portfolio_id="",
            groups_checked=0,
            production_safe=False,
            readiness_decision="NO_LIVE_TRADING",
        )
    write_json(Path(args.out_json), asdict(report))
    for key, value in asdict(report).items():
        print(f"{key}={value}")
    if report.status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
