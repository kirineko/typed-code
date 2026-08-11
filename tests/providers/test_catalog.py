"""Model catalog discovery and resolution."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.protocol.common import ProviderName
from typed_code.protocol.errors import ErrorCode
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID
from typed_code.providers.settings_normalize import ModelSelectionError


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", cliproxy_base_url="http://cliproxy.test/v1")


_DEFAULT_DS = SecretStr("ds-key")
_DEFAULT_CP = SecretStr("cp-key")


def _creds(
    *,
    deepseek_api_key: SecretStr | None = _DEFAULT_DS,
    cliproxy_api_key: SecretStr | None = _DEFAULT_CP,
    deepseek_availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
    cliproxy_availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
) -> Credentials:
    return Credentials(
        server_token=SecretStr("tok"),
        deepseek_api_key=deepseek_api_key,
        cliproxy_api_key=cliproxy_api_key,
        server_token_present=True,
        deepseek_availability=deepseek_availability,
        cliproxy_availability=cliproxy_availability,
    )


@pytest.mark.asyncio
async def test_refresh_ignores_order_for_defaults(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    catalog = ModelCatalog(settings=settings, credentials=_creds())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        # Put non-default model first to prove order is ignored
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "zzz-first"},
                    {"id": "gpt-5.6-terra"},
                    {"id": "aaa-last"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://cliproxy.test") as client:
        ids = await catalog.refresh_cliproxy(client=client)

    assert set(ids) == {"zzz-first", "gpt-5.6-terra", "aaa-last"}
    resolved = catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-terra")
    assert resolved.model_id == "gpt-5.6-terra"
    # Default uses settings.default_model name match
    default = catalog.resolve(None, None)
    assert default.provider is ProviderName.CLIPROXY
    assert default.model_id == "gpt-5.6-terra"


@pytest.mark.asyncio
async def test_unknown_cliproxy_model_rejected(tmp_path: Path) -> None:
    catalog = ModelCatalog(settings=_settings(tmp_path), credentials=_creds())
    catalog.seed_cliproxy_models({"known"})
    with pytest.raises(ModelSelectionError, match="not discovered"):
        catalog.resolve(ProviderName.CLIPROXY, "unknown")


def test_missing_deepseek_credentials(tmp_path: Path) -> None:
    catalog = ModelCatalog(
        settings=_settings(tmp_path),
        credentials=_creds(
            deepseek_api_key=None,
            deepseek_availability=ProviderAvailability.MISSING_CREDENTIALS,
            cliproxy_api_key=SecretStr("cp-key"),
        ),
    )
    with pytest.raises(ModelSelectionError) as exc:
        catalog.resolve(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID)
    assert exc.value.code is ErrorCode.MISSING_CREDENTIALS


def test_default_falls_back_to_deepseek_when_cliproxy_unavailable(
    tmp_path: Path,
) -> None:
    """Settings default cliproxy/gpt-5.6-sol but only DeepSeek key is configured."""
    catalog = ModelCatalog(
        settings=_settings(tmp_path),
        credentials=_creds(
            cliproxy_api_key=None,
            cliproxy_availability=ProviderAvailability.MISSING_CREDENTIALS,
        ),
    )
    # No discovered cliproxy models
    resolved = catalog.resolve(None, None)
    assert resolved.provider is ProviderName.DEEPSEEK
    assert resolved.model_id == DEEPSEEK_MODEL_ID


def test_explicit_cliproxy_still_strict_when_not_discovered(tmp_path: Path) -> None:
    catalog = ModelCatalog(
        settings=_settings(tmp_path),
        credentials=_creds(
            cliproxy_api_key=None,
            cliproxy_availability=ProviderAvailability.MISSING_CREDENTIALS,
        ),
    )
    with pytest.raises(ModelSelectionError, match="credentials are missing"):
        catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-sol")
