"""Live smoke probes for DeepSeek and CLIProxyAPI Responses endpoints."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent

from typed_code.config.credentials import load_credentials
from typed_code.config.settings import load_settings
from typed_code.protocol.common import ProviderName
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.factories import build_responses_model
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID


@dataclass(frozen=True)
class SmokeResult:
    provider: str
    model_id: str
    ok: bool
    detail: str


async def smoke_deepseek() -> SmokeResult:
    settings = load_settings()
    creds = load_credentials()
    catalog = ModelCatalog(settings=settings, credentials=creds)
    if creds.deepseek_api_key is None:
        return SmokeResult("deepseek", DEEPSEEK_MODEL_ID, False, "missing_credentials")
    try:
        resolved = catalog.resolve(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID)
        model = build_responses_model(
            resolved, api_key=creds.deepseek_api_key.get_secret_value()
        )
        agent = Agent(model, output_type=str, system_prompt="Reply with exactly: ok")
        result = await agent.run("ping")
        text = result.output if isinstance(result.output, str) else str(result.output)
        return SmokeResult("deepseek", DEEPSEEK_MODEL_ID, True, f"output_len={len(text)}")
    except Exception as exc:
        return SmokeResult(
            "deepseek", DEEPSEEK_MODEL_ID, False, type(exc).__name__
        )


async def smoke_cliproxy() -> SmokeResult:
    settings = load_settings()
    creds = load_credentials()
    catalog = ModelCatalog(settings=settings, credentials=creds)
    if creds.cliproxy_api_key is None:
        return SmokeResult("cliproxy", settings.default_model, False, "missing_credentials")
    try:
        await catalog.refresh_cliproxy()
        resolved = catalog.resolve(ProviderName.CLIPROXY, settings.default_model)
        model = build_responses_model(
            resolved, api_key=creds.cliproxy_api_key.get_secret_value()
        )
        agent = Agent(model, output_type=str, system_prompt="Reply with exactly: ok")
        result = await agent.run("ping")
        text = result.output if isinstance(result.output, str) else str(result.output)
        return SmokeResult(
            "cliproxy", resolved.model_id, True, f"output_len={len(text)}"
        )
    except Exception as exc:
        return SmokeResult(
            "cliproxy", settings.default_model, False, type(exc).__name__
        )


def run_smoke(target: str) -> SmokeResult:
    if target == "deepseek":
        return asyncio.run(smoke_deepseek())
    if target == "cliproxy":
        return asyncio.run(smoke_cliproxy())
    raise SystemExit(f"unknown smoke target: {target}")
