from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from .config import config_to_json, default_config_path, hermes_home, normalize_base_url, normalize_path, redact_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the Leadtime Hermes plugin.")
    parser.add_argument("--leadtime-base-url", required=True, help="Leadtime app/API URL, e.g. https://leadtime.app/api")
    parser.add_argument("--claim", help="One-time Leadtime setup code")
    parser.add_argument("--gateway-public-url", help="Public connector URL reachable by Leadtime")
    parser.add_argument("--agent-id", default="default", help="Hermes agent/profile id label for this bot")
    parser.add_argument("--mode", choices=["basic", "full"], default="basic")
    parser.add_argument("--webhook-path", default="/leadtime/webhook")
    parser.add_argument("--bot-user-id")
    parser.add_argument("--bot-pat")
    parser.add_argument("--webhook-secret")
    parser.add_argument("--name", default="Leadtime Bot")
    parser.add_argument("--raw-api", nargs="?", const="true", default="false")
    parser.add_argument("--hermes-api-base-url", default="http://127.0.0.1:8642")
    parser.add_argument("--hermes-api-key", default=os.environ.get("API_SERVER_KEY") or "leadtime-hermes-local")
    parser.add_argument("--config", default=str(default_config_path()))
    parser.add_argument("--hermes-config", default=str(hermes_home() / "config.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    leadtime_base_url = normalize_leadtime_api_base_url(args.leadtime_base_url)
    webhook_path = normalize_path(args.webhook_path)

    if args.claim:
        if not args.gateway_public_url:
            raise SystemExit("--gateway-public-url is required when claiming a setup code")
        validate_gateway_public_url(args.gateway_public_url, leadtime_base_url)
        setup = claim_setup_token(
            leadtime_base_url=leadtime_base_url,
            setup_token=args.claim,
            gateway_public_url=args.gateway_public_url,
            agent_id=args.agent_id,
        )
        bot = {
            "name": setup.get("botName") or "Leadtime Bot",
            "botUserId": required(setup, "botUserId"),
            "botPat": required(setup, "botPat"),
            "webhookSecret": required(setup, "webhookSecret"),
            "agentId": setup.get("agentId") or args.agent_id,
            "mode": "full" if setup.get("mode") == "full" else "basic",
            "promptGuidance": (setup.get("guidance") or {}).get("instructions", "") if isinstance(setup.get("guidance"), dict) else "",
            "exposeRawApiCredentialToAgent": bool(setup.get("exposeRawApiCredentialToAgent")),
        }
        webhook_path = normalize_path(setup.get("webhookPath") or webhook_path)
    else:
        for key in ["bot_user_id", "bot_pat", "webhook_secret"]:
            if not getattr(args, key):
                raise SystemExit(f"--{key.replace('_', '-')} is required without --claim")
        bot = {
            "name": args.name,
            "botUserId": args.bot_user_id,
            "botPat": args.bot_pat,
            "webhookSecret": args.webhook_secret,
            "agentId": args.agent_id,
            "mode": args.mode,
            "promptGuidance": "",
            "exposeRawApiCredentialToAgent": parse_bool(args.raw_api),
        }

    config_path = Path(args.config)
    existing = read_json(config_path, {})
    merged = merge_config(
        existing,
        {
            "leadtimeBaseUrl": leadtime_base_url,
            "webhookPath": webhook_path,
            "hermesApiBaseUrl": normalize_base_url(args.hermes_api_base_url),
            "hermesApiKey": args.hermes_api_key,
            "runner": {"timeoutSeconds": 900},
            "bot": bot,
        },
    )

    hermes_config = read_yaml(Path(args.hermes_config))
    hermes_config.setdefault("plugins", {})
    enabled = hermes_config["plugins"].setdefault("enabled", [])
    if "leadtime" not in enabled:
        enabled.append("leadtime")
    model = hermes_config.setdefault("model", {})
    model.setdefault("provider", "openrouter")
    model.setdefault("model", os.environ.get("HERMES_TEST_MODEL") or "moonshotai/kimi-k2.6")

    if args.dry_run:
        print(config_to_json(redact_config(merged)))
        print("--- hermes config ---")
        print(yaml.safe_dump(hermes_config, sort_keys=False))
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_to_json(merged), "utf-8")
    hermes_config_path = Path(args.hermes_config)
    hermes_config_path.parent.mkdir(parents=True, exist_ok=True)
    hermes_config_path.write_text(yaml.safe_dump(hermes_config, sort_keys=False), "utf-8")

    print(f"Updated {config_path}")
    print(f"Updated {hermes_config_path}")
    print("")
    print("Next steps:")
    print("1. Install/enable the Hermes plugin if needed:")
    print("   hermes plugins install workcio/hermes-leadtime-plugin --enable")
    print("2. Start Hermes API server:")
    print(f"   API_SERVER_ENABLED=true API_SERVER_KEY={args.hermes_api_key} hermes gateway")
    print("3. Start the Leadtime connector:")
    print("   leadtime-hermes-connector")
    if args.gateway_public_url:
        print(f"4. Leadtime has saved this bot webhook URL: {args.gateway_public_url.rstrip('/')}{webhook_path}")
    else:
        print(f"4. In Leadtime, set this bot webhook URL: <your-hermes-public-url>{webhook_path}")


def claim_setup_token(*, leadtime_base_url: str, setup_token: str, gateway_public_url: str, agent_id: str) -> dict[str, Any]:
    endpoint = f"{leadtime_base_url}/public/agent-connectors/setup/claim"
    response = requests.post(
        endpoint,
        json={
            "setupToken": setup_token,
            "gatewayPublicUrl": gateway_public_url.rstrip("/"),
            "agentId": agent_id,
            "runtimeVersion": "hermes-leadtime-plugin@0.1.0",
        },
        timeout=30,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not response.ok:
        raise SystemExit(body.get("message") or f"Setup claim failed with HTTP {response.status_code}: {response.text[:500]}")
    return body


def merge_config(existing: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["leadtimeBaseUrl"] = setup["leadtimeBaseUrl"]
    merged["webhookPath"] = setup["webhookPath"]
    merged["hermesApiBaseUrl"] = setup["hermesApiBaseUrl"]
    merged["hermesApiKey"] = setup["hermesApiKey"]
    merged["runner"] = {**(merged.get("runner") or {}), **setup["runner"]}
    bots = [bot for bot in merged.get("bots") or [] if bot.get("botUserId") != setup["bot"]["botUserId"]]
    bots.append(setup["bot"])
    merged["bots"] = bots
    return merged


def normalize_leadtime_api_base_url(value: str) -> str:
    normalized = normalize_base_url(value.strip())
    if normalized.endswith("/public"):
        normalized = normalized.removesuffix("/public")
    if not normalized.endswith("/api"):
        normalized = f"{normalized}/api"
    return normalized


def validate_gateway_public_url(gateway_public_url: str, leadtime_base_url: str) -> None:
    parsed = urlparse(gateway_public_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("Gateway public URL must be an absolute http(s) URL.")
    leadtime_host = urlparse(leadtime_base_url).hostname or ""
    host = parsed.hostname or ""
    local_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    if host in local_hosts and leadtime_host not in local_hosts:
        raise SystemExit("A local Hermes connector URL can only be used with local Leadtime.")


def required(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"Setup claim response is missing {key}.")
    return value.strip()


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return fallback


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


if __name__ == "__main__":
    main()
