"""In-memory model settings for the local Web application.

This module is the security boundary for credentials entered in the browser.
It never writes model credentials to disk and never exposes an API key in a
status payload or error message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Mapping
from urllib.parse import urlparse

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover - dependency-light test environments
    def dotenv_values(*args, **kwargs):
        return {}

from ..config import RuntimeConfig, resolve_text_model_id
from ..llm import build_llm


_RUNTIME_ENV_KEYS = {
    "LLM_MODEL_ID",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "TAVILY_API_KEY",
    "EMBEDDING_MODEL_ID",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_TIMEOUT",
    "VISION_LLM_MODEL_ID",
    "VISION_LLM_API_KEY",
    "VISION_LLM_BASE_URL",
    "VISION_LLM_TIMEOUT",
}


@dataclass(frozen=True)
class ModelSettingsInput:
    model_id: str
    base_url: str
    api_key: str
    timeout: int = 120


@dataclass(frozen=True)
class _StoredModelSettings:
    config: RuntimeConfig
    updated_at: str
    connection_status: str = "untested"
    connection_message: str = "尚未测试连接。"


def _safe_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _environment_values(env_file: str | Path | None = None) -> dict[str, str]:
    file_values: Mapping[str, object] = {}
    target = Path(env_file) if env_file else Path(".env")
    if target.exists():
        file_values = dotenv_values(target, encoding="utf-8-sig")

    values: dict[str, str] = {
        str(key): str(value)
        for key, value in file_values.items()
        if key in _RUNTIME_ENV_KEYS and value not in (None, "")
    }
    for key in _RUNTIME_ENV_KEYS:
        value = os.getenv(key)
        if value:
            values[key] = value
    return values


def validate_model_settings(
    settings: ModelSettingsInput,
    *,
    env_file: str | Path | None = None,
) -> RuntimeConfig:
    """Validate browser input and build an immutable runtime snapshot."""

    model_id = str(settings.model_id or "").strip()
    base_url = str(settings.base_url or "").strip().rstrip("/")
    api_key = str(settings.api_key or "").strip()
    timeout = _safe_int(settings.timeout, 120)

    if not model_id:
        raise ValueError("请输入模型名称。")
    if len(model_id) > 200:
        raise ValueError("模型名称过长，请检查后重试。")
    if not base_url:
        raise ValueError("请输入 Base URL。")
    if len(base_url) > 2048:
        raise ValueError("Base URL 过长，请检查后重试。")

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL 必须是完整的 http:// 或 https:// 地址。")
    if parsed.username or parsed.password:
        raise ValueError("Base URL 不能包含用户名或密码。")
    if parsed.fragment or parsed.query:
        raise ValueError("Base URL 不能包含查询参数或片段。")
    if not api_key:
        raise ValueError("请输入 API Key。")
    if len(api_key) > 4096:
        raise ValueError("API Key 过长，请检查后重试。")
    if timeout < 5 or timeout > 600:
        raise ValueError("连接超时必须在 5 到 600 秒之间。")

    environment = _environment_values(env_file)
    return RuntimeConfig(
        model_id=resolve_text_model_id(model_id, base_url),
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        tavily_api_key=environment.get("TAVILY_API_KEY"),
        embedding_model_id=environment.get("EMBEDDING_MODEL_ID"),
        embedding_api_key=environment.get("EMBEDDING_API_KEY"),
        embedding_base_url=environment.get("EMBEDDING_BASE_URL"),
        embedding_timeout=_safe_int(environment.get("EMBEDDING_TIMEOUT"), timeout),
        vision_model_id=environment.get("VISION_LLM_MODEL_ID"),
        vision_api_key=environment.get("VISION_LLM_API_KEY"),
        vision_base_url=environment.get("VISION_LLM_BASE_URL"),
        vision_timeout=_safe_int(environment.get("VISION_LLM_TIMEOUT"), timeout),
    )


def redact_sensitive_text(text: object, *secrets: str) -> str:
    redacted = str(text or "")
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def actionable_connection_error(error: Exception, api_key: str) -> str:
    """Return a short, actionable message without echoing credentials."""

    raw = redact_sensitive_text(error, api_key)
    lowered = raw.lower()
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)

    if status_code in {401, 403} or "unauthorized" in lowered or "forbidden" in lowered:
        return "认证失败：请检查 API Key 是否正确，以及该密钥是否有权访问此模型。"
    if status_code == 404 or "not found" in lowered:
        return "未找到接口或模型：请检查 Base URL 和模型名称。"
    if "timeout" in lowered or "timed out" in lowered:
        return "连接超时：请检查网络、Base URL，或稍后重试。"
    if any(token in lowered for token in ("connection", "dns", "name resolution", "refused")):
        return "无法连接模型服务：请检查网络和 Base URL。"
    return f"连接测试失败：{raw[:300] or '模型服务未返回有效响应。'}"


def test_model_connection(config: RuntimeConfig) -> str:
    """Make one minimal model call without starting an analysis run."""

    try:
        client = build_llm(config)
        client.invoke(
            [{"role": "user", "content": "Reply with OK only."}],
            max_tokens=8,
            temperature=0,
        )
    except Exception as exc:
        raise ValueError(actionable_connection_error(exc, config.api_key)) from None
    return "连接成功，模型服务已响应。"


class ModelSettingsStore:
    """Thread-safe process-local storage for browser-provided credentials."""

    def __init__(self, default_env_file: str | Path | None = None) -> None:
        self._lock = Lock()
        self._stored: _StoredModelSettings | None = None
        self._default_env_file = Path(default_env_file) if default_env_file else None

    def save(self, settings: ModelSettingsInput) -> dict[str, object]:
        config = validate_model_settings(settings, env_file=self._default_env_file)
        stored = _StoredModelSettings(
            config=config,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._stored = stored
        return self.public_status()

    def clear(self) -> dict[str, object]:
        with self._lock:
            self._stored = None
        return self.public_status()

    def runtime_config(self, env_file: str | Path | None = None) -> RuntimeConfig | None:
        with self._lock:
            stored = self._stored
        if stored is None:
            return None
        if not env_file:
            return stored.config
        return validate_model_settings(
            ModelSettingsInput(
                model_id=stored.config.model_id,
                base_url=stored.config.base_url,
                api_key=stored.config.api_key,
                timeout=stored.config.timeout,
            ),
            env_file=env_file,
        )

    def record_connection_result(
        self,
        tested_config: RuntimeConfig,
        *,
        succeeded: bool,
        message: str,
    ) -> None:
        with self._lock:
            current = self._stored
            if current is None or current.config != tested_config:
                return
            self._stored = _StoredModelSettings(
                config=current.config,
                updated_at=current.updated_at,
                connection_status="connected" if succeeded else "failed",
                connection_message=redact_sensitive_text(message, current.config.api_key),
            )

    def public_status(self) -> dict[str, object]:
        with self._lock:
            stored = self._stored
        if stored is not None:
            return {
                "configured": True,
                "source": "web",
                "modelId": stored.config.model_id,
                "baseUrl": stored.config.base_url,
                "apiKeyConfigured": True,
                "connectionStatus": stored.connection_status,
                "message": stored.connection_message,
                "updatedAt": stored.updated_at,
            }

        environment = _environment_values(self._default_env_file)
        configured = all(environment.get(key) for key in ("LLM_MODEL_ID", "LLM_BASE_URL", "LLM_API_KEY"))
        return {
            "configured": configured,
            "source": "environment" if configured else "none",
            "modelId": environment.get("LLM_MODEL_ID", "") if configured else "",
            "baseUrl": environment.get("LLM_BASE_URL", "") if configured else "",
            "apiKeyConfigured": bool(environment.get("LLM_API_KEY")),
            "connectionStatus": "untested",
            "message": (
                "当前使用环境文件配置。"
                if configured
                else "尚未配置模型，请在此页面填写，或继续使用项目环境文件。"
            ),
            "updatedAt": "",
        }
