# crm-copilot

Turn sales call transcripts into clean CRM updates. Extracts MEDDPICC, objections and next steps with an LLM, proposes a deal stage and a follow-up email, and writes to a self-hosted Twenty CRM only after human approval. Exposes the same actions as an MCP server so Claude or any agent can use them.

## Features

- **MEDDPICC extraction** — LLM extracts all 8 fields with evidence quotes from transcripts
- **Anti-hallucination guard** — Every evidence quote verified against source transcript
- **Deterministic stage mapping** — Pure Python rules: discovery→SCREENING, qualified→MEETING, evaluation→PROPOSAL, negotiation→PROPOSAL
- **Human-in-the-loop** — CLI shows full plan, asks for confirmation before writing to CRM
- **Idempotent writes** — No duplicate opportunities per company
- **Twenty CRM integration** — REST API adapter for self-hosted Twenty
- **MCP server** — FastMCP stdio server for agent consumption
- **Offline tests** — All tests run without external APIs (FakeAdapter)

## Quickstart

```bash
# Install
uv sync --dev

# Configure
cp .env.example .env
# Edit .env with your LiteLLM and Twenty credentials

# Run CLI
uv run crm-copilot --help

# Process a transcript (dry-run with FakeAdapter)
uv run crm-copilot process examples/transcript_1_discovery.txt --dry-run

# Process and apply to Twenty CRM (requires TWENTY_API_KEY)
uv run crm-copilot process examples/transcript_1_discovery.txt

# List opportunities with MEDDPICC gaps
uv run crm-copilot missing

# Check connectivity
uv run crm-copilot doctor

# Run MCP server (stdio)
uv run crm-copilot mcp
```

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
MCP server (FastMCP) exposes: process_transcript, apply_plan_tool, list_gaps, health_check
```

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_MODEL` | LiteLLM model alias (e.g., `nim-laguna`, `groq-qwen`) | Yes |
| `LLM_JUDGE_MODEL` | Judge model for validation (e.g., `nim-step`) | No |
| `LITELLM_BASE_URL` | LiteLLM proxy URL | Yes |
| `LITELLM_API_KEY` | LiteLLM master key | If proxy requires |
| `TWENTY_BASE_URL` | Twenty server URL (default: http://localhost:3000) | For Twenty |
| `TWENTY_API_KEY` | Twenty API key | For Twenty |
| `TWENTY_REST_PREFIX` | REST prefix (default: `/rest`) | No |
| `AUTO_APPLY` | Skip confirmation prompt | No |

## CLI Commands

### `process`
Process a transcript and optionally apply to CRM.

```bash
# Dry run (FakeAdapter, no writes)
crm-copilot process transcript.txt --dry-run

# Apply to CRM with confirmation
crm-copilot process transcript.txt

# Auto-apply without confirmation
crm-copilot process transcript.txt --yes

# Save plan to JSON file
crm-copilot process transcript.txt --out plan.json
```

### `missing`
List open opportunities with MEDDPICC gaps.

```bash
crm-copilot missing
```

### `doctor`
Check LLM and Twenty connectivity.

```bash
crm-copilot doctor
```

### `mcp`
Run MCP server (stdio transport).

```bash
crm-copilot mcp
```

## MCP Tools

The MCP server exposes 4 tools:

| Tool | Description |
|------|-------------|
| `process_transcript(transcript)` | Extract insights and plan updates from transcript |
| `apply_plan_tool(plan)` | Apply UpdatePlan to CRM |
| `list_gaps()` | List open opportunities with MEDDPICC gaps |
| `health_check()` | Check LLM and Twenty connectivity |

## MEDDPICC Storage

Stored as compact JSON in custom `meddpicc` field on Opportunity (Option A):

```json
{
  "metrics": {"value": "$120k ARR lost, 20 hrs/week", "confidence": 0.9},
  "economic_buyer": {"value": "VP Engineering (Mike), CTO (Lisa)", "confidence": 0.85},
  ...
}
```

Human-readable table also included in note body for UI visibility.

## Project Structure

```
src/crm_copilot/
├── config.py          # Settings (pydantic-settings)
├── models.py          # Pydantic models (CallInsights, UpdatePlan, etc.)
├── llm.py             # CachedLLMClient (disk cache, retry, JSON validation)
├── extract.py         # MEDDPICC extraction + anti-hallucination
├── planner.py         # Deterministic stage rules, missing fields, note/tasks
├── followup.py        # LLM follow-up email (no em dashes)
├── apply.py           # apply_plan delegation
├── cli.py             # Typer CLI
├── mcp_server.py      # FastMCP server
└── crm/
    ├── base.py        # CRMAdapter Protocol
    ├── fake.py        # FakeAdapter (in-memory, for tests/dry-run)
    └── twenty.py      # TwentyAdapter (REST API)
```

## Testing

```bash
# Run all tests
bash scripts/gate.sh

# Or directly
uv run pytest -q

# Lint
uv run ruff check .
```

Gate: `ruff check . && pytest -q` — must pass before commit.

## Milestones

| Milestone | Status | Description |
|-----------|--------|-------------|
| M0 | ✅ | Scaffold (uv, deps, CI, gate) |
| M1 | ✅ | Models + LLM wrapper (cache, retry, validation) |
| M2 | ✅ | Extraction (prompt, anti-hallucination) |
| M3 | ✅ | Planner + follow-up (stage rules, email) |
| M4 | ✅ | Fake adapter + apply + CLI (review checkpoint) |
| M5 | ✅ | Twenty adapter (REST API, verified live) |
| M6 | ✅ | MCP server (FastMCP, 4 tools) |
| M7 | ✅ | Examples + evals (3 transcripts, eval script) |
| M8 | ✅ | Polish + final review |

## License

MIT