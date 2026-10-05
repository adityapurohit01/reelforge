"""ReelForge CLI built with Typer and Rich."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 stdout/stderr on Windows to prevent cp1252 charmap encoding errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx
import typer
from rich.console import Console
from rich.table import Table

from reelforge.config import load_config
from reelforge.db import init_db

app = typer.Typer(
    name="reelforge",
    help="Autonomous marketing-video pipeline for AI voice receptionist company",
    no_args_is_help=True,
)
console = Console(highlight=False)


@app.command()
def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose diagnostics"),
) -> None:
    """Verify toolchain health, models, dependencies, and external configurations."""
    console.print("\n[bold cyan][*] Running ReelForge Doctor Toolchain Diagnostics...[/bold cyan]\n")
    table = Table(title="ReelForge System Health", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="dim", width=22)
    table.add_column("Status", width=12)
    table.add_column("Details")

    config = load_config()
    all_ok = True

    # 1. Python & Core packages
    try:
        import sqlmodel
        import soundfile
        import pyloudnorm
        import pydub
        table.add_row("Python Environment", "[green]PASSED[/green]", f"Python {sys.version.split()[0]} with core packages")
    except Exception as e:
        table.add_row("Python Environment", "[red]FAILED[/red]", str(e))
        all_ok = False

    # 2. Node.js & Remotion
    node_path = shutil.which("node")
    if node_path:
        try:
            res = subprocess.run([node_path, "--version"], capture_output=True, text=True, check=True)
            table.add_row("Node.js", "[green]PASSED[/green]", f"{res.stdout.strip()} ({node_path})")
        except Exception as e:
            table.add_row("Node.js", "[red]FAILED[/red]", f"Execution failed: {e}")
            all_ok = False
    else:
        table.add_row("Node.js", "[red]FAILED[/red]", "Node.exe not found on PATH")
        all_ok = False

    # 3. FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else "Available"
            table.add_row("FFmpeg", "[green]PASSED[/green]", first_line[:50])
        except Exception as e:
            table.add_row("FFmpeg", "[red]FAILED[/red]", f"Execution failed: {e}")
            all_ok = False
    else:
        table.add_row("FFmpeg", "[red]FAILED[/red]", "ffmpeg not found on PATH")
        all_ok = False

    # 4. Ollama Server & Models
    ollama_host = config.settings.ollama_host
    try:
        resp = httpx.get(f"{ollama_host}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            models_data = resp.json().get("models", [])
            model_names = [m.get("name") for m in models_data]
            required_llm = config.models.llm_model
            fallback_llm = config.models.llm_fallback
            embed_model = config.models.embedding_model

            llm_present = any(required_llm in m for m in model_names) or any(fallback_llm in m for m in model_names)
            embed_present = any(embed_model in m for m in model_names)

            details = f"Server online. Models: {', '.join(model_names[:4])}"
            if llm_present and embed_present:
                table.add_row("Ollama & Models", "[green]PASSED[/green]", details)
            else:
                missing = []
                if not llm_present:
                    missing.append(f"LLM ({required_llm} or {fallback_llm})")
                if not embed_present:
                    missing.append(f"Embeddings ({embed_model})")
                table.add_row("Ollama & Models", "[yellow]WARNING[/yellow]", f"Missing models: {', '.join(missing)}")
        else:
            table.add_row("Ollama & Models", "[red]FAILED[/red]", f"Status {resp.status_code}")
            all_ok = False
    except Exception as e:
        table.add_row("Ollama & Models", "[red]FAILED[/red]", f"Cannot connect to {ollama_host}: {e}")
        all_ok = False

    # 5. Database
    try:
        init_db()
        table.add_row("SQLite DB", "[green]PASSED[/green]", "reelforge.db initialized with schema")
    except Exception as e:
        table.add_row("SQLite DB", "[red]FAILED[/red]", f"DB init error: {e}")
        all_ok = False

    # 6. Telegram Bot Config
    tg_token = config.settings.telegram_bot_token
    if tg_token:
        try:
            tg_resp = httpx.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=4.0)
            if tg_resp.status_code == 200:
                bot_info = tg_resp.json().get("result", {})
                table.add_row("Telegram Bot", "[green]PASSED[/green]", f"@{bot_info.get('username')}")
            else:
                table.add_row("Telegram Bot", "[yellow]WARNING[/yellow]", f"Invalid token (HTTP {tg_resp.status_code})")
        except Exception as e:
            table.add_row("Telegram Bot", "[yellow]WARNING[/yellow]", f"Telegram check error: {e}")
    else:
        table.add_row("Telegram Bot", "[dim]UNCONFIGURED[/dim]", "TELEGRAM_BOT_TOKEN empty in .env (Required for Phase 4)")

    # 7. Cloudflare R2 / Storage
    if config.storage.backend == "r2":
        if config.settings.r2_access_key_id and config.settings.r2_secret_access_key:
            table.add_row("Storage (R2)", "[green]CONFIGURED[/green]", f"Bucket: {config.settings.r2_bucket}")
        else:
            table.add_row("Storage (R2)", "[yellow]WARNING[/yellow]", "R2 credentials missing")
    else:
        table.add_row("Storage", "[green]PASSED[/green]", "Local storage mode active")

    # 8. Instagram Graph API
    if config.settings.ig_access_token and config.settings.ig_user_id:
        table.add_row("Instagram API", "[green]CONFIGURED[/green]", f"User ID: {config.settings.ig_user_id}")
    else:
        table.add_row("Instagram API", "[dim]UNCONFIGURED[/dim]", "Credentials empty in .env (Required for live Phase 5)")

    console.print(table)
    if all_ok:
        console.print("[bold green][OK] Toolchain and environment ready![/bold green]\n")
    else:
        console.print("[bold red][FAIL] Toolchain has issues. Review rows marked FAILED.[/bold red]\n")
        raise typer.Exit(code=1)


@app.command()
def plan(
    n: int = typer.Option(1, "--n", help="Number of plans to generate"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run without persisting"),
) -> None:
    """Generate novelty-aware plans for upcoming marketing videos."""
    from reelforge.pipeline.stages.planner import run_planner_batch
    run_planner_batch(n=n, dry_run=dry_run)


@app.command(name="run")
def run_command_cmd(
    n: int = typer.Option(1, "--n", help="Number of videos to generate"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Simulate publishing step"),
    preview: bool = typer.Option(False, "--preview", help="Render 5-second fast preview"),
    force: bool = typer.Option(False, "--force", help="Force overwrite of stages"),
) -> None:
    """Execute end-to-end pipeline for N videos, stopping at founder approval."""
    from reelforge.pipeline.state_machine import run_pipeline

    console.print(f"\n[bold cyan]🚀 ReelForge Pipeline: Generating {n} video(s)... (preview={preview}, dry_run={dry_run})[/bold cyan]\n")
    for i in range(n):
        console.print(f"[bold magenta]▶ Processing Video {i + 1}/{n}...[/bold magenta]")
        res = run_pipeline(dry_run=dry_run, preview=preview, force=force, stop_at_approval=True)
        console.print(f"[green]✔ Video {i + 1} generated successfully: [bold]{res['business']}[/bold] ({res['vertical']} in {res['city']})[/green]")
        console.print(f"  • Video Path: [dim]{res['video_path']}[/dim]")
        console.print(f"  • State: [bold yellow]{res['state']}[/bold yellow] (Wall Clock: {res['total_wall_clock_seconds']}s)\n")


@app.command()
def generate(
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Specific run ID to generate"),
    force: bool = typer.Option(False, "--force", help="Force overwrite of existing run"),
) -> None:
    """Execute pipeline generation from planning through rendering."""
    from reelforge.pipeline.state_machine import run_pipeline
    res = run_pipeline(run_id=run_id, force=force, preview=True)
    console.print(f"[green]Generation completed for run {res['run_id']}[/green]")


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Dry run mode"),
) -> None:
    """Resume a previous pipeline run from its last completed stage."""
    from reelforge.pipeline.state_machine import resume_run
    console.print(f"[bold cyan]Resuming run {run_id}...[/bold cyan]")
    res = resume_run(run_id=run_id, dry_run=dry_run)
    console.print(f"[green]Run {run_id} resumed successfully! State: {res['state']}[/green]")


@app.command()
def approve(
    run_id: str = typer.Argument(..., help="Run ID to approve"),
    decision: str = typer.Option("APPROVE", "--decision", "-d", help="APPROVE, REJECT, REGENERATE"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="Reason for rejection or note"),
) -> None:
    """Manually approve or reject a video without Telegram."""
    from datetime import datetime, timezone
    from sqlmodel import Session, select
    from reelforge.db import get_engine
    from reelforge.models import Approval, Video

    engine = get_engine()
    with Session(engine) as session:
        v = session.exec(select(Video).where(Video.run_id == run_id)).first()
        if not v:
            console.print(f"[red]No video found for run_id {run_id}[/red]")
            raise typer.Exit(code=1)

        app_rec = Approval(
            video_id=v.id,
            decision=decision.lower(),
            decided_by="cli_founder",
            decided_at=datetime.now(timezone.utc),
            note=reason or "",
        )
        session.add(app_rec)
        v.state = "APPROVED" if decision.lower() == "approve" else "REJECTED"
        session.commit()
        console.print(f"[green]Approval recorded: {decision} for run {run_id} (Video #{v.id})[/green]")


@app.command()
def publish(
    run_id: str = typer.Argument(..., help="Run ID to publish"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run publish check"),
) -> None:
    """Publish an approved video to Instagram Reels."""
    from sqlmodel import Session, select
    from reelforge.db import get_engine
    from reelforge.models import Video
    from reelforge.pipeline.stages.upload import run_upload_stage
    from reelforge.pipeline.stages.publish import run_publish_stage

    engine = get_engine()
    with Session(engine) as session:
        v = session.exec(select(Video).where(Video.run_id == run_id)).first()
        if not v or not v.video_path:
            console.print(f"[red]Video not found or not rendered for run {run_id}[/red]")
            raise typer.Exit(code=1)

        console.print(f"[bold cyan]Uploading media for {run_id}...[/bold cyan]")
        upload_res = run_upload_stage(Path(v.video_path), Path(v.cover_path) if v.cover_path else None)

        console.print(f"[bold cyan]Publishing to Instagram Reels (dry_run={dry_run})...[/bold cyan]")
        pub_res = run_publish_stage(
            video_id=v.id,
            video_url=upload_res["video_url"],
            caption=v.caption or "Automated Front Desk by Vocalis AI",
            cover_url=upload_res.get("cover_url"),
            session=session,
            dry_run=dry_run,
        )
        console.print(f"[bold green]✔ Published successfully![/bold green] Permalink: {pub_res.get('permalink')}")


@app.command()
def metrics(
    video_id: Optional[int] = typer.Option(None, "--video-id", help="Specific video ID to refresh"),
) -> None:
    """Fetch updated video metrics from Instagram Insights and update bandit."""
    from sqlmodel import Session, select
    from reelforge.db import get_engine
    from reelforge.models import Video, PublishLog
    from reelforge.analytics.insights import InsightsCollector

    collector = InsightsCollector()
    engine = get_engine()
    with Session(engine) as session:
        if video_id:
            videos = session.exec(select(Video).where(Video.id == video_id)).all()
        else:
            videos = session.exec(select(Video).where(Video.state == "PUBLISHED")).all()

        if not videos:
            console.print("[yellow]No published videos found to collect metrics for.[/yellow]")
            return

        for vid in videos:
            try:
                res = collector.process_video_metrics(session, vid.id)
                console.print(f"[green]Updated metrics for Video #{vid.id}: {res['metrics']}[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not fetch metrics for Video #{vid.id}: {e}[/yellow]")


@app.command()
def report(
    report_type: str = typer.Argument("diversity", help="Report type: diversity or performance"),
    last: int = typer.Option(30, "--last", help="Number of past videos to analyze"),
) -> None:
    """Display analytics reports on pipeline diversity and video performance."""
    from sqlmodel import Session
    from reelforge.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        if report_type == "diversity":
            from reelforge.analytics.report import generate_diversity_report
            rep = generate_diversity_report(session, last_n=last)
            console.print(rep)
        elif report_type == "performance":
            from reelforge.analytics.report import generate_performance_report
            rep = generate_performance_report(session)
            console.print(rep)
        else:
            console.print(f"[red]Unknown report type: {report_type}[/red]")


@app.command()
def demo(
    business_json: Path = typer.Option(..., "--business-json", "-b", help="JSON file containing prospect details"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Custom output MP4 path"),
) -> None:
    """Prospect demo mode: Render a personalized demo for a single business (no publish)."""
    from reelforge.pipeline.stages.profile import BusinessProfile
    from reelforge.pipeline.state_machine import ReelForgeStateMachine

    if not business_json.exists():
        console.print(f"[red]File not found: {business_json}[/red]")
        raise typer.Exit(code=1)

    with open(business_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = BusinessProfile.model_validate(data)
    console.print(f"[bold cyan]Rendering prospect demo for: {profile.name} ({profile.vertical})...[/bold cyan]")
    sm = ReelForgeStateMachine()
    # Execute personalized demo run
    r_id = f"demo_{uuid.uuid4().hex[:8]}"
    manifest = sm.run_pipeline(run_id=r_id, dry_run=True, preview=False, stop_at_approval=True)
    console.print(f"[bold green]✔ Prospect demo rendered successfully![/bold green] Path: {manifest['video_path']}")


if __name__ == "__main__":
    app()

