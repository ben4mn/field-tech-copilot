from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvicorn

from fieldtech.api.app import STATIC_DIR, create_app
from fieldtech.config import Settings
from fieldtech.core.database import Database
from fieldtech.core.service import DiagnosticService
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore
from fieldtech.providers import build_provider
from fieldtech.providers.mock import MockDiagnosticModel

APP_HOST = "127.0.0.1"
APP_PORT = 8765
MODEL_ALIAS = "fieldtech-lite"
MODEL_FILENAME = "Qwen3-1.7B-Q8_0.gguf"
KNOWLEDGE_PACK_VERSION = "2"
MUTEX_NAME = "FieldTechCopilotDesktop-8D4D48B8-9518-4BA1-A44B-2243D7D97E63"
VC_RUNTIME_FILENAMES = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")


@dataclass(frozen=True, slots=True)
class BundlePaths:
    root: Path
    server: Path
    model: Path
    knowledge: Path
    manifest: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Field Tech Copilot desktop launcher")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--model-smoke", action="store_true")
    parser.add_argument("--data-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--bundle-root", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def install_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_paths(root: Path) -> BundlePaths:
    return BundlePaths(
        root=root,
        server=root / "runtime" / "llama-server.exe",
        model=root / "models" / MODEL_FILENAME,
        knowledge=root / "knowledge",
        manifest=root / "bundle-manifest.json",
    )


def user_data_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "FieldTechCopilot"
    return Path.home() / ".local" / "share" / "FieldTechCopilot"


def configure_logging(data_root: Path) -> None:
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_dir / "launcher.log", encoding="utf-8")],
        force=True,
    )


def show_error(message: str) -> None:
    logging.error(message)
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            message,
            "Field Tech Copilot",
            0x10,
        )
    else:
        print(f"Field Tech Copilot: {message}", file=sys.stderr)


def validate_bundle(paths: BundlePaths) -> dict[str, object]:
    required_paths = (
        paths.server,
        paths.model,
        paths.knowledge,
        paths.manifest,
        *(paths.root / "runtime" / name for name in VC_RUNTIME_FILENAMES),
    )
    missing = [
        str(path) for path in required_paths if not path.exists()
    ]
    if missing:
        raise RuntimeError("The offline bundle is incomplete. Missing: " + ", ".join(missing))
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if str(manifest.get("knowledgePackVersion", "")) != KNOWLEDGE_PACK_VERSION:
        raise RuntimeError(
            "The bundled knowledge-pack version does not match this application"
        )
    model = manifest.get("model", {})
    expected_size = int(model.get("size", 0)) if isinstance(model, dict) else 0
    if expected_size <= 0 or paths.model.stat().st_size != expected_size:
        raise RuntimeError("The bundled model size does not match its release manifest")
    if not find_cards(paths.knowledge):
        raise RuntimeError("The bundled starter knowledge pack is empty")
    return manifest


def seed_knowledge(database: Database, knowledge_root: Path) -> int:
    marker = database.get_meta("starter_knowledge_pack")
    if marker == KNOWLEDGE_PACK_VERSION:
        return 0
    count = KnowledgeStore(database).ingest(find_cards(knowledge_root))
    database.set_meta("starter_knowledge_pack", KNOWLEDGE_PACK_VERSION)
    return count


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.35)
        return client.connect_ex((APP_HOST, port)) == 0


def available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((APP_HOST, 0))
        return int(server.getsockname()[1])


def existing_app_is_ready() -> bool:
    try:
        response = httpx.get(f"http://{APP_HOST}:{APP_PORT}/", timeout=1.0)
        return response.status_code == 200 and "Field Tech Copilot" in response.text
    except httpx.HTTPError:
        return False


def wait_for_url(url: str, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.35)
    return False


def acquire_mutex() -> tuple[int | None, bool]:
    if os.name != "nt":
        return None, False
    handle = ctypes.windll.kernel32.CreateMutexW(  # type: ignore[attr-defined]
        None, False, MUTEX_NAME
    )
    if not handle:
        raise OSError("Windows could not create the single-instance lock")
    already_running = ctypes.windll.kernel32.GetLastError() == 183  # type: ignore[attr-defined]
    return int(handle), already_running


def release_mutex(handle: int | None) -> None:
    if handle is not None and os.name == "nt":
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]


def start_model(
    paths: BundlePaths,
    data_root: Path,
    model_port: int,
    api_key: str,
) -> tuple[subprocess.Popen[bytes], object]:
    log_path = data_root / "logs" / "llama-server.log"
    log_stream = log_path.open("ab")
    command = [
        str(paths.server),
        "--model",
        str(paths.model),
        "--alias",
        MODEL_ALIAS,
        "--host",
        APP_HOST,
        "--port",
        str(model_port),
        "--api-key",
        api_key,
        "--ctx-size",
        "8192",
        "--parallel",
        "1",
        "--threads",
        str(max(2, (os.cpu_count() or 4) - 1)),
        "--jinja",
        "--reasoning",
        "off",
        "--no-webui",
    ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=paths.root,
        stdin=subprocess.DEVNULL,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )
    logging.info("Started bundled model runtime with pid %s", process.pid)
    return process, log_stream


def stop_model(process: subprocess.Popen[bytes] | None, log_stream: object | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=4)
    if log_stream is not None and hasattr(log_stream, "close"):
        log_stream.close()  # type: ignore[union-attr]


def desktop_settings(data_root: Path, model_port: int, api_key: str) -> Settings:
    return Settings(
        host=APP_HOST,
        port=APP_PORT,
        data_dir=data_root / "data",
        model_provider="llama_cpp",
        model_base_url=f"http://{APP_HOST}:{model_port}/v1",
        model_name=MODEL_ALIAS,
        model_api_key=api_key,
        model_timeout_seconds=240.0,
        model_reasoning_effort="medium",
        allow_remote=False,
    )


def run_self_test(paths: BundlePaths) -> None:
    validate_bundle(paths)
    if not (STATIC_DIR / "index.html").is_file():
        raise RuntimeError("The packaged browser interface is missing")
    with tempfile.TemporaryDirectory(prefix="fieldtech-selftest-") as temporary:
        database = Database(Path(temporary) / "data" / "fieldtech.db")
        database.initialize()
        seed_knowledge(database, paths.knowledge)
        service = DiagnosticService(
            database=database,
            knowledge=KnowledgeStore(database),
            model=MockDiagnosticModel(),
        )
        case = service.create_case("Synthetic offline bundle self-test")
        if not case.assessment or database.count_knowledge_cards() < 1:
            raise RuntimeError("The packaged database workflow failed its self-test")


def run_model_smoke(paths: BundlePaths, data_root: Path) -> None:
    process: subprocess.Popen[bytes] | None = None
    log_stream: object | None = None
    try:
        model_port = available_loopback_port()
        api_key = secrets.token_urlsafe(32)
        process, log_stream = start_model(paths, data_root, model_port, api_key)
        settings = desktop_settings(data_root, model_port, api_key)
        provider = build_provider(settings)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            ready, _ = provider.health()
            if ready:
                break
            if process.poll() is not None:
                raise RuntimeError("The bundled model runtime exited during startup")
            time.sleep(0.75)
        else:
            raise RuntimeError("The bundled model did not become ready within three minutes")
        database = Database(settings.database_path)
        database.initialize()
        seed_knowledge(database, paths.knowledge)
        case = DiagnosticService(
            database=database,
            knowledge=KnowledgeStore(database),
            model=provider,
        ).create_case("Synthetic smoke test: Wi-Fi disconnects but Ethernet remains stable")
        if not case.assessment:
            detail = case.last_error or "no validation detail was recorded"
            raise RuntimeError(
                f"The bundled model did not return a validated assessment: {detail}"
            )
    finally:
        stop_model(process, log_stream)


def open_browser_when_ready(url: str) -> None:
    if wait_for_url(url, timeout_seconds=30):
        webbrowser.open(url)


def run_desktop(paths: BundlePaths, data_root: Path, no_browser: bool) -> None:
    validate_bundle(paths)
    if existing_app_is_ready():
        if not no_browser:
            webbrowser.open(f"http://{APP_HOST}:{APP_PORT}")
        return
    if port_is_open(APP_PORT):
        raise RuntimeError(f"Local port {APP_PORT} is already used by another application")

    model_port = available_loopback_port()
    api_key = secrets.token_urlsafe(32)
    settings = desktop_settings(data_root, model_port, api_key)
    database = Database(settings.database_path)
    database.initialize()
    seed_knowledge(database, paths.knowledge)

    process: subprocess.Popen[bytes] | None = None
    log_stream: object | None = None
    try:
        process, log_stream = start_model(paths, data_root, model_port, api_key)

        provider = build_provider(settings)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            ready, _ = provider.health()
            if ready:
                break
            if process is not None and process.poll() is not None:
                raise RuntimeError(
                    "The bundled model runtime stopped. See logs\\llama-server.log for details."
                )
            time.sleep(0.75)
        else:
            raise RuntimeError(
                "The bundled model did not start within three minutes. "
                "See logs\\llama-server.log for details."
            )

        server_holder: dict[str, uvicorn.Server] = {}

        def request_shutdown() -> None:
            server_holder["server"].should_exit = True

        app = create_app(settings, shutdown_callback=request_shutdown)
        config = uvicorn.Config(
            app,
            host=APP_HOST,
            port=APP_PORT,
            log_level="warning",
            access_log=False,
            loop="asyncio",
            http="h11",
        )
        server = uvicorn.Server(config)
        server_holder["server"] = server
        if not no_browser:
            threading.Thread(
                target=open_browser_when_ready,
                args=(f"http://{APP_HOST}:{APP_PORT}",),
                daemon=True,
            ).start()
        server.run()
    finally:
        stop_model(process, log_stream)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_root = user_data_root(args.data_dir)
    configure_logging(data_root)
    paths = bundle_paths(install_root(args.bundle_root))
    mutex_handle: int | None = None
    try:
        mutex_handle, already_running = acquire_mutex()
        if already_running:
            if not args.no_browser:
                webbrowser.open(f"http://{APP_HOST}:{APP_PORT}")
            return 0
        if args.self_test:
            run_self_test(paths)
            if args.model_smoke:
                run_model_smoke(paths, data_root)
            return 0
        run_desktop(paths, data_root, no_browser=args.no_browser)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        if args.self_test:
            logging.exception("Self-test failed: %s", exc)
            if sys.stderr is not None:
                print(f"Self-test failed: {exc}", file=sys.stderr)
        else:
            show_error(str(exc))
        return 2
    finally:
        release_mutex(mutex_handle)


if __name__ == "__main__":
    raise SystemExit(main())
