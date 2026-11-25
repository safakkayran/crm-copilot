# Example Transcripts

This directory contains example sales call transcripts for testing and evaluating the crm-copilot pipeline.

## Transcripts

| File | Stage | Description |
|------|-------|-------------|
| `transcript_1_discovery.txt` | Discovery | Initial discovery call with SaaS buyer - pain points, budget, decision makers |
| `transcript_2_negotiation.txt` | Negotiation | Pricing negotiation with VP Engineering and prospect |
| `transcript_3_evaluation.txt` | Evaluation | Technical deep dive with lead engineer |

## Running Evaluation

```bash
# Requires LiteLLM proxy running with API keys configured
cd examples
python3 run_eval.py
```

Results are saved to `eval_results.json`.

## Expected MEDDPICC Extraction

### Transcript 1 (Discovery)
- **Metrics**: $120k ARR lost, 20 hrs/week engineering time
- **Economic Buyer**: VP Engineering (Mike), CTO (Lisa) for >$50k
- **Decision Criteria**: Reliability, ease of use, integrations (PostgreSQL, Slack, Salesforce), pricing transparency
- **Decision Process**: POC → security review → procurement
- **Paper Process**: Not discussed
- **Identify Pain**: Webhook failures, no visibility, lost client
- **Champion**: Sarah (advocating for solution)
- **Competition**: Tray.io (too complex), Workato (opaque pricing)

### Transcript 2 (Negotiation)
- **Metrics**: Budget $75k max
- **Economic Buyer**: CTO (Lisa) needs to approve
- **Decision Criteria**: SSO, audit logs, custom roles, SLA
- **Decision Process**: Security review (2 weeks), then procurement
- **Paper Process**: MSA, DPA, SOC2 review
- **Identify Pain**: Rate limits on growth tier
- **Champion**: Sarah and Mike (both supportive)
- **Competition**: Not discussed

### Transcript 3 (Evaluation)
- **Metrics**: Not explicitly stated
- **Economic Buyer**: Not discussed
- **Decision Criteria**: Data residency (EU), encryption, PII handling, CMK, read replica support
- **Decision Process**: Security questionnaire (SIG Lite) → implementation sprint
- **Paper Process**: DPA, security questionnaire
- **Identify Pain**: Migration from Zapier, team stretched
- **Champion**: David (technical lead)
- **Competition**: Not discussed

## Notes

- The LiteLLM proxy must be running with valid API keys for NVIDIA NIM, Groq, or OpenRouter models
- Configure `LLM_MODEL` in `.env` (e.g., `nim-laguna`, `groq-qwen`, `gemini-flash`)
- Without API keys, the evaluation will fail with connection errors