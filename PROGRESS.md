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

### M3 - Planner + follow-up
- Status: IN PROGRESS

---

### M4 - Fake adapter + apply + CLI (REVIEW CHECKPOINT)
- Status: NOT STARTED

---

### M5 - Twenty adapter
- Status: NOT STARTED

---

### M6 - MCP server
- Status: NOT STARTED

---

### M7 - Examples + evals
- Status: NOT STARTED

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