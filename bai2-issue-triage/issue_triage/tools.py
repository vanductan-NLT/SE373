"""Application-owned tool schema, validation and execution."""

import json
from typing import Any

COMPONENT_OWNERS = {
    "payment": "checkout-platform",
    "identity": "identity-platform",
    "search": "search-platform",
}
GET_COMPONENT_OWNER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_component_owner",
        "description": "Trả team chịu trách nhiệm cho software component đã biết.",
        "parameters": {
            "type": "object",
            "properties": {"component": {"type": "string", "enum": list(COMPONENT_OWNERS)}},
            "required": ["component"],
            "additionalProperties": False,
        },
    },
}


class ToolValidationError(ValueError):
    pass


def parse_tool_arguments(name: str, raw_arguments: str) -> dict[str, str]:
    if name != "get_component_owner":
        raise ToolValidationError(f"Tool không được phép: {name}")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        raise ToolValidationError("Tool arguments không phải JSON hợp lệ") from error
    if not isinstance(arguments, dict):
        raise ToolValidationError("Tool arguments phải là JSON object")
    if set(arguments) != {"component"}:
        raise ToolValidationError("Tool chỉ được có đúng argument component")
    component = arguments["component"]
    if not isinstance(component, str):
        raise ToolValidationError("component phải là string")
    if component not in COMPONENT_OWNERS:
        raise ToolValidationError(f"Component không được phép: {component}")
    return {"component": component}


def execute_tool_call(name: str, raw_arguments: str) -> tuple[dict[str, str], dict[str, str]]:
    arguments = parse_tool_arguments(name, raw_arguments)
    component = arguments["component"]
    return arguments, {"component": component, "owner": COMPONENT_OWNERS[component]}
