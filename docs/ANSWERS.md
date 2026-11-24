# ANSWERS.md

Fill this in BEFORE starting the loop and save it as `docs/ANSWERS.md` in the repo.
Delete the sections for other repos. Write "SKIP" for anything you want the agent to leave out.
The agent may only use external API details written here or in SPEC.

## Common (all repos)
- GitHub repo URL: https://github.com/safakkayran/crm-copilot
- Git push works from the server (yes/no): yes (HTTPS via gh auth)
- `node --version` output (or "not installed"): v26.12.1
- LiteLLM base URL (e.g. http://localhost:4000): http://127.0.0.1:4000
- Model alias for generation (LLM_MODEL): nim-laguna
- Model alias for evals judge (LLM_JUDGE_MODEL, must differ): nim-step

---

## crm-copilot

### Twenty instance
- Base URL (e.g. http://localhost:3000):
- API key created (yes/no; do not paste the key here, it goes in .env):

### REST endpoints and fields
Open Settings > APIs & Webhooks > API playground on your Twenty instance and paste the relevant parts below.
- Companies: list/search path, create path, field names for name and domain:
- Opportunities: list/search path, create path, update path, field names for name, stage, amount, company relation:
- Opportunity stage values exactly as in your instance (e.g. NEW, SCREENING, MEETING, PROPOSAL, CUSTOMER):
- Notes: create path, and how a note is linked to an opportunity or company (field names or a separate "noteTargets" call):
- Tasks: create path, field names for title, body, due date, and how a task is linked:
- One real example JSON response for a company and an opportunity (paste):

### Decisions
- MEDDPICC storage: (A) one text/JSON custom field on Opportunity, named: ____ / (B) separate custom fields / (C) only in the note body
- Stage mapping (our stage -> your Twenty value):
  - discovery ->
  - qualified ->
  - evaluation ->
  - negotiation ->