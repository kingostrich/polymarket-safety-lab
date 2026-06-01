# Contributing

Thanks for helping improve this paper-only prediction-market research scaffold.

## Project Boundaries

- Keep the default workflow paper-only.
- Do not add live order placement, wallet signing, private-key handling, or asset movement.
- Do not add Web3 signing dependencies such as `web3.py`, `eth-account`, wallet SDKs, or production order-submission SDK paths without a separate security design review.
- Do not commit API keys, wallet credentials, account exports, private transaction histories, or personally identifying financial records.
- Treat all model outputs and strategy claims as untrusted until they are auditable through tests, manifests, and reproducible reports.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests
```

## Pull Request Checklist

- Explain the paper-trading or backtesting behavior being changed.
- Include focused tests for new behavior.
- Run:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m compileall src tests
```

- If the change affects readiness gates, model benchmark reports, settlement replay, auth/security, CI, or project policy, request an external review and summarize what was checked.

## Issue Reports

Useful bug reports include:

- Command run.
- Input dataset or mock fixture used.
- Expected and actual output.
- Relevant manifest paths.
- Whether the issue affects accounting, risk flags, or safety gates.

## Good First Contributions

- Improve sample dataset validation.
- Add documentation examples for existing CLI commands.
- Add tests for malformed forecast inputs.
- Improve report summaries without changing paper-only safety boundaries.
