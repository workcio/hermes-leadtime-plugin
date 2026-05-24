from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BotConfig:
    name: str
    bot_user_id: str
    bot_pat: str
    webhook_secret: str
    agent_id: str
    mode: str = "basic"
    prompt_guidance: str = ""
    expose_raw_api_credential_to_agent: bool = False


@dataclass(frozen=True)
class LeadtimeConfig:
    leadtime_base_url: str
    webhook_path: str
    connector_host: str
    connector_port: int
    hermes_api_base_url: str
    hermes_api_key: str
    runner_timeout_seconds: int
    bots: list[BotConfig]

    @property
    def public_base_url(self) -> str:
        return f"{self.leadtime_base_url}/public"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def default_config_path() -> Path:
    return Path(os.environ.get("LEADTIME_HERMES_CONFIG") or hermes_home() / "leadtime" / "config.json")


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def normalize_path(value: str | None) -> str:
    raw = (value or "/leadtime/webhook").strip() or "/leadtime/webhook"
    with_slash = raw if raw.startswith("/") else f"/{raw}"
    return with_slash.rstrip("/") or "/leadtime/webhook"


def load_config(path: str | Path | None = None) -> LeadtimeConfig:
    config_path = Path(path) if path else default_config_path()
    raw = json.loads(config_path.read_text("utf-8"))
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> LeadtimeConfig:
    leadtime_base_url = normalize_base_url(str(raw.get("leadtimeBaseUrl") or ""))
    if not leadtime_base_url:
        raise ValueError("leadtimeBaseUrl is required")

    bots: list[BotConfig] = []
    for index, entry in enumerate(raw.get("bots") or []):
        if not isinstance(entry, dict):
            raise ValueError(f"bots[{index}] must be an object")
        bot_user_id = str(entry.get("botUserId") or "").strip()
        bot_pat = str(entry.get("botPat") or "").strip()
        webhook_secret = str(entry.get("webhookSecret") or "").strip()
        if not bot_user_id:
            raise ValueError(f"bots[{index}].botUserId is required")
        if not bot_pat:
            raise ValueError(f"bots[{index}].botPat is required")
        if not webhook_secret:
            raise ValueError(f"bots[{index}].webhookSecret is required")
        bots.append(
            BotConfig(
                name=str(entry.get("name") or bot_user_id),
                bot_user_id=bot_user_id,
                bot_pat=bot_pat,
                webhook_secret=webhook_secret,
                agent_id=str(entry.get("agentId") or "default"),
                mode="full" if entry.get("mode") == "full" else "basic",
                prompt_guidance=str(entry.get("promptGuidance") or ""),
                expose_raw_api_credential_to_agent=bool(entry.get("exposeRawApiCredentialToAgent")),
            )
        )
    if not bots:
        raise ValueError("At least one bot must be configured")

    runner = raw.get("runner") if isinstance(raw.get("runner"), dict) else {}
    timeout = runner.get("timeoutSeconds", 900)
    try:
        timeout = max(30, int(timeout))
    except (TypeError, ValueError):
        timeout = 900

    return LeadtimeConfig(
        leadtime_base_url=leadtime_base_url,
        webhook_path=normalize_path(raw.get("webhookPath")),
        connector_host=str((raw.get("connector") or {}).get("host") or "0.0.0.0")
        if isinstance(raw.get("connector"), dict)
        else "0.0.0.0",
        connector_port=_connector_port(raw.get("connector")),
        hermes_api_base_url=normalize_base_url(str(raw.get("hermesApiBaseUrl") or "http://127.0.0.1:8642")),
        hermes_api_key=str(raw.get("hermesApiKey") or os.environ.get("API_SERVER_KEY") or ""),
        runner_timeout_seconds=timeout,
        bots=bots,
    )


def _connector_port(raw_connector: Any) -> int:
    if not isinstance(raw_connector, dict):
        return 9338
    try:
        return max(1, min(65535, int(raw_connector.get("port") or 9338)))
    except (TypeError, ValueError):
        return 9338


def config_to_json(config: dict[str, Any]) -> str:
    return json.dumps(config, indent=2, sort_keys=True) + "\n"


def redact_config(raw: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(raw))
    for bot in clone.get("bots") or []:
        if "botPat" in bot:
            bot["botPat"] = redact_secret(str(bot["botPat"]))
        if "webhookSecret" in bot:
            bot["webhookSecret"] = redact_secret(str(bot["webhookSecret"]))
    if clone.get("hermesApiKey"):
        clone["hermesApiKey"] = redact_secret(str(clone["hermesApiKey"]))
    return clone


def redact_secret(value: str) -> str:
    if len(value) <= 12:
        return "***"
    return f"{value[:6]}…{value[-4:]}"
