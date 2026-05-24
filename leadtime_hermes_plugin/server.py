from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import BotConfig, LeadtimeConfig, load_config
from .hermes_client import HermesClient
from .leadtime_client import LeadtimeClient
from .runtime import remember_session
from .signature import verify_leadtime_signature

logger = logging.getLogger("leadtime_hermes_plugin.server")


class ConnectorServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, config_path: str | None):
        super().__init__(server_address, RequestHandlerClass)
        self.config_path = config_path

    def load_config(self) -> LeadtimeConfig:
        return load_config(self.config_path)


class Handler(BaseHTTPRequestHandler):
    server: ConnectorServer

    def log_message(self, fmt: str, *args) -> None:
        logger.info(fmt, *args)

    def do_GET(self) -> None:
        if self.path in {"/health", "/"}:
            try:
                config = self.server.load_config()
                configured = len(config.bots) > 0
                webhook_path = config.webhook_path
            except Exception:
                configured = False
                webhook_path = "/leadtime/webhook"
            self._json(
                200,
                {
                    "ok": True,
                    "connector": "leadtime-hermes",
                    "configured": configured,
                    "webhookPath": webhook_path,
                },
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        try:
            config = self.server.load_config()
        except Exception as exc:
            self._json(503, {"error": "Leadtime Hermes connector is not configured", "detail": str(exc)})
            return

        if self.path.split("?", 1)[0] != config.webhook_path:
            self._json(404, {"error": "not_found"})
            return

        raw_body = self.rfile.read(int(self.headers.get("content-length") or "0"))
        bot = self._find_bot(config, raw_body)
        if bot is None:
            self._json(401, {"error": "Invalid Leadtime webhook signature"})
            return

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except ValueError:
            self._json(400, {"error": "Invalid JSON"})
            return

        run_id = str(payload.get("agentRunId") or "")
        if not run_id:
            self._json(400, {"error": "agentRunId is required"})
            return

        event_id = self.headers.get("leadtime-webhook-id") or self.headers.get("idempotency-key") or run_id
        self._json(202, {"ok": True, "runId": run_id})
        threading.Thread(target=self._dispatch, args=(config, bot, payload, event_id), daemon=True).start()

    def _find_bot(self, config: LeadtimeConfig, raw_body: bytes) -> BotConfig | None:
        signature = self.headers.get("leadtime-signature")
        timestamp = self.headers.get("leadtime-webhook-timestamp")
        for bot in config.bots:
            if verify_leadtime_signature(raw_body, bot.webhook_secret, signature, timestamp):
                return bot
        return None

    def _dispatch(self, config: LeadtimeConfig, bot: BotConfig, payload: dict[str, Any], event_id: str) -> None:
        run_id = str(payload["agentRunId"])
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        task = context.get("task") if isinstance(context.get("task"), dict) else {}
        task_id = payload.get("taskId") or task.get("id")
        task_identifier = str(task.get("shortNumber")) if task.get("shortNumber") is not None else task_id
        remember_session(run_id, bot, task_id, task_identifier)

        client = LeadtimeClient(config, bot)
        hermes = HermesClient(config)
        try:
            client.update_status(run_id, "running", "Hermes accepted the Leadtime session", f"status-running-{event_id}")
            client.append_activity(
                run_id,
                {
                    "activityType": "prompt",
                    "body": "Hermes received the Leadtime session webhook and started the configured agent.",
                    "providerEventId": event_id,
                    "providerEventType": payload.get("eventType"),
                    "idempotencyKey": f"webhook-accepted-{event_id}",
                    "raw": {
                        "eventType": payload.get("eventType"),
                        "taskId": payload.get("taskId"),
                        "commentId": payload.get("commentId"),
                        "botUserId": bot.bot_user_id,
                        "mode": bot.mode,
                    },
                },
            )
            hermes_run_id = hermes.create_run(
                session_id=f"leadtime-{run_id}",
                input_text=build_agent_message(config, bot, payload, run_id),
                instructions="You are a Hermes Agent runtime connected to Leadtime task sessions. Use the Leadtime tools when acting on Leadtime tasks.",
            )
            final_output = ""
            for event in hermes.stream_events(hermes_run_id, config.runner_timeout_seconds):
                event_type = event.get("event")
                if event_type in {"tool.started", "tool.completed"}:
                    client.append_activity(
                        run_id,
                        {
                            "activityType": "toolCall" if event_type == "tool.started" else "toolResult",
                            "body": event.get("preview") or event.get("tool") or event_type,
                            "providerEventId": event_id,
                            "providerEventType": event_type,
                    "idempotencyKey": f"hermes-{event_type}-{event.get('timestamp') or event_id}-{event.get('tool') or 'event'}",
                            "raw": event,
                        },
                    )
                elif event_type == "run.completed":
                    final_output = str(event.get("output") or "Hermes agent finished.")
                elif event_type == "run.failed":
                    raise RuntimeError(str(event.get("error") or "Hermes run failed"))
            client.append_activity(
                run_id,
                {
                    "activityType": "response",
                    "body": final_output or "Hermes agent finished.",
                    "providerEventId": event_id,
                    "providerEventType": "hermes.agent.finished",
                    "idempotencyKey": f"hermes-response-{event_id}",
                    "raw": {"hermesRunId": hermes_run_id},
                },
            )
            client.update_status(run_id, "done", "Hermes agent finished", f"status-done-{event_id}")
        except Exception as exc:
            logger.exception("Leadtime Hermes dispatch failed")
            try:
                client.append_activity(
                    run_id,
                    {
                        "activityType": "error",
                        "body": f"Hermes agent did not finish successfully: {exc}",
                        "providerEventId": event_id,
                        "providerEventType": "hermes.agent.failed",
                        "idempotencyKey": f"hermes-error-{event_id}",
                        "raw": {"error": str(exc)},
                    },
                )
                client.update_status(run_id, "failed", f"Hermes agent did not finish successfully: {exc}", f"status-failed-{event_id}")
            except Exception:
                logger.exception("Failed to report Hermes failure to Leadtime")

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_agent_message(config: LeadtimeConfig, bot: BotConfig, payload: dict[str, Any], run_id: str) -> str:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    prompt_context = context.get("promptContext")
    if not isinstance(prompt_context, str):
        prompt_context = json.dumps(context, indent=2, default=str)

    lines = [
        "You are handling a Leadtime task agent session.",
        "",
        f"Leadtime session id: {run_id}",
        f"Leadtime API base URL: {config.public_base_url}",
        f"Configured mode: {bot.mode}",
        "",
        "Use Leadtime tools with leadtimeSessionId set to the session id above.",
        "The connector reports session status; use task tools to read/update the task and add comments when useful.",
    ]
    if bot.mode == "basic":
        lines.append("Available Leadtime task tools: leadtime_get_session_context, leadtime_read_task, leadtime_add_task_comment, leadtime_list_task_statuses, leadtime_update_task_status.")
    else:
        lines.append("Full Leadtime API tools are enabled: leadtime_list_actions, leadtime_action_details, leadtime_execute_action.")
        if bot.expose_raw_api_credential_to_agent:
            lines.extend([
                "",
                "Raw Leadtime API credential exposure is enabled for this bot.",
                f"Authorization header: Bearer {bot.bot_pat}",
                f"OpenAPI document: {config.public_base_url}/docs/json",
            ])
    if bot.prompt_guidance:
        lines.extend(["", "Bot-specific guidance:", bot.prompt_guidance])
    lines.extend(["", "Leadtime context:", prompt_context])
    return "\n".join(lines)


def start_connector_server(host: str, port: int, config_path: str | None = None) -> ConnectorServer:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = ConnectorServer((host, port), Handler, config_path)
    logger.info("Leadtime Hermes connector listening on http://%s:%s/leadtime/webhook", host, port)
    return server


def run_connector_server(host: str, port: int, config_path: str | None = None) -> None:
    server = start_connector_server(host, port, config_path)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Leadtime Hermes connector webhook server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9338)
    parser.add_argument("--config")
    args = parser.parse_args()
    run_connector_server(args.host, args.port, args.config)


if __name__ == "__main__":
    main()
