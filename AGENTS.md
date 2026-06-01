# Workspace AI Operating Rules

This workspace uses Codex as the primary operator. Manus MCP, Antigravity CLI, and Gemini CLI are supporting tools, not final authorities.

These rules apply to `/Users/gangtaesu/Documents/금융 에이전트` and all subfolders. The detailed operating-design rationale is maintained in `/Users/gangtaesu/Documents/New project/Codex_Manus_Gemini_운영설계.md`; this `AGENTS.md` is the project-level rule file Codex should follow automatically.

## Default Responsibility

- Codex owns task interpretation, local execution, file changes, verification, and final answers.
- Manus, Antigravity, and Gemini are external AI surfaces. Their output must be reviewed by Codex before use.
- Do not pass secrets, API keys, passwords, resident numbers, account numbers, brokerage credentials, private full-text documents, or raw private repository dumps to external AI.
- If external AI disagrees with Codex, compare evidence and either resolve explicitly or mark the uncertainty for the user.

## Financial Work

Financial tasks are high-stakes. Codex must verify current market data, dates, assumptions, and source quality before giving a final answer.

Rules:
- Do not present investment, tax, accounting, or legal conclusions as professional advice.
- For current prices, rates, earnings dates, macro indicators, regulations, filings, product terms, or broker/platform rules, verify with current official or primary sources when available.
- Never send account numbers, brokerage login data, API keys, portfolio exports with personally identifying details, tax documents, or private transaction histories to external AI.
- Antigravity may analyze anonymized tables, cleaned summaries, model assumptions, and draft reports, but Codex must verify formulas, source rows, key claims, and final recommendations.
- Manus may be used for broad market, company, product, or data-source discovery; Codex must check dates and primary evidence before finalizing.

## Manus MCP

Use Manus only when the task benefits from broad or long-running research.

Good uses:
- Market, company, product, institution, data-source, or candidate discovery.
- Wide web research across many sources.
- Research where 20-30 candidates or sources are expected.
- Manus-specific skills such as SimilarWeb, stock analysis, video, or music workflows.

Rules:
- Create at most one Manus task per normal user task.
- Wait for task completion instead of asking for interim results.
- If the result is incomplete, send at most one narrow follow-up focused on the gaps.
- Codex must synthesize the final answer from raw evidence, not just repeat the Manus result.

## Antigravity CLI

Use Antigravity CLI (`agy`) as a delegated partner for non-sensitive document, research-organization, data-cleaning, and first-pass analysis tasks. Codex remains the final judge.

Current local baseline:
- Binary: `/Users/gangtaesu/.local/bin/agy`
- Version: `1.0.1`
- Headless mode: `agy -p`
- Observed model: `Gemini 3.5 Flash (High)` in CLI status/logs
- Delegation benchmark: `/tmp/agy-delegation-bench`, average 93/100, Level 3 partial task partner allowed for non-sensitive knowledge work

Rules:
- Default to low-context review:
  `agy -p "Review only the provided excerpt/table/draft for omissions, contradictions, overclaims, weak evidence, data-quality issues, and financial-analysis risks. Do not edit files." --print-timeout 3m --log-file /tmp/agy-review.log`
- For non-sensitive document/research/data tasks, Codex may delegate first drafts, structured summaries, comparison tables, data-cleaning observations, and Codex review packets to Antigravity.
- Use Antigravity at most three times per normal user task unless the user explicitly asks for more: one task packet, one targeted follow-up, and one final critique.
- Send only short excerpts, anonymized tables, summaries, or sanitized assumptions.
- Record latency, exit status, output path, and observed model label when Antigravity materially affects a final answer.
- Do not use Antigravity for cost-sensitive bulk review until numeric usage/token capture is configured through `/usage` or statusline JSON.
- If Antigravity returns auth/model errors, falls into interactive onboarding, or cannot produce headless output, fall back to Gemini CLI or Codex-only review.

Delegation levels:
- Level 1 Reviewer: critique Codex outputs for omissions, contradictions, overclaims, weak evidence, unclear reasoning, and financial-analysis risks.
- Level 2 Draft Partner: create first drafts, summaries, comparison tables, and analysis outlines from sanitized inputs; Codex verifies and finalizes.
- Level 3 Task Partner, partial: perform first-pass sorting, candidate classification, repeated note cleanup, and small anonymized table analysis; Codex validates samples, formulas, high-impact claims, and final decisions.

Output contract for delegated work:
- Ask Antigravity to return `핵심 결론`, `근거`, `불확실성`, `검증 필요점`, and `Codex가 확인할 샘플`.
- Treat Antigravity claims as untrusted until Codex checks source snippets, sample rows, formulas, or cited evidence.
- If Antigravity creates side artifacts, Codex must inspect the artifact path and summarize only the relevant parts.

Codex verification requirements:
- For Level 2 output, Codex must verify the final structure, all high-impact claims, and any recommendation before delivery.
- For Level 3 partial output, Codex must check at least a representative sample of source rows/notes plus every claim that affects a user decision.
- If source evidence is missing, stale, or not directly inspectable, mark the result as provisional rather than treating Antigravity output as established fact.
- Do not let Antigravity make final legal, financial, hiring, medical, security, or privacy decisions.

## Gemini CLI

Use Gemini as a fallback second reviewer during the Antigravity transition window, not as the final writer.

Rules:
- Default to low-context review from a neutral directory:
  `cat "$EXCERPT_FILE" | gemini --skip-trust -m gemini-3.1-flash-lite -p "Review only the provided excerpt for omissions, contradictions, overclaims, and weak evidence. Do not use tools or inspect files." --output-format json`
- Record total tokens from `stats.models.*.tokens.total`.
- Target <= 12,000 tokens per automatic Gemini review; warn above 15,000; stop or redesign above 20,000 or when tool calls occur.
- Use Gemini at most twice per normal user task unless the user explicitly asks for more.
- Send only the necessary excerpt, diff, summary, or table, not the whole workspace or full private source text.
- Keep Gemini CLI installed as fallback for 7 days after Antigravity passes smoke, document review, and diff review.
- Do not use Gemini and Antigravity redundantly on the same ordinary task. Use Gemini mainly when Antigravity fails, numeric token stats are required, or a policy/security file such as `AGENTS.md` needs independent review.

## Korean-Law MCP

For legal work, official legal sources come first.

Rules:
- Use korean-law MCP for statutes, cases, amendment history, and official legal evidence.
- If the user says "korean-law MCP만 사용", do not use Manus, Antigravity, Gemini, or web search.
- Do not send legal matter originals, resident numbers, private facts, account details, or full confidential documents to external AI.
- Antigravity may review only anonymized excerpts for omissions, contradictions, overclaims, and unclear reasoning.

## Routing

- Simple command, local inspection, or small file work: Codex only.
- Important written output: Codex may delegate a sanitized first draft or comparison table to Antigravity, then Codex verifies and finalizes.
- Broad current research: Manus researches, Codex reviews, Antigravity organizes findings or checks gaps only when the result affects a final recommendation.
- Financial research: Manus or web/primary-source verification gathers current evidence; Antigravity may organize sanitized findings; Codex verifies dates, sources, formulas, and final conclusions.
- Data collection/cleanup/analysis: Codex may delegate anonymized small-table first-pass cleaning, classification, and insight extraction to Antigravity; Codex checks formulas, samples, outliers, and final conclusions.
- Coding work: Codex implements and tests; Antigravity reviews when a sensitive file changes or the change is broad, risky, or design-sensitive.
- Legal work: korean-law MCP supplies legal sources; Codex writes and verifies; external AI is used only for anonymized structure review when appropriate.

Force external AI review when changes affect:
- `AGENTS.md`
- package manifests or lockfiles
- MCP, automation, CI/CD, auth, security, billing, deployment, finance data pipelines, or policy configuration
- user-facing final reports, applications, legal/business/financial drafts, or high-impact recommendations

Avoid duplicate review:
- Do not route the same output through both Antigravity and Gemini unless the task is policy/security-critical or the first tool failed.
- When external AI opinions conflict, Codex resolves by checking source evidence and reports only material unresolved uncertainty.

## Security Preflight

Before sending any content to Manus, Antigravity, or Gemini:
- Redact secrets, tokens, passwords, private keys, resident numbers, account numbers, brokerage credentials, phone numbers, detailed addresses, and private full-text documents.
- Prefer short excerpts, anonymized tables, diffs, or summaries.
- Never use `--raw-output` for untrusted model output.
- Report external AI calls, token/credit usage, and material limitations when they affect the final answer.
- If uncertain whether an excerpt is safe to send externally, do not send it; summarize or redact further first.
- For any Level 2 or Level 3 Antigravity delegation, keep a short note of what was sent, what came back, and what Codex verified.
