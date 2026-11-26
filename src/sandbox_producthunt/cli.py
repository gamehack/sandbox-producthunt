"""One-shot sandbox entrypoint; no scheduler or channel publishing."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from qjai_producthunt.cli import _require_notion_config, _require_production_config
from qjai_producthunt.notion_sync import check_period_ready, sync_article
from qjai_producthunt.pipeline import DailyPipeline
from qjai_producthunt.recovery import read_saved_article
from qjai_producthunt.research import WebsiteEvidenceCollector
from qjai_producthunt.runtimes import AgentTask, OpenAIAgentRuntime
from qjai_producthunt.settings import Settings
from qjai_producthunt.sources import ProductHuntSource
from qjai_producthunt.storage import StepStore

from .locking import exclusive_run_lock
from .runtime import DSHRuntime, DSHError


class Probe(BaseModel):
    ok: bool


def snapshot_day(value: str | None = None) -> date:
    if value is None:
        return datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=1)
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError("Date must be canonical YYYY-MM-DD")
    return day


def ready(day: date) -> bool:
    return check_period_ready(
        source_key=f"producthunt:{day.isoformat()}",
        unique_prefix=f"{day.isoformat()}｜",
    )


def backend_settings(settings: Settings, backend: str) -> Settings:
    if backend == "dsh":
        return settings
    # Keep model outputs/checkpoints separate when comparing the original runtime.
    db = settings.database_path
    return replace(settings, database_path=db.with_name(db.stem + ".openai" + db.suffix),
                   output_dir=settings.output_dir / "openai")


def make_runtime(root: Path, settings: Settings, backend: str):
    if backend == "dsh":
        return DSHRuntime(root)
    return OpenAIAgentRuntime(settings.omni_base_url, settings.omni_api_key, settings.omni_model)


async def execute(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    settings = Settings.load(Path(args.env).resolve() if args.env else root / ".env")
    backend = args.runtime or os.getenv("SANDBOX_RUNTIME", "dsh")
    if backend not in {"dsh", "openai"}:
        raise ValueError("SANDBOX_RUNTIME must be dsh or openai")
    lock_path = settings.database_path.parent / "producthunt.lock"
    settings = backend_settings(settings, backend)

    if args.command == "doctor":
        runtime = make_runtime(root, settings, backend)
        result = await runtime.generate(AgentTask("doctor", 'Return {"ok":true}.', {}), Probe)
        if not result.ok:
            raise RuntimeError("Model probe returned false")
        return {"status": "ok", "runtime": backend}

    day = snapshot_day(args.date)
    _require_notion_config()
    if args.command == "check-ready":
        return {"status": "ready" if ready(day) else "missing", "period": day.isoformat()}

    if settings.source != "producthunt" or not settings.ph_commercial_authorized:
        raise PermissionError("Production requires official Product Hunt commercial authorization")

    with exclusive_run_lock(lock_path):
        if ready(day):
            return {"status": "already_ready", "period": day.isoformat(), "runtime": backend}

        if args.command == "sync-notion":
            saved = read_saved_article(settings.output_dir, day)
            sync_article(source_key=f"producthunt:{day.isoformat()}",
                         title=f"{day.isoformat()}｜{saved['title']}",
                         unique_prefix=f"{day.isoformat()}｜", markdown=saved["markdown"])
        else:
            if not settings.ph_token:
                raise ValueError("PRODUCT_HUNT_TOKEN is required")
            if backend == "openai":
                _require_production_config(settings)
            runtime = make_runtime(root, settings, backend)
            pipeline = DailyPipeline(settings, runtime,
                                     ProductHuntSource(settings.ph_token, commercial_authorized=True),
                                     WebsiteEvidenceCollector(), StepStore(settings.database_path))
            await pipeline.run(day)
        if not ready(day):
            raise RuntimeError("Notion READY verification failed after run")
        return {"status": "notion_ready", "period": day.isoformat(), "runtime": backend}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sandbox-producthunt")
    p.add_argument("--root", default="/data/opt/sandbox-producthunt")
    p.add_argument("--env")
    p.add_argument("--runtime", choices=["dsh", "openai"])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("run").add_argument("--date")
    sub.add_parser("check-ready").add_argument("--date", required=True)
    sub.add_parser("sync-notion").add_argument("--date", required=True)
    return p


def main() -> None:
    os.umask(0o077)
    p = parser()
    try:
        result = asyncio.run(execute(p.parse_args()))
        print(json.dumps(result, ensure_ascii=False))
    except (DSHError, PermissionError) as exc:
        # These are locally generated messages; do not print provider response bodies.
        print(f"sandbox-producthunt: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as exc:
        print(f"sandbox-producthunt failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
