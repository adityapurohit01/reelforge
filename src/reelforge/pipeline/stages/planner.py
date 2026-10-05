"""Stage 1 Planner for ReelForge.
Generates novelty-aware plans adhering to hard cooldown constraints and bandit priors.
"""
import json
import uuid
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from sqlmodel import Session

from reelforge.db import engine, init_db
from reelforge.diversity.sampler import NoveltySampler
from reelforge.models import Plan

console = Console(highlight=False)


def generate_plan(
    session: Optional[Session] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    seed: Optional[int] = None,
    run_id: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Generate a single novelty-aware plan."""
    sampler = NoveltySampler()
    axis_tuple, relaxations = sampler.sample_plan(session=session, history=history, seed=seed)
    
    plan_run_id = run_id or f"run_{uuid.uuid4().hex[:10]}"
    plan_data = {
        "run_id": plan_run_id,
        "seed": seed if seed is not None else 42,
        "axes": axis_tuple,
        "relaxations": relaxations,
    }

    if persist and session:
        db_plan = Plan(
            run_id=plan_run_id,
            axis_tuple_json=json.dumps(axis_tuple),
            seed=plan_data["seed"],
            relaxations_json=json.dumps(relaxations),
        )
        session.add(db_plan)
        session.commit()
        session.refresh(db_plan)
        plan_data["plan_id"] = db_plan.id

    return plan_data


def run_planner_batch(n: int = 1, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Generate a batch of N plans (e.g. for testing diversity or planning a queue)."""
    init_db()
    plans = []
    accumulated_history: List[Dict[str, Any]] = []

    with Session(engine) as session:
        table = Table(title=f"Generated {n} Marketing Video Plans (Dry Run: {dry_run})")
        table.add_column("#", width=4)
        table.add_column("Vertical", width=22)
        table.add_column("Locale", width=14)
        table.add_column("Scenario", width=20)
        table.add_column("Hook Family", width=18)
        table.add_column("Layout", width=12)
        table.add_column("Palette", width=16)

        for i in range(n):
            seed = 1000 + i * 37
            plan = generate_plan(
                session=None if dry_run else session,
                history=accumulated_history,
                seed=seed,
                persist=not dry_run,
            )
            axes = plan["axes"]
            accumulated_history.insert(0, axes)
            plans.append(plan)

            table.add_row(
                str(i + 1),
                axes.get("vertical_name", axes.get("vertical", "")),
                f"{axes.get('city')}, {axes.get('country')}",
                axes.get("scenario_name", axes.get("scenario", "")),
                axes.get("hook_family", axes.get("hook_style", "")),
                axes.get("layout", ""),
                axes.get("palette", ""),
            )

        console.print(table)
        if dry_run:
            console.print(f"[bold green][OK] Successfully planned {n} diverse videos without persistence.[/bold green]\n")
        else:
            console.print(f"[bold green][OK] Successfully committed {n} plans to database.[/bold green]\n")

    return plans
