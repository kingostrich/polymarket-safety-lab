# Model Benchmark Smoke Run

Date: 2026-05-30

This run validates that a delegated model can return minimal forecast rows that pass the local import, audit, and survival replay pipeline. It is not a strategy-performance result.

## Input

- Source paper directory: `data/paper/model_bench_20`
- Source records: 20
- Prompt template: `data/forecasts/model_bench_20/template.jsonl`
- Template fields supplied to the model: `logged_at`, `market_id`, `question`, bid/ask context, liquidity, volume, `input_hash`
- Required model output fields: `logged_at`, `market_id`, `input_hash`, `fair_yes`, `cost`, `reasoning`

## Delegated Model Call

- Provider label: `agy`
- Model label used in imported records: `Gemini 3.5 Flash High via agy`
- Raw model output: `/tmp/agy_model_bench20_raw.txt`
- Saved minimal forecast file: `data/forecasts/agy_smoke/model_minimal.jsonl`
- Imported canonical forecasts: `data/forecasts/agy_smoke/imported/latest_forecasts.jsonl`
- Exit status: 0
- Approximate latency: 22 seconds
- Cost field: 0.0 for every row

The model was instructed to use only the supplied row context and not current real-world outcomes. The returned probabilities were midpoint-style estimates from the visible bid/ask context, so this run only validates plumbing and schema compliance.

## Audit Result

- Audit file: `data/forecasts/agy_smoke/imported/latest_audit.json`
- Status: PASS
- Source rows: 20
- Forecast records: 20
- Matched records: 20
- Coverage: 1.0
- Input hash mismatches: 0
- Invalid probabilities: 0
- Invalid costs: 0
- Blank reasoning/model/provider values: 0
- Provider counts: `agy:20`
- Model counts: `Gemini 3.5 Flash High via agy:20`

## Survival Replay Result

- Report: `data/paper/model_bench_20_survival_agy_smoke/latest_survival_report.json`
- State: ALIVE
- Rows processed: 20
- Forecast calls: 20
- Forecast cost total: 0.0
- Signals seen: 0
- Positions opened: 0
- Positions closed: 0
- Final equity: 50.0
- Max drawdown: 0.0

## Interpretation

The delegated model path is now connected end to end for a small controlled benchmark:

1. Create a bounded paper subset.
2. Generate a model prompt template.
3. Generate a reusable model prompt packet.
4. Collect minimal model forecast rows.
5. Run the end-to-end model benchmark harness.
6. Import rows into the canonical forecast schema.
7. Audit row coverage and input hashes.
8. Replay with the survival engine.

The current smoke output intentionally does not create trades because the returned fair values track the market midpoint. A real model comparison needs either a forecast prompt that produces independent probabilities from a defined evidence packet, or a separate calibrated probability source. Use the full snapshot history, not the 20-row smoke subset, for ROI and drawdown conclusions.

Prompt packets treat `question` and every other input field as untrusted data. This matters because market questions are externally sourced text and could contain instruction-like strings. The generated packet isolates rows in a JSONL data block and tells the model not to treat row text as instructions.
