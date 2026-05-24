from __future__ import annotations

import json
import time
from typing import Any, Iterator

import requests

from .config import LeadtimeConfig


class HermesClient:
    def __init__(self, config: LeadtimeConfig):
        self.config = config

    @property
    def v1_base_url(self) -> str:
        return f"{self.config.hermes_api_base_url}/v1"

    def headers(self) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if self.config.hermes_api_key:
            headers["authorization"] = f"Bearer {self.config.hermes_api_key}"
        return headers

    def health(self) -> bool:
        response = requests.get(f"{self.config.hermes_api_base_url}/health", headers=self.headers(), timeout=10)
        return response.ok

    def create_run(self, *, session_id: str, input_text: str, instructions: str = "") -> str:
        response = requests.post(
            f"{self.v1_base_url}/runs",
            headers={**self.headers(), "content-type": "application/json"},
            json={
                "input": input_text,
                "session_id": session_id,
                "instructions": instructions or None,
            },
            timeout=30,
        )
        if response.status_code != 202:
            raise RuntimeError(f"Hermes run create failed: {response.status_code} {response.text[:500]}")
        return response.json()["run_id"]

    def stream_events(self, hermes_run_id: str, timeout_seconds: int) -> Iterator[dict[str, Any]]:
        deadline = time.monotonic() + timeout_seconds
        with requests.get(
            f"{self.v1_base_url}/runs/{hermes_run_id}/events",
            headers={**self.headers(), "accept": "text/event-stream"},
            stream=True,
            timeout=(10, timeout_seconds + 30),
        ) as response:
            if not response.ok:
                raise RuntimeError(f"Hermes run events failed: {response.status_code} {response.text[:500]}")
            for raw_line in response.iter_lines(decode_unicode=True):
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Hermes run {hermes_run_id} timed out")
                if not raw_line or raw_line.startswith(":"):
                    continue
                if not raw_line.startswith("data:"):
                    continue
                payload = raw_line.removeprefix("data:").strip()
                if payload == "[DONE]":
                    break
                yield json.loads(payload)
