# crm-copilot: SPEC

**Pitch:** Turn sales call transcripts into clean CRM updates. Extracts MEDDPICC, objections and next steps with an LLM, proposes a deal stage and a follow-up email, and writes to a self-hosted Twenty CRM only after human approval. Exposes the same actions as an MCP server so Claude or any agent can use them.

Package name: `crm_copilot`. CLI name: `crm-copilot`.

## Architecture

```
transcript.txt ──> extract (LLM, JSON schema) ──> CallInsights
                                                    │
                    plan_updates (pure Python) <────┘
                           │
                     UpdatePlan  ──> review (CLI shows diff, asks y/n)
                           │
                     CRMAdapter.apply(plan)   (TwentyAdapter | FakeAdapter)
                           │
MCP server (FastMCP) exposes: process_call, list_deals_missing, get_deal_summary, apply_plan
```

## Modules

- `config.py`: `Settings` (pydantic-settings): `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `TWENTY_BASE_URL` (default `http://localhost:3000`), `TWENTY_API_KEY`, `AUTO_APPLY` (default `false`), `CACHE_DIR` (default `.cache`).
- `llm.py`: wrapper described in AGENTS.md. Function `complete_json(system: str, user: str, schema: type[BaseModel]) -> BaseModel`.
- `models.py`:
  - `MeddpiccField(value: str | None, evidence_quote: str | None, confidence: Literal["low","medium","high"])`
  - `CallInsights`: `company_name`, `contact_names: list[str]`, `summary` (max ~80 words), `meddpicc: dict` with keys `metrics, economic_buyer, decision_criteria, decision_process, paper_process, identify_pain, champion, competition`, each a `MeddpiccField`; `objections: list[str]`, `next_step: str | None`, `next_step_date: str | None` (ISO date if stated), `budget_signal`, `timeline_signal`.
  - `StageSuggestion(stage: str, reason: str)`
  - `UpdatePlan`: `company_name`, `opportunity_fields: dict[str, Any]`, `note_markdown: str`, `tasks: list[TaskDraft]`, `followup_email: EmailDraft(subject, body)`, `missing_fields: list[str]`, `stage: StageSuggestion`.
- `extract.py`: `extract_insights(transcript: str) -> CallInsights`. One LLM call. The prompt must tell the model: only use facts present in the transcript, `evidence_quote` must be a verbatim substring of the transcript, use null when unknown. After the call, **verify in code** that every `evidence_quote` is a substring of the transcript; if not, set that field's `value` and `evidence_quote` to None and confidence to "low" (anti-hallucination guard).
- `planner.py`: `plan_updates(insights) -> UpdatePlan`. Pure Python, no LLM, except the follow-up email which uses one LLM call in `followup.py`. Stage rules (deterministic, documented in README):
  - no identified pain → `discovery`
  - pain + champion → `qualified`
  - pain + champion + economic_buyer + decision_process → `evaluation`
  - all of the above + paper_process → `negotiation`
  Stage names are mapped to Twenty's stage values via a config dict filled from `docs/ANSWERS.md`.
  `missing_fields` = MEDDPICC keys with value None, phrased as questions to ask next call.
- `followup.py`: `draft_followup(insights) -> EmailDraft`. Short, plain text, references the next step, no em dashes.
- `crm/base.py`: `CRMAdapter` protocol: `find_company(name) -> str | None`, `upsert_company(name) -> str`, `find_open_opportunity(company_id) -> dict | None`, `upsert_opportunity(company_id, fields) -> str`, `add_note(target_id, markdown) -> str`, `add_task(target_id, task) -> str`, `list_opportunities() -> list[dict]`.
- `crm/fake.py`: in-memory implementation used by tests and by `--dry-run`.
- `crm/twenty.py`: Twenty REST implementation with `httpx`, Bearer `TWENTY_API_KEY`. **Do not guess endpoints or field names.** Use only the REST paths, field names and MEDDPICC storage decision in `docs/ANSWERS.md`.
- `apply.py`: `apply_plan(plan, adapter) -> ApplyResult` (ids created/updated). Idempotent per company + opportunity: running twice must not create a second opportunity.
- `cli.py` (typer):
  - `crm-copilot process <transcript.txt> [--dry-run] [--yes] [--out plan.json]`: extract, plan, print a rich table of proposed changes, ask "Apply to CRM? [y/N]" unless `--yes` or `AUTO_APPLY=true`.
  - `crm-copilot missing`: list open opportunities whose MEDDPICC has gaps.
  - `crm-copilot doctor`: check LLM endpoint reachable, Twenty reachable and key valid.
- `mcp_server.py`: FastMCP server (`pip: fastmcp`, or the official `mcp` package's FastMCP; ask if unsure which is installed). Tools: `process_call(transcript: str, apply: bool = False)`, `list_deals_missing_info()`, `get_deal_summary(company_name: str)`, `apply_plan(plan_json: str)`. `apply` defaults to False; when False it returns the plan only. Run with `crm-copilot mcp` (stdio).

## Data
- `examples/transcripts/`: 6 fictional call transcripts (300 to 900 words each) for fictional B2B SaaS deals, covering: first discovery call, technical eval with a competitor mentioned, pricing/procurement call, a call with no clear next step, a messy call with small talk, a call where the buyer is not the decision maker. Write them by hand-style prompting, check they read naturally.
- `examples/expected/`: for each transcript, a hand-checked JSON of the key expected facts (company, champion name or null, competitor or null, next step present yes/no).

## Evals
`evals/run.py`: runs extraction on all example transcripts, compares to `examples/expected/`, prints a table: field accuracy per transcript, overall accuracy, hallucination guard triggers. Supports `--model` to compare two LiteLLM aliases. Save results to `evals/results/<model>.json`. README shows one results table.

## Milestones
- **M0 Scaffold:** uv project, layout, ruff, pytest, `.env.example`, `.gitignore`, `PROGRESS.md`, GitHub Actions CI (ruff + pytest on push), README stub. Test: a trivial import test.
- **M1 Models + LLM wrapper:** `models.py`, `llm.py` with disk cache, retry, JSON validation retry. Tests with a fake OpenAI client: cache hit, invalid JSON then valid, 429 retry.
- **M2 Extraction:** `extract.py` + prompt in `prompts/extract.md`. Tests: fake LLM returns a quote not in transcript → field nulled; valid quote kept.
- **M3 Planner + follow-up:** `planner.py`, `followup.py`. Tests: each stage rule, missing_fields wording, no em dash in email body.
- **M4 Fake adapter + apply + CLI (REVIEW CHECKPOINT):** `crm/base.py`, `crm/fake.py`, `apply.py`, `cli.py` (`process --dry-run`, `missing`). Tests: idempotency (apply twice, one opportunity), CLI with typer's CliRunner.
- **M5 Twenty adapter:** use the API details in `docs/ANSWERS.md`; if any are missing, stop and ask. Implement `crm/twenty.py`, `doctor`. Tests with respx mocks built from the real responses the user pasted. Then the user runs one real `process` against their Twenty and confirms.
- **M6 MCP server:** `mcp_server.py`, `crm-copilot mcp`. Tests call tool functions directly with the fake adapter. Document how to add it to Claude Desktop / Claude Code config in README.
- **M7 Examples + evals:** transcripts, expected files, `evals/run.py`, results for at least 2 models.
- **M8 Polish (FINAL REVIEW CHECKPOINT):** README (pitch, Mermaid diagram, quickstart, Twenty setup, MCP setup, stage rules, eval table, design decisions: human-in-the-loop default, evidence-quote guard, adapter pattern), demo GIF script for `vhs` (`demo.tape`), repo topics list in PROGRESS.md for the user to add.

## Done means
`uv run pytest` green offline, CI green, `crm-copilot process examples/transcripts/01.txt --dry-run` prints a sensible plan, one real write to the user's Twenty confirmed, README complete.
