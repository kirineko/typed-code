"""Model catalog: DeepSeek fixed entry + CLIProxyAPI discovery."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.protocol.common import ProviderName
from typed_code.protocol.errors import ErrorCode
from typed_code.protocol.models import ModelInfo, ModelListResponse
from typed_code.providers.profiles import (
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_PROFILE,
    cliproxy_profile,
    resolve_context_token_budget,
)
from typed_code.providers.settings_normalize import ModelSelectionError


@dataclass(frozen=True)
class ResolvedModel:
    provider: ProviderName
    model_id: str
    base_url: str
    display_name: str | None
    availability: ProviderAvailability


@dataclass
class ModelCatalog:
    settings: Settings
    credentials: Credentials
    _cliproxy_model_ids: set[str] = field(default_factory=set)
    _cliproxy_refresh_error: str | None = None

    def deepseek_info(self) -> ModelInfo:
        availability = self.credentials.deepseek_availability
        return ModelInfo(
            provider=ProviderName.DEEPSEEK,
            model_id=DEEPSEEK_MODEL_ID,
            display_name="DeepSeek V4 Flash",
            availability=availability,  # type: ignore[arg-type]
            capabilities=DEEPSEEK_PROFILE.to_public_capabilities(),
            context_token_budget=resolve_context_token_budget(
                ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID
            ),
        )

    def list_models(self) -> ModelListResponse:
        models = [self.deepseek_info()]
        cliproxy_availability = self.credentials.cliproxy_availability
        for model_id in sorted(self._cliproxy_model_ids):
            profile = cliproxy_profile(model_id)
            models.append(
                ModelInfo(
                    provider=ProviderName.CLIPROXY,
                    model_id=model_id,
                    display_name=model_id,
                    availability=cliproxy_availability,  # type: ignore[arg-type]
                    capabilities=profile.to_public_capabilities(),
                    context_token_budget=profile.context_token_budget,
                )
            )
        return ModelListResponse(models=models)

    async def refresh_cliproxy(
        self, *, client: httpx.AsyncClient | None = None
    ) -> list[str]:
        """Refresh discovered CLIProxy model IDs. Order of API response is ignored."""
        if self.credentials.cliproxy_availability is ProviderAvailability.MISSING_CREDENTIALS:
            self._cliproxy_model_ids = set()
            self._cliproxy_refresh_error = "missing_credentials"
            return []

        base = self.settings.cliproxy_base_url.rstrip("/")
        url = f"{base}/models"
        owns_client = client is None
        http = client or httpx.AsyncClient(timeout=10.0)
        try:
            key = self.credentials.cliproxy_api_key
            headers = {}
            if key is not None:
                headers["Authorization"] = f"Bearer {key.get_secret_value()}"
            response = await http.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            ids = _parse_model_ids(payload)
            self._cliproxy_model_ids = set(ids)
            self._cliproxy_refresh_error = None
            return sorted(self._cliproxy_model_ids)
        except Exception as exc:  # network / parse — catalog stays usable
            self._cliproxy_refresh_error = type(exc).__name__
            # Keep previous discovery on soft failure
            return sorted(self._cliproxy_model_ids)
        finally:
            if owns_client:
                await http.aclose()

    def resolve(
        self,
        provider: ProviderName | None,
        model_id: str | None,
    ) -> ResolvedModel:
        """Resolve a selection.

        When both ``provider`` and ``model_id`` are omitted, try configured
        defaults first, then fall back to any available provider (DeepSeek, then
        first discovered CLIProxy model). Explicit selections stay strict.
        """
        if provider is None and model_id is None:
            return self._resolve_default_with_fallback()
        return self._resolve_exact(provider, model_id)

    def _resolve_default_with_fallback(self) -> ResolvedModel:
        try:
            return self._resolve_exact(None, None)
        except ModelSelectionError:
            pass
        # Prefer DeepSeek when its key is present (common single-key setup).
        if self.credentials.deepseek_api_key is not None:
            return self._resolve_exact(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID)
        if (
            self.credentials.cliproxy_api_key is not None
            and self._cliproxy_model_ids
        ):
            mid = sorted(self._cliproxy_model_ids)[0]
            return self._resolve_exact(ProviderName.CLIPROXY, mid)
        err = ModelSelectionError(
            "no available model: configure a provider API key "
            "(DeepSeek or CLIProxy) and ensure models are discoverable"
        )
        err.code = ErrorCode.MISSING_CREDENTIALS
        raise err

    def _resolve_exact(
        self,
        provider: ProviderName | None,
        model_id: str | None,
    ) -> ResolvedModel:
        """Resolve an explicit or settings-default selection (no cross-provider fallback)."""
        prov = provider or ProviderName(self.settings.default_provider)
        mid = (model_id or self.settings.default_model).strip()
        if not mid:
            raise ModelSelectionError("model must be non-empty")

        if prov is ProviderName.DEEPSEEK:
            if mid != DEEPSEEK_MODEL_ID:
                raise ModelSelectionError(
                    f"DeepSeek only supports {DEEPSEEK_MODEL_ID!r}, got {mid!r}"
                )
            if self.credentials.deepseek_api_key is None:
                err = ModelSelectionError("DeepSeek credentials are missing")
                err.code = ErrorCode.MISSING_CREDENTIALS
                raise err
            return ResolvedModel(
                provider=ProviderName.DEEPSEEK,
                model_id=DEEPSEEK_MODEL_ID,
                base_url=self.settings.deepseek_base_url,
                display_name="DeepSeek V4 Flash",
                availability=ProviderAvailability.AVAILABLE,
            )

        # cliproxy
        if self.credentials.cliproxy_api_key is None:
            err = ModelSelectionError("CLIProxyAPI credentials are missing")
            err.code = ErrorCode.MISSING_CREDENTIALS
            raise err
        if mid not in self._cliproxy_model_ids:
            raise ModelSelectionError(
                f"CLIProxyAPI model {mid!r} was not discovered; "
                "ensure CLIProxy is running and refresh models "
                f"(discovered={sorted(self._cliproxy_model_ids)!r})"
            )
        return ResolvedModel(
            provider=ProviderName.CLIPROXY,
            model_id=mid,
            base_url=self.settings.cliproxy_base_url,
            display_name=mid,
            availability=ProviderAvailability.AVAILABLE,
        )

    def default_selection(self) -> ResolvedModel | None:
        try:
            return self.resolve(None, None)
        except ModelSelectionError:
            return None

    @property
    def cliproxy_refresh_error(self) -> str | None:
        return self._cliproxy_refresh_error

    def seed_cliproxy_models(self, model_ids: set[str] | list[str]) -> None:
        """Test helper / offline seed; production uses refresh_cliproxy."""
        self._cliproxy_model_ids = set(model_ids)


def _parse_model_ids(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            mid = item["id"].strip()
            if mid:
                ids.append(mid)
        elif isinstance(item, str) and item.strip():
            ids.append(item.strip())
    return ids
