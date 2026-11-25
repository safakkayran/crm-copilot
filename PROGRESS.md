# PROGRESS.md

## Milestone Log

### M0 - Scaffold ✅
- uv project initialized with src layout
- Dependencies: httpx, pydantic, pydantic-settings, typer, rich, openai, python-dotenv
- Dev dependencies: pytest, pytest-asyncio, respx, ruff, fastmcp
- Ruff and pytest configured
- GitHub Actions CI (ruff + pytest on push)
- .env.example with placeholders
- Trivial import test passing
- Package structure: src/crm_copilot/
- Gate: PASSED (1 test)

---

### M1 - Models + LLM wrapper ✅
- `config.py`: Settings with pydantic-settings
- `models.py`: MeddpiccField, CallInsights, StageSuggestion, TaskDraft, EmailDraft, UpdatePlan, ApplyResult
- `llm.py`: CachedLLMClient with disk cache, retry on 429/5xx, JSON validation retry
- Tests: cache hit, invalid JSON retry, 429 retry, convenience function
- Gate: PASSED (14 tests)

---

### M2 - Extraction ✅
- `prompts/extract.md`: Detailed extraction prompt
- `extract.py`: extract_insights() with LLM call and anti-hallucination verification
- Tests: valid quote kept, invalid quote nulled, null quote unchanged, LLM call + verification, hallucinated quote removed
- Gate: PASSED (19 tests)

---

### M3 - Planner + follow-up ✅
- `planner.py`: Deterministic stage rules, missing fields, opportunity fields, note markdown, tasks
- `followup.py`: LLM-based follow-up email with no em dashes
- Tests: stage rules (4), missing fields, opportunity fields, note markdown, tasks, followup no em dash, integration
- Gate: PASSED (33 tests)

---

### M4 - Fake adapter + apply + CLI (REVIEW CHECKPOINT) ✅
- `crm/base.py`: CRMAdapter Protocol with all required methods
- `crm/fake.py`: FakeAdapter in-memory implementation with idempotent upserts
- `apply.py`: apply_plan() delegation to adapter
- `cli.py`: Typer CLI with `process`, `missing`, `doctor`, `mcp` commands
- `crm/__init__.py`: exports
- Tests: FakeAdapter CRUD, idempotency, apply_plan, CLI dry-run, output file, missing, doctor, help
- Gate: PASSED (48 tests)

---

### M5 - Twenty adapter ✅
- Verified live Twenty instance against ANSWERS.md spec (`/rest` prefix, field names, filter syntax)
- `crm/twenty.py`: TwentyAdapter with full REST API implementation
  - Company CRUD (find, upsert with idempotency)
  - Opportunity CRUD (find open, upsert with idempotency per company)
  - Notes (create with markdown, link to opportunity + company via noteTargets)
  - Tasks (create with due dates, link to opportunity + company via taskTargets)
  - List opportunities with MEDDPICC gaps
  - Health check for `doctor` command
- CLI auto-selects TwentyAdapter when `TWENTY_API_KEY` is set
- Manual verification: health check, find/upsert company, find/upsert opportunity, apply_plan with idempotency
- Gate: PASSED (48 tests)

---

### M6 - MCP server ✅
- `mcp_server.py`: FastMCP server with 4 tools:
  - `process_transcript(transcript)` → UpdatePlan: extract insights + plan updates
  - `apply_plan_tool(plan)` → ApplyResult: apply plan to CRM (Twenty or Fake)
  - `list_gaps()` → list[dict]: open opportunities with MEDDPICC gaps
  - `health_check()` → dict: LLM + Twenty connectivity status
- CLI `mcp` command runs the stdio server
- Gate: PASSED (48 tests)

---

### M7 - Examples + evals ✅
- `examples/transcript_1_discovery.txt`: Discovery call - pain, budget ($120k ARR lost), decision makers (VP Eng, CTO), criteria, timeline (Q1)
- `examples/transcript_2_negotiation.txt`: Negotiation - pricing ($52.5k enterprise), SSO, security review, procurement
- `examples/transcript_3_evaluation.txt`: Technical deep dive - EU data residency, CMK, encryption, PII, SIG Lite questionnaire
- `examples/run_eval.py`: Evaluation script running full pipeline (extract → plan → apply) on all transcripts
- `examples/README.md`: Documentation with expected MEDDPICC extraction for each transcript
- Note: Actual LLM eval requires LiteLLM proxy with API keys (NVIDIA NIM, Groq, OpenRouter) - framework complete

---

### M8 - Polish (FINAL REVIEW CHECKPOINT)
- Status: NOT STARTED

---

## Decisions
- Using src/ layout with package name `crm_copilot`
- Python 3.11+ required (spec says 3.11+)
- LiteLLM models: nim-laguna (worker), nim-step (judge)
- Twenty REST prefix: /rest (configurable via TWENTY_REST_PREFIX)
- MEDDPICC storage: Option A (custom field `meddpicc` on Opportunity)
- Stage mapping: discovery→SCREENING, qualified→MEETING, evaluation→PROPOSAL, negotiation→PROPOSAL

## Skipped, needs user
- None yet

## Test changes
- None yet

## Known issues
- None yet