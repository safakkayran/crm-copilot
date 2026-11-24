# crm-copilot

Turn sales call transcripts into clean CRM updates. Extracts MEDDPICC, objections and next steps with an LLM, proposes a deal stage and a follow-up email, and writes to a self-hosted Twenty CRM only after human approval. Exposes the same actions as an MCP server so Claude or any agent can use them.

## Quickstart

```bash
# Install
uv sync --dev

# Configure
cp .env.example .env
# Edit .env with your LiteLLM and Twenty credentials

# Run CLI
uv run crm-copilot --help

# Process a transcript (dry-run)
uv run crm-copilot process examples/transcripts/01.txt --dry-run
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
MCP server (FastMCP) exposes: process_call, list_deals_missing, get_deal_summary, apply_plan
```

## Milestones

- M0 Scaffold ✅
- M1 Models + LLM wrapper
- M2 Extraction
- M3 Planner + follow-up
- M4 Fake adapter + apply + CLI (REVIEW CHECKPOINT)
- M5 Twenty adapter
- M6 MCP server
- M7 Examples + evals
- M8 Polish (FINAL REVIEW CHECKPOINT)

## License

MIT