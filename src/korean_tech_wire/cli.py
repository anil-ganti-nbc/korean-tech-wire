from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_settings, load_sources
from .discovery import run_collectors
from .locking import LockUnavailable, RunLock
from .scheduling import DEFAULT_INTERVAL_SECONDS, describe
from .soak import run_soak
from .storage import Database
from .qualification import QualificationProvenance

ROOT = Path.cwd()

def context(args: argparse.Namespace):
    settings = load_settings(Path(args.config)); database = Database(settings.database_path)
    # This is the sole CLI startup boundary allowed to invoke the canonical
    # migration mechanism.  Every command receives a post-check-compatible DB.
    database.migrate(); database.require_compatible()
    return settings, database, load_sources(Path(args.sources))

def main() -> None:
    # Windows consoles may otherwise default to a legacy code page and corrupt Korean titles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="korean-tech-wire")
    parser.add_argument("--config", default="config/config.example.yaml"); parser.add_argument("--sources", default="config/sources.yaml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("source").add_argument("action", choices=["list"])
    run = commands.add_parser("run"); run.add_argument("--source"); run.add_argument("--production", action="store_true")
    health = commands.add_parser("health"); health.add_argument("--source"); health.add_argument("--recent", type=int, default=20)
    soak = commands.add_parser("soak"); soak.add_argument("--cycles", type=int, default=1); soak.add_argument("--interval-seconds", type=int, default=7200); soak.add_argument("--source", action="append", default=[]); soak.add_argument("--if-due", action="store_true")
    state = commands.add_parser("state"); state.add_argument("action", choices=["backup", "checkpoint"]); state.add_argument("--destination")
    latest = commands.add_parser("articles"); latest.add_argument("action", choices=["latest"]); latest.add_argument("--limit", type=int, default=20)
    commands.add_parser("status")
    maintenance = commands.add_parser("maintenance"); maintenance.add_argument("action", choices=["cleanup-samsung-legacy", "quarantine-theelec-legacy"])
    args = parser.parse_args(); settings, database, sources = context(args)
    if args.command == "source":
        for source in sources: print(f"{source.id:22} {source.status:12} enabled={source.enabled}  {source.collector}  {source.name}")
    elif args.command == "run":
        if args.production:
            selected = [source for source in sources if source.enabled and source.status == "PRODUCTION"]
            print(f"Production scope: {len(selected)} source(s)" + (" — " + ", ".join(source.id for source in selected) if selected else " (allowlist is empty)"))
        try:
            with RunLock(settings.database_path.with_name(settings.database_path.name + ".lock")):
                summary = run_collectors(sources, settings, database, args.source, production_only=args.production, provenance=QualificationProvenance.MANUAL)
        except LockUnavailable as error:
            raise SystemExit(str(error))
        print(f"Run: {'success' if not summary.failed else 'partial failure'}\nSources attempted: {summary.attempted}; succeeded: {summary.succeeded}; failed: {summary.failed}\nReferences discovered: {summary.discovered}; accepted: {summary.accepted}; rejected: {summary.rejected}\nNew articles: {summary.new}; existing articles: {summary.existing}; timestamped: {summary.timestamped}; extraction failures: {summary.extraction_failed}")
        for error in summary.errors: print(f"ERROR {error}")
    elif args.command == "articles":
        for row in database.latest_articles(args.limit): print(f"{row['published_at'] or row['discovered_at']} | {row['source_id']} | {row['title_original']}\n  {row['canonical_url']}")
    elif args.command == "maintenance":
        if args.action == "cleanup-samsung-legacy":
            marked, deleted = database.quarantine_legacy_samsung_records()
            print(f"Samsung legacy records marked unverified: {marked}; URL-proven noise removed: {deleted}")
        else:
            marked = database.quarantine_legacy_theelec_records()
            print(f"The Elec broad-index records marked unverified: {marked}")
    elif args.command == "health":
        source_map = {source.id: source for source in sources}
        requested = [args.source] if args.source else list(source_map)
        for summary in database.health_summary(requested, args.recent):
            source = source_map.get(summary["source_id"])
            lifecycle = source.status if source else "UNKNOWN"
            print(f"{summary['source_id']} [{lifecycle}] runs={summary['runs']} success={summary['successes']} source_failures={summary['source_failures']} environment_failures={summary['environment_failures']} consecutive_successes={summary['consecutive_successes']}")
            print(f"  latest refs={summary['latest_references']} accepted={summary['latest_accepted']} rejected={summary['latest_rejected']} timestamped={summary['latest_timestamped']} extraction_failures={summary['latest_extraction_failures']} unexpected_zero={summary['unexpected_zero_events']}")
            print(f"  last_success={summary['last_success'] or '-'} last_failure={summary['last_failure'] or '-'}")
            due_state = database.source_due_state(summary["source_id"])
            print(f"  schedule={describe(due_state, DEFAULT_INTERVAL_SECONDS)}")
            for note in summary["recent_notes"][:3]: print(f"  note: {note}")
    elif args.command == "soak":
        print(f"Soak: cycles={args.cycles}; interval_seconds={args.interval_seconds}; sources={', '.join(args.source) if args.source else 'all enabled'}")
        try:
            with RunLock(settings.database_path.with_name(settings.database_path.name + ".lock")):
                summaries = run_soak(sources, settings, database, cycles=args.cycles, interval_seconds=args.interval_seconds, source_ids=args.source, if_due=args.if_due)
        except KeyboardInterrupt:
            print("Soak interrupted cleanly; completed cycles remain in SQLite health history."); return
        print(f"Soak {'skipped (not due)' if not summaries else 'completed collector runs: ' + str(len(summaries))}")
    elif args.command == "state":
        if args.action == "checkpoint":
            print(json.dumps(database.migration_checkpoint(), ensure_ascii=False, indent=2)); return
        if not args.destination:
            raise SystemExit("state backup requires --destination")
        try:
            with RunLock(settings.database_path.with_name(settings.database_path.name + ".lock")):
                database.backup_to(Path(args.destination))
        except LockUnavailable as error:
            raise SystemExit(str(error))
        print(f"SQLite backup created: {args.destination}")
    else:
        for key, value in database.status().items(): print(f"{key}: {value}")

if __name__ == "__main__": main()
