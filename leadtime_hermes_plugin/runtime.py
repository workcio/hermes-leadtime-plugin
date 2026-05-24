from __future__ import annotations

from .config import BotConfig, load_config
from .leadtime_client import LeadtimeClient


_SESSION_BINDINGS: dict[str, dict] = {}


def remember_session(run_id: str, bot: BotConfig, task_id: str | None = None, task_identifier: str | None = None) -> None:
    _SESSION_BINDINGS[run_id] = {
        "bot": bot,
        "taskId": task_id,
        "taskIdentifier": task_identifier or task_id,
    }


def resolve_client_and_binding(run_id: str) -> tuple[LeadtimeClient, dict]:
    config = load_config()
    binding = _SESSION_BINDINGS.get(run_id)
    if binding:
        return LeadtimeClient(config, binding["bot"]), binding

    for bot in config.bots:
        client = LeadtimeClient(config, bot)
        try:
            context = client.get_session_context(run_id)
        except Exception:
            continue
        task = context.get("task") if isinstance(context, dict) else None
        task_id = task.get("id") if isinstance(task, dict) else None
        task_identifier = str(task.get("shortNumber")) if isinstance(task, dict) and task.get("shortNumber") is not None else task_id
        remember_session(run_id, bot, task_id, task_identifier)
        return client, _SESSION_BINDINGS[run_id]

    raise ValueError(f"Leadtime session {run_id} is not owned by any configured Hermes bot.")
