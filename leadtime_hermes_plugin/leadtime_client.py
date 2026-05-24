from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import requests

from .config import BotConfig, LeadtimeConfig


class LeadtimeClient:
    def __init__(self, config: LeadtimeConfig, bot: BotConfig):
        self.config = config
        self.bot = bot

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        token: str | None = None,
        timeout: int = 60,
    ) -> Any:
        url = f"{self.config.public_base_url}{path if path.startswith('/') else '/' + path}"
        headers = {
            "authorization": f"Bearer {token or self.bot.bot_pat}",
            "accept": "application/json",
        }
        if body is not None:
            headers["content-type"] = "application/json"
        response = requests.request(method, url, headers=headers, json=body, timeout=timeout)
        text = response.text
        try:
            payload = response.json() if text else None
        except ValueError:
            payload = text
        if not response.ok:
            raise RuntimeError(f"Leadtime {method} {path} failed: {response.status_code} {text[:500]}")
        return payload

    def get_session_context(self, run_id: str) -> Any:
        return self.request("GET", f"/agent-sessions/{quote(run_id)}/context")

    def append_activity(self, run_id: str, activity: dict[str, Any]) -> Any:
        return self.request("POST", f"/agent-sessions/{quote(run_id)}/activities", body=activity)

    def update_status(self, run_id: str, status: str, message: str = "", idempotency_key: str = "") -> Any:
        return self.request(
            "PATCH",
            f"/agent-sessions/{quote(run_id)}/status",
            body={"status": status, "message": message, "idempotencyKey": idempotency_key},
        )

    def read_task(self, identifier: str) -> Any:
        return self.request("GET", f"/tasks/{quote(identifier)}")

    def add_task_comment(self, identifier: str, comment: str) -> Any:
        return self.request("POST", f"/tasks/{quote(identifier)}/comments", body={"comment": comment})

    def list_task_statuses(self) -> Any:
        return self.request("GET", "/tasks/statuses")

    def update_task_status(self, identifier: str, status_id: str) -> Any:
        return self.request("PATCH", f"/tasks/{quote(identifier)}", body={"statusId": status_id})

    def get_openapi_document(self) -> dict[str, Any]:
        return self.request("GET", "/docs/json")

    def execute_action(self, method: str, path: str, body: Any | None = None) -> Any:
        if not path.startswith("/"):
            path = f"/{path}"
        return self.request(method.upper(), path, body=body)


def list_openapi_actions(doc: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for path, operations in (doc.get("paths") or {}).items():
        if not isinstance(operations, dict):
            continue
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation = operation if isinstance(operation, dict) else {}
            actions.append(
                {
                    "operationId": operation.get("operationId") or _fallback_operation_id(method, path),
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary"),
                    "description": operation.get("description"),
                }
            )
    return sorted(actions, key=lambda item: str(item["operationId"]))


def find_openapi_action(doc: dict[str, Any], action_name: str) -> dict[str, Any] | None:
    for path, operations in (doc.get("paths") or {}).items():
        if not isinstance(operations, dict):
            continue
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation = operation if isinstance(operation, dict) else {}
            operation_id = operation.get("operationId") or _fallback_operation_id(method, path)
            if operation_id == action_name or f"{method.upper()} {path}" == action_name:
                return {
                    "operationId": operation_id,
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary"),
                    "description": operation.get("description"),
                    "operation": operation,
                }
    return None


def _fallback_operation_id(method: str, path: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in path)
    return f"{method.lower()}_{safe}"


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)
