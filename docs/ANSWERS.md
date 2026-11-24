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

> Source: Twenty's public API docs and its published OpenAPI schema for the default data model.
> These are Twenty DEFAULTS. Before M5 the agent MUST verify them against the live instance (see "Verification" at the bottom) and fix this section if anything differs.

### Twenty instance
- Base URL: http://localhost:3000
- API key created: yes (stored only in `.env` as `TWENTY_API_KEY`, never committed)
- Auth header: `Authorization: Bearer $TWENTY_API_KEY`
- REST prefix: `/rest` (official docs). Some published specs show `/rest/core`. The agent checks which one returns 200 on the live instance and uses that one everywhere via a single `TWENTY_REST_PREFIX` setting.
- Limits: 100 requests per minute, max 60 records per batch, `limit` max 60 per page. Pagination with `starting_after` cursor.

### Filter and query syntax
- `filter=field[COMPARATOR]:value`, comparators: eq, neq, in, is, gt, gte, lt, lte, like, ilike, startsWith, containsAny
- Commas mean AND; also `and()`, `or()`, `not()`
- Example: `GET /rest/companies?filter=name[eq]:"Acme"`
- `depth=0` returns relation ids like `companyId`; `depth=1` includes related records
- `fields=id,name` to trim responses

### Companies
- List/search: `GET /rest/companies?filter=name[eq]:"<name>"` (fallback: `name[ilike]:"%<name>%"`)
- Create: `POST /rest/companies`
- Update: `PATCH /rest/companies/{id}`
- Fields:
  - `name`: string
  - `domainName`: object `{ "primaryLinkUrl": "https://acme.com", "primaryLinkLabel": "", "secondaryLinks": [] }`

### Opportunities
- List/search open deal of a company: `GET /rest/opportunities?filter=companyId[eq]:"<companyId>",stage[neq]:"CUSTOMER"`
- Create: `POST /rest/opportunities`
- Update: `PATCH /rest/opportunities/{id}`
- Fields:
  - `name`: string (we use `"<Company> - <YYYY-MM>"` on create)
  - `stage`: enum, see below
  - `amount`: object `{ "amountMicros": 12000000000, "currencyCode": "USD" }` (micros: 1,000,000 = 1.00). Only set if the call states a budget number; otherwise leave unset.
  - `closeDate`: `YYYY-MM-DD` or null
  - `companyId`: UUID
  - `pointOfContactId`: UUID or null (we leave it null, we do not create People in v1)
  - `meddpicc`: custom Text field (see Decisions)

### Notes
- Create note: `POST /rest/notes`
  - `title`: string (we use `"Call notes <YYYY-MM-DD>"`)
  - `bodyV2`: object `{ "markdown": "<note markdown>" }` (do not send `blocknote`; if the live instance rejects markdown-only, record the error and stop)
- Link note to records: `POST /rest/noteTargets`
  - `noteId`: UUID of the note
  - `opportunityId`: UUID (we link to the opportunity)
  - `companyId`: UUID (we also create a second target for the company)
  - (`personId` exists but is unused)

### Tasks
- Create task: `POST /rest/tasks`
  - `title`: string
  - `bodyV2`: `{ "markdown": "..." }`
  - `status`: `TODO` | `IN_PROGRESS` | `DONE` (we always create `TODO`)
  - `dueAt`: ISO datetime or null (from `next_step_date` if stated)
  - `assigneeId`: null
- Link task: `POST /rest/taskTargets` with `taskId` plus `opportunityId` and/or `companyId`
  - NOTE: taskTargets field names are inferred from the noteTargets pattern and are NOT confirmed. Verify first.

### Opportunity stage values (Twenty default, exact)
`NEW`, `SCREENING`, `MEETING`, `PROPOSAL`, `CUSTOMER`

### Decisions
- MEDDPICC storage: **A**. One custom field on Opportunity:
  - API name: `meddpicc`
  - Type: Text
  - Content: compact JSON string of the 8 MEDDPICC fields (`value`, `confidence`; evidence quotes stay in the note only, to keep it short)
  - The note body ALSO contains a human-readable MEDDPICC table, so it is visible in the UI.
  - Why A: `crm-copilot missing` and the MCP tool `list_deals_missing_info` can read gaps with one list call, without parsing notes.
  - The user creates this field by hand in the Twenty UI (Settings, Data model, Opportunities, add field). The agent does NOT create schema via the metadata API.
  - If the field does not exist on the live instance, the adapter skips writing it, logs a warning, and keeps MEDDPICC in the note only (behaves like option C).
- Stage mapping (our stage -> Twenty value):
  - discovery -> `SCREENING`
  - qualified -> `MEETING`
  - evaluation -> `PROPOSAL`
  - negotiation -> `PROPOSAL`
  - `NEW` is never set by crm-copilot (left for deals created by hand).
  - `CUSTOMER` (closed won) is NEVER set automatically. Closing a deal is a human decision. The planner may only move a stage forward, never backward; if the suggested stage is lower than the current one, keep the current stage and mention it in the plan.

### Verification (agent does this at the start of M5, on the server)
Twenty runs locally, so the agent can check everything itself with the key from `.env`. It must not print the key.
1. `GET {prefix}/companies?limit=1` with prefix `/rest`, then `/rest/core` if the first is not 200. Record which works.
2. `GET {prefix}/opportunities?limit=1&depth=0` and confirm field names: `name`, `stage`, `amount`, `closeDate`, `companyId`, and whether `meddpicc` exists.
3. Create one test company `crm-copilot test co`, one opportunity, one note with `bodyV2.markdown`, one noteTarget, one task, one taskTarget. Save each raw response (keys only, values redacted) to `tests/fixtures/twenty/*.json` for respx mocks. Then delete the test records.
4. If ANY field name or path differs from this section, stop and report the difference before writing the adapter.