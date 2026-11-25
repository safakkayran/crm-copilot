#!/usr/bin/env python3
"""Evaluation script for crm-copilot.

Note: Requires LiteLLM proxy with working API keys (NVIDIA NIM, Groq, or OpenRouter).
Set LLM_MODEL in .env or environment to use a specific model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from crm_copilot.apply import apply_plan
from crm_copilot.config import settings
from crm_copilot.crm.fake import FakeAdapter
from crm_copilot.extract import extract_insights
from crm_copilot.planner import plan_updates

EXAMPLES_DIR = Path(__file__).parent


def run_eval() -> dict:
    """Run evaluation on all example transcripts."""
    results = {}

    for transcript_file in sorted(EXAMPLES_DIR.glob("transcript_*.txt")):
        name = transcript_file.stem
        print(f"\n{'='*60}")
        print(f"Evaluating: {name}")
        print(f"{'='*60}")

        transcript = transcript_file.read_text(encoding="utf-8")

        # Extract insights
        print("\n[1/3] Extracting insights...")
        try:
            insights = extract_insights(transcript)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[name] = {"error": str(e)}
            continue

        # Plan updates
        print("[2/3] Planning updates...")
        plan = plan_updates(insights)

        # Apply to fake CRM
        print("[3/3] Applying to CRM...")
        adapter = FakeAdapter()
        result = apply_plan(plan, adapter)

        # Store results
        results[name] = {
            "company_name": plan.company_name,
            "stage": plan.stage.stage,
            "stage_reason": plan.stage.reason,
            "opportunity_fields": plan.opportunity_fields,
            "note_length": len(plan.note_markdown),
            "task_count": len(plan.tasks),
            "followup_subject": plan.followup_email.subject,
            "missing_fields": plan.missing_fields,
            "meddpicc_fields_found": sum(
                1 for v in insights.meddpicc.values() if v.value is not None
            ),
            "result_ids": {
                "company_id": result.company_id,
                "opportunity_id": result.opportunity_id,
                "note_id": result.note_id,
                "task_ids": result.task_ids,
            },
        }

        print(f"\nCompany: {plan.company_name}")
        print(f"Stage: {plan.stage.stage} ({plan.stage.reason})")
        print(f"MEDDPICC fields found: {results[name]['meddpicc_fields_found']}/8")
        print(f"Missing fields: {plan.missing_fields}")
        print(f"Tasks: {len(plan.tasks)}")
        print(f"Follow-up: {plan.followup_email.subject[:50]}...")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, r in results.items():
        if "error" in r:
            print(f"{name}: ERROR - {r['error']}")
        else:
            msg = f"{name}: {r['company_name']} -> {r['stage']} "
            msg += f"({r['meddpicc_fields_found']}/8 MEDDPICC)"
            print(msg)

    return results


if __name__ == "__main__":
    # Check if LLM is configured
    if not settings.LLM_MODEL:
        print("ERROR: LLM_MODEL not configured in settings")
        sys.exit(1)

    results = run_eval()

    # Save results
    output_file = Path(__file__).parent / "eval_results.json"
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {output_file}")