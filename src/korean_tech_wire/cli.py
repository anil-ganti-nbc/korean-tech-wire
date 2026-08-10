from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_settings, load_sources
from .discovery import run_collectors
from .storage import Database

ROOT = Path.cwd()

def context(args: argparse.Namespace):
    settings = load_settings(Path(args.config)); database = Database(settings.database_path); database.migrate()
    return settings, database, load_sources(Path(args.sources))

def main() -> None:
    # Windows consoles may otherwise default to a legacy code page and corrupt Korean titles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="korean-tech-wire")
    parser.add_argument("--config", default="config/config.example.yaml"); parser.add_argument("--sources", default="config/sources.yaml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("source").add_argument("action", choices=["list"])
    run = commands.add_parser("run"); run.add_argument("--source")
    latest = commands.add_parser("articles"); latest.add_argument("action", choices=["latest"]); latest.add_argument("--limit", type=int, default=20)
    commands.add_parser("status")
    args = parser.parse_args(); settings, database, sources = context(args)
    if args.command == "source":
        for source in sources: print(f"{source.id:22} {source.status:12} enabled={source.enabled}  {source.collector}  {source.name}")
    elif args.command == "run":
        summary = run_collectors(sources, settings, database, args.source)
        print(f"Run: {'success' if not summary.failed else 'partial failure'}\nSources attempted: {summary.attempted}; succeeded: {summary.succeeded}; failed: {summary.failed}\nReferences discovered: {summary.discovered}; new articles: {summary.new}; existing articles: {summary.existing}")
        for error in summary.errors: print(f"ERROR {error}")
    elif args.command == "articles":
        for row in database.latest_articles(args.limit): print(f"{row['published_at'] or row['discovered_at']} | {row['source_id']} | {row['title_original']}\n  {row['canonical_url']}")
    else:
        for key, value in database.status().items(): print(f"{key}: {value}")

if __name__ == "__main__": main()
