from __future__ import annotations

import argparse
import shutil
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from fieldtech.api.app import create_app
from fieldtech.config import Settings
from fieldtech.core.database import Database
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore
from fieldtech.providers import build_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fieldtech", description="Offline field technician diagnostic copilot"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the loopback-only local application")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--provider", choices=["mock", "ollama"])
    serve.add_argument("--model")
    serve.add_argument("--no-browser", action="store_true")

    knowledge = subparsers.add_parser("knowledge", help="Manage the local knowledge index")
    knowledge_subparsers = knowledge.add_subparsers(dest="knowledge_command", required=True)
    ingest = knowledge_subparsers.add_parser("ingest", help="Index Markdown procedure cards")
    ingest.add_argument("path", type=Path)

    subparsers.add_parser("doctor", help="Check local offline readiness")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "serve":
            run_server(args, settings)
        elif args.command == "knowledge":
            ingest_knowledge(args.path, settings)
        elif args.command == "doctor":
            raise SystemExit(run_doctor(settings))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def run_server(args: argparse.Namespace, settings: Settings) -> None:
    settings = settings.with_overrides(
        host=args.host,
        port=args.port,
        model_provider=args.provider,
        model_name=args.model,
    )
    app = create_app(settings)
    url = f"http://{settings.host}:{settings.port}"
    print(f"Field Tech Copilot: {url}")
    print(f"Data: {settings.database_path.resolve()}")
    print("No commands are executed by the application.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


def ingest_knowledge(path: Path, settings: Settings) -> None:
    if not path.exists():
        raise ValueError(f"Knowledge path does not exist: {path}")
    database = Database(settings.database_path)
    database.initialize()
    cards = find_cards(path)
    count = KnowledgeStore(database).ingest(cards)
    print(f"Indexed {count} procedure card(s) into {settings.database_path.resolve()}")


def run_doctor(settings: Settings) -> int:
    database = Database(settings.database_path)
    database.initialize()
    provider = build_provider(settings)
    model_ready, model_message = provider.health()
    usage = shutil.disk_usage(settings.data_dir.resolve().parent)
    knowledge_count = database.count_knowledge_cards()

    checks = [
        (True, f"Database ready: {settings.database_path.resolve()}"),
        (model_ready, model_message),
        (knowledge_count > 0, f"Knowledge cards indexed: {knowledge_count}"),
        (
            usage.free > 5 * 1024**3,
            f"Free disk space: {usage.free / 1024**3:.1f} GiB",
        ),
        (
            settings.host in {"127.0.0.1", "localhost", "::1"},
            f"Bind address: {settings.host}",
        ),
    ]
    for passed, message in checks:
        print(f"{'PASS' if passed else 'WARN'}  {message}")
    print("MANUAL  Reboot, disable Wi-Fi/Ethernet, and complete one saved-case smoke test")
    return 0 if all(passed for passed, _ in checks) else 1


if __name__ == "__main__":
    main()

