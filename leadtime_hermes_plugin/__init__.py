from __future__ import annotations

from .leadtime_client import find_openapi_action, json_text, list_openapi_actions
from .runtime import resolve_client_and_binding


def register(ctx):
    ctx.register_tool(
        name="leadtime_get_session_context",
        toolset="leadtime",
        schema={
            "name": "leadtime_get_session_context",
            "description": "Read the current Leadtime agent session context, including trigger, task, comments, and history.",
            "parameters": _object({"leadtimeSessionId": _string("Leadtime agent session id from the current prompt.")}, ["leadtimeSessionId"]),
        },
        handler=_get_session_context,
        description="Read Leadtime task-session context.",
    )
    ctx.register_tool(
        name="leadtime_read_task",
        toolset="leadtime",
        schema={
            "name": "leadtime_read_task",
            "description": "Read a Leadtime task by UUID or short number. Defaults to the current session task.",
            "parameters": _task_identifier_schema(),
        },
        handler=_read_task,
        description="Read a Leadtime task.",
    )
    ctx.register_tool(
        name="leadtime_add_task_comment",
        toolset="leadtime",
        schema={
            "name": "leadtime_add_task_comment",
            "description": "Add a comment to the current Leadtime task or a specified task.",
            "parameters": _object(
                {
                    "leadtimeSessionId": _string("Leadtime agent session id from the current prompt."),
                    "taskIdentifier": _string("Task UUID or short number. Defaults to the session task."),
                    "comment": _string("Comment body in Markdown or HTML."),
                },
                ["leadtimeSessionId", "comment"],
            ),
        },
        handler=_add_task_comment,
        description="Add a Leadtime task comment.",
    )
    ctx.register_tool(
        name="leadtime_list_task_statuses",
        toolset="leadtime",
        schema={
            "name": "leadtime_list_task_statuses",
            "description": "List active Leadtime task statuses so the agent can choose a valid status id.",
            "parameters": _object({"leadtimeSessionId": _string("Leadtime agent session id from the current prompt.")}, ["leadtimeSessionId"]),
        },
        handler=_list_task_statuses,
        description="List Leadtime task statuses.",
    )
    ctx.register_tool(
        name="leadtime_update_task_status",
        toolset="leadtime",
        schema={
            "name": "leadtime_update_task_status",
            "description": "Update the current Leadtime task or a specified task to a valid Leadtime status id.",
            "parameters": _object(
                {
                    "leadtimeSessionId": _string("Leadtime agent session id from the current prompt."),
                    "taskIdentifier": _string("Task UUID or short number. Defaults to the session task."),
                    "statusId": _string("Leadtime task status UUID."),
                },
                ["leadtimeSessionId", "statusId"],
            ),
        },
        handler=_update_task_status,
        description="Update a Leadtime task status.",
    )
    ctx.register_tool(
        name="leadtime_list_actions",
        toolset="leadtime",
        schema={
            "name": "leadtime_list_actions",
            "description": "Full mode only. List public Leadtime API operations discovered from the OpenAPI document.",
            "parameters": _object({"leadtimeSessionId": _string("Leadtime agent session id from the current prompt.")}, ["leadtimeSessionId"]),
        },
        handler=_list_actions,
        description="List Leadtime public API actions.",
    )
    ctx.register_tool(
        name="leadtime_action_details",
        toolset="leadtime",
        schema={
            "name": "leadtime_action_details",
            "description": "Full mode only. Get OpenAPI details for one Leadtime public API action.",
            "parameters": _object(
                {
                    "leadtimeSessionId": _string("Leadtime agent session id from the current prompt."),
                    "action": _string("operationId or 'METHOD /path'."),
                },
                ["leadtimeSessionId", "action"],
            ),
        },
        handler=_action_details,
        description="Inspect a Leadtime public API action.",
    )
    ctx.register_tool(
        name="leadtime_execute_action",
        toolset="leadtime",
        schema={
            "name": "leadtime_execute_action",
            "description": "Full mode only. Execute a Leadtime public API request by method and public path. Use action details first when unsure.",
            "parameters": _object(
                {
                    "leadtimeSessionId": _string("Leadtime agent session id from the current prompt."),
                    "method": _string("HTTP method."),
                    "path": _string("Public API path, for example /tasks/123."),
                    "body": {"description": "Optional JSON body."},
                },
                ["leadtimeSessionId", "method", "path"],
            ),
        },
        handler=_execute_action,
        description="Execute a Leadtime public API action.",
    )


def _get_session_context(args: dict, **kwargs) -> str:
    client, _binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    return json_text(client.get_session_context(_required(args, "leadtimeSessionId")))


def _read_task(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    return json_text(client.read_task(args.get("taskIdentifier") or binding.get("taskIdentifier") or binding.get("taskId")))


def _add_task_comment(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    return json_text(client.add_task_comment(args.get("taskIdentifier") or binding.get("taskIdentifier") or binding.get("taskId"), _required(args, "comment")))


def _list_task_statuses(args: dict, **kwargs) -> str:
    client, _binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    return json_text(client.list_task_statuses())


def _update_task_status(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    return json_text(client.update_task_status(args.get("taskIdentifier") or binding.get("taskIdentifier") or binding.get("taskId"), _required(args, "statusId")))


def _list_actions(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    _assert_full_mode(binding)
    return json_text(list_openapi_actions(client.get_openapi_document()))


def _action_details(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    _assert_full_mode(binding)
    action = find_openapi_action(client.get_openapi_document(), _required(args, "action"))
    if not action:
        raise ValueError("Leadtime API action not found")
    return json_text(action)


def _execute_action(args: dict, **kwargs) -> str:
    client, binding = resolve_client_and_binding(_required(args, "leadtimeSessionId"))
    _assert_full_mode(binding)
    return json_text(client.execute_action(_required(args, "method"), _required(args, "path"), args.get("body")))


def _assert_full_mode(binding: dict) -> None:
    if binding["bot"].mode != "full":
        raise ValueError("This Leadtime bot is configured in basic mode.")


def _required(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _string(description: str) -> dict:
    return {"type": "string", "description": description}


def _object(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _task_identifier_schema() -> dict:
    return _object(
        {
            "leadtimeSessionId": _string("Leadtime agent session id from the current prompt."),
            "taskIdentifier": _string("Task UUID or short number. Defaults to the session task."),
        },
        ["leadtimeSessionId"],
    )
