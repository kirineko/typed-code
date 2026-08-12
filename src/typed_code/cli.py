"""Command-line entry points for the typed-code service process."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="typed-code")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the local HTTP/SSE agent service")
    serve.add_argument(
        "--host",
        default=None,
        help="Bind host (default from config.toml / 127.0.0.1)",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default from config.toml / 8741)",
    )

    smoke = sub.add_parser(
        "smoke",
        help="Opt-in live provider smoke (not used by default tests)",
    )
    smoke.add_argument(
        "target",
        choices=("deepseek", "cliproxy"),
        help="Provider endpoint to probe via Responses API",
    )

    sub.add_parser("version", help="Print version")
    sub.add_parser(
        "export-contracts",
        help="Write OpenAPI and event schema artifacts to contracts/",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        print("typed-code 0.1.0")
        print("commands: serve | version | smoke {deepseek,cliproxy} | export-contracts")
        return 0

    if args.command == "version":
        from typed_code import __version__

        print(__version__)
        return 0

    if args.command == "export-contracts":
        from typed_code.api.export_contracts import main as export_main

        export_main()
        return 0

    if args.command == "smoke":
        from typed_code.smoke.live import run_smoke

        result = run_smoke(args.target)
        status = "ok" if result.ok else "fail"
        print(
            f"smoke provider={result.provider} model={result.model_id} "
            f"status={status} detail={result.detail}"
        )
        return 0 if result.ok else 1

    if args.command == "serve":
        return _serve(host=args.host, port=args.port)

    return 1


def _serve(*, host: str | None, port: int | None) -> int:
    from contextlib import suppress
    from copy import deepcopy

    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    from typed_code.config.errors import ConfigurationError
    from typed_code.config.settings import load_settings
    from typed_code.service.app_state import build_app_state
    from typed_code.service.runtime_identity import DEFAULT_MAX_LOG_BYTES

    async def _run() -> None:
        settings = load_settings()
        bind_host = host or settings.host
        bind_port = port or settings.port
        state = await build_app_state(settings=settings, require_server_token=True)
        owner = state.service_owner
        assert owner is not None
        try:
            from typed_code.api.app import create_app

            app = create_app(state=state)
            log_config = deepcopy(LOGGING_CONFIG)
            log_config["handlers"]["service_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": str(owner.paths.log_path),
                "maxBytes": DEFAULT_MAX_LOG_BYTES,
                "backupCount": 1,
                "encoding": "utf-8",
            }
            for logger_name in ("uvicorn", "uvicorn.access"):
                handlers = log_config["loggers"][logger_name]["handlers"]
                if "service_file" not in handlers:
                    handlers.append("service_file")
            config = uvicorn.Config(
                app,
                host=bind_host,
                port=bind_port,
                log_level="info",
                loop="asyncio",
                log_config=log_config,
            )
            server = uvicorn.Server(config)
            serve_task = asyncio.create_task(server.serve())
            while not server.started and not serve_task.done():
                await asyncio.sleep(0.01)
            if server.started:
                descriptor_host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
                if ":" in descriptor_host and not descriptor_host.startswith("["):
                    descriptor_host = f"[{descriptor_host}]"
                owner.publish_descriptor(f"http://{descriptor_host}:{bind_port}")
            shutdown_task = asyncio.create_task(state.shutdown_requested.wait())
            try:
                done, _pending = await asyncio.wait(
                    {serve_task, shutdown_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_task in done and not serve_task.done():
                    server.should_exit = True
                await serve_task
            finally:
                shutdown_task.cancel()
                with suppress(asyncio.CancelledError):
                    await shutdown_task
        finally:
            await state.aclose()

    try:
        import asyncio

        asyncio.run(_run())
        return 0
    except ConfigurationError as exc:
        print(f"configuration error: {exc.message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
