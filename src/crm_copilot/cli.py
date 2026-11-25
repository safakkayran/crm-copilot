"""CLI module for crm-copilot."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from crm_copilot.apply import apply_plan  # noqa: TC001
from crm_copilot.config import settings  # noqa: TC001
from crm_copilot.crm.fake import FakeAdapter  # noqa: TC001
from crm_copilot.crm.twenty import TwentyAdapter  # noqa: TC001
from crm_copilot.extract import extract_insights  # noqa: TC001
from crm_copilot.llm import complete_json  # noqa: TC001
from crm_copilot.mcp_server import main as mcp_main  # noqa: TC001
from crm_copilot.models import EmailDraft, UpdatePlan  # noqa: TC001
from crm_copilot.planner import plan_updates  # noqa: TC001


def _get_adapter() -> FakeAdapter | TwentyAdapter:
    """Get the appropriate CRM adapter based on configuration."""
    if settings.TWENTY_API_KEY:
        return TwentyAdapter()
    return FakeAdapter()

app = typer.Typer(
    name="crm-copilot",
    help="Turn sales call transcripts into clean CRM updates.",
    no_args_is_help=True,
)

console = Console()


def _print_plan(plan: UpdatePlan) -> None:
    """Print a rich table of the proposed plan."""
    console.print(f"\n[bold]Plan for: {plan.company_name}[/bold]\n")

    # Opportunity fields
    if plan.opportunity_fields:
        table = Table(title="Opportunity Fields")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        for k, v in plan.opportunity_fields.items():
            if k == "meddpicc":
                table.add_row(k, f"<JSON: {len(str(v))} chars>")
            else:
                table.add_row(k, str(v))
        console.print(table)

    # Note
    if plan.note_markdown:
        console.print("\n[bold]Note:[/bold]")
        max_len = 500
        note_text = plan.note_markdown[:max_len]
        if len(plan.note_markdown) > max_len:
            note_text += "..."
        console.print(note_text)

    # Tasks
    if plan.tasks:
        table = Table(title="Tasks")
        table.add_column("Title", style="cyan")
        table.add_column("Due", style="yellow")
        for task in plan.tasks:
            table.add_row(task.title, task.due_at or "—")
        console.print(table)

    # Follow-up email
    if plan.followup_email.subject or plan.followup_email.body:
        console.print("\n[bold]Follow-up Email:[/bold]")
        console.print(f"Subject: {plan.followup_email.subject}")
        console.print(f"Body: {plan.followup_email.body}")

    # Missing fields
    if plan.missing_fields:
        console.print("\n[bold]Missing Fields (ask next call):[/bold]")
        for i, field in enumerate(plan.missing_fields, 1):
            console.print(f"  {i}. {field}")

    # Stage
    console.print(f"\n[bold]Suggested Stage:[/bold] {plan.stage.stage} ({plan.stage.reason})")


@app.command()
def process(
    transcript_file: Annotated[
        Path, typer.Argument(help="Path to transcript .txt file")
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Use fake adapter, don't write to CRM")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Auto-apply without confirmation")
    ] = False,
    out: Annotated[
        Path | None, typer.Option("--out", help="Write plan JSON to file")
    ] = None,
) -> None:
    """Process a transcript: extract insights, plan updates, optionally apply to CRM."""
    # Read transcript
    transcript = transcript_file.read_text(encoding="utf-8")

    # Extract insights
    console.print("[cyan]Extracting insights...[/cyan]")
    insights = extract_insights(transcript)

    # Plan updates
    console.print("[cyan]Planning updates...[/cyan]")
    plan = plan_updates(insights)

    # Print plan
    _print_plan(plan)

    # Write plan to file if requested
    if out:
        out.write_text(plan.model_dump_json(indent=2))
        console.print(f"\n[green]Plan written to {out}[/green]")

    # Determine if we should apply
    auto_apply = settings.AUTO_APPLY or yes
    if dry_run:
        console.print("\n[yellow]Dry run mode - not applying to CRM[/yellow]")
        return

    if not auto_apply:
        confirm = typer.confirm("\nApply to CRM?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Apply to CRM (will use FakeAdapter if Twenty not configured)
    console.print("[cyan]Applying to CRM...[/cyan]")
    adapter = _get_adapter()
    result = apply_plan(plan, adapter)

    console.print("[green]Applied successfully![/green]")
    console.print(f"  Company ID: {result.company_id}")
    console.print(f"  Opportunity ID: {result.opportunity_id}")
    console.print(f"  Note ID: {result.note_id}")
    console.print(f"  Task IDs: {result.task_ids}")


@app.command()
def missing() -> None:
    """List open opportunities with MEDDPICC gaps."""
    adapter = _get_adapter()
    opportunities = adapter.list_opportunities()

    if not opportunities:
        console.print("[yellow]No opportunities found[/yellow]")
        return

    table = Table(title="Open Opportunities with MEDDPICC Gaps")
    table.add_column("Company", style="cyan")
    table.add_column("Opportunity", style="green")
    table.add_column("Stage", style="yellow")
    table.add_column("Missing Fields", style="red")

    for opp in opportunities:
        meddpicc = opp.get("meddpicc", {})
        if isinstance(meddpicc, str):
            try:
                meddpicc = json.loads(meddpicc)
            except json.JSONDecodeError:
                meddpicc = {}

        missing = []
        for field_name, field_data in meddpicc.items():
            if isinstance(field_data, dict) and field_data.get("value") is None:
                missing.append(field_name)

        if missing:
            table.add_row(
                opp.get("company_name", "Unknown"),
                opp.get("name", "Unknown"),
                opp.get("stage", "Unknown"),
                ", ".join(missing),
            )

    console.print(table)


@app.command()
def doctor() -> None:
    """Check LLM endpoint reachable, Twenty reachable and key valid."""
    console.print("[cyan]Checking LLM endpoint...[/cyan]")
    try:
        # Simple LLM call
        complete_json(
            system="Reply with JSON",
            user='Say {"status": "ok"}',
            schema=EmailDraft,
        )
        console.print(f"  LLM: [green]OK[/green] (model: {settings.LLM_MODEL})")
    except Exception as e:
        console.print(f"  LLM: [red]FAIL[/red] - {e}")

    console.print("[cyan]Checking Twenty CRM...[/cyan]")
    if settings.TWENTY_API_KEY:
        try:
            adapter = TwentyAdapter()
            if adapter.health_check():
                console.print(f"  Twenty: [green]OK[/green] (base: {settings.TWENTY_BASE_URL})")
            else:
                console.print("  Twenty: [red]FAIL[/red] - health check failed")
        except Exception as e:
            console.print(f"  Twenty: [red]FAIL[/red] - {e}")
    else:
        console.print("  Twenty: [yellow]Not configured (using FakeAdapter)[/yellow]")


@app.command()
def mcp() -> None:
    """Run MCP server (stdio)."""
    mcp_main()


if __name__ == "__main__":
    app()