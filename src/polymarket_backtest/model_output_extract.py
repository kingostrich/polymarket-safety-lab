from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_KEYS = {"logged_at", "market_id", "input_hash", "fair_yes", "cost", "reasoning"}


@dataclass(frozen=True)
class ExtractionResult:
    raw_path: str
    output_path: str
    manifest_path: str
    raw_lines: int
    records: int
    ignored_non_json_lines: int
    malformed_json_lines: int
    missing_required_key_rows: int
    unexpected_key_rows: int
    expected_records: int
    status: str


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def extract_json_objects(raw_text: str, allowed_keys: set[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    allowed_keys = allowed_keys or REQUIRED_KEYS
    records: list[dict[str, Any]] = []
    counters = {
        "raw_lines": 0,
        "ignored_non_json_lines": 0,
        "malformed_json_lines": 0,
        "missing_required_key_rows": 0,
        "unexpected_key_rows": 0,
    }
    for line in raw_text.splitlines():
        counters["raw_lines"] += 1
        stripped = line.strip()
        if not stripped:
            counters["ignored_non_json_lines"] += 1
            continue
        if not stripped.startswith("{"):
            counters["ignored_non_json_lines"] += 1
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            counters["malformed_json_lines"] += 1
            continue
        if not isinstance(row, dict):
            counters["malformed_json_lines"] += 1
            continue
        if not REQUIRED_KEYS <= set(row):
            counters["missing_required_key_rows"] += 1
        if set(row) - allowed_keys:
            counters["unexpected_key_rows"] += 1
        records.append(row)
    return records, counters


def extract_model_output(raw_path: Path, output_path: Path, expected_records: int = 0, strict: bool = True) -> ExtractionResult:
    records, counters = extract_json_objects(raw_path.read_text(encoding="utf-8"))
    status = "PASS"
    if counters["malformed_json_lines"] or counters["missing_required_key_rows"] or counters["unexpected_key_rows"]:
        status = "FAIL"
    if expected_records > 0 and len(records) != expected_records:
        status = "FAIL"
    if strict and status != "PASS":
        raise ValueError(
            "model output extraction failed: "
            f"records={len(records)} expected={expected_records} "
            f"malformed={counters['malformed_json_lines']} "
            f"missing_keys={counters['missing_required_key_rows']} "
            f"unexpected_keys={counters['unexpected_key_rows']}"
        )

    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    atomic_write_text(output_path, content)
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    result = ExtractionResult(
        raw_path=str(raw_path),
        output_path=str(output_path),
        manifest_path=str(manifest_path),
        raw_lines=counters["raw_lines"],
        records=len(records),
        ignored_non_json_lines=counters["ignored_non_json_lines"],
        malformed_json_lines=counters["malformed_json_lines"],
        missing_required_key_rows=counters["missing_required_key_rows"],
        unexpected_key_rows=counters["unexpected_key_rows"],
        expected_records=expected_records,
        status=status,
    )
    manifest = {**asdict(result), "generated_at": datetime.now(UTC).isoformat()}
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract strict minimal JSONL forecast rows from a raw model response.")
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--expected-records", type=int, default=0)
    parser.add_argument("--no-strict", action="store_true", help="Write output and manifest even when validation status is FAIL.")
    args = parser.parse_args()

    result = extract_model_output(
        raw_path=Path(args.raw_file),
        output_path=Path(args.out_jsonl),
        expected_records=args.expected_records,
        strict=not args.no_strict,
    )
    for key, value in asdict(result).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
