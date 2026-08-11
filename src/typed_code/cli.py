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
    import uvicorn

    from typed_code.config.errors import ConfigurationError
    from typed_code.config.settings import load_settings
    from typed_code.service.app_state import build_app_state

    async def _run() -> None:
        settings = load_settings()
        bind_host = host or settings.host
        bind_port = port or settings.port
        state = await build_app_state(settings=settings, require_server_token=True)
        from typed_code.api.app import create_app

        app = create_app(state=state)
        config = uvicorn.Config(
            app,
            host=bind_host,
            port=bind_port,
            log_level="info",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        await server.serve()

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
