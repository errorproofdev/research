from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .auth import (
    ApprovalAuthority,
    ApprovalDenied,
    AuthorizationContext,
    AuthorizationDenied,
    arguments_hash,
)


class InvalidToolArguments(ValueError):
    pass


class ApprovalRequired(ValueError):
    def __init__(self, tool: str, arguments: dict[str, Any]):
        super().__init__("approval_required")
        self.tool = tool
        self.arguments_sha256 = arguments_hash(arguments)


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    required_scope: str
    approval_required: bool
    handler: Callable[[dict[str, Any]], Any]

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": not self.approval_required,
                "destructiveHint": False,
                "openWorldHint": self.approval_required,
            },
            "_meta": {
                "io.errorproofdev/requiredScope": self.required_scope,
                "io.errorproofdev/approvalRequired": self.approval_required,
            },
        }


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    if not isinstance(arguments, dict):
        raise InvalidToolArguments("arguments_must_be_object")
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    missing = required - set(arguments)
    if missing:
        raise InvalidToolArguments(f"missing_arguments:{','.join(sorted(missing))}")
    if schema.get("additionalProperties") is False:
        extra = set(arguments) - set(properties)
        if extra:
            raise InvalidToolArguments(f"unknown_arguments:{','.join(sorted(extra))}")
    python_types = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list}
    for name, value in arguments.items():
        expected_name = properties.get(name, {}).get("type")
        expected = python_types.get(expected_name)
        if expected and (not isinstance(value, expected) or expected is int and isinstance(value, bool)):
            raise InvalidToolArguments(f"invalid_type:{name}:{expected_name}")


class ToolRegistry:
    def __init__(self, tools: list[Tool], approvals: ApprovalAuthority):
        self.tools = {tool.name: tool for tool in tools}
        self.approvals = approvals

    def list_for(self, context: AuthorizationContext) -> list[dict[str, Any]]:
        return [
            tool.descriptor()
            for tool in self.tools.values()
            if tool.required_scope in context.scopes
        ]

    def call(self, name: str, arguments: dict[str, Any], context: AuthorizationContext) -> Any:
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError(name)
        if tool.required_scope not in context.scopes:
            raise AuthorizationDenied("insufficient_scope")
        validate_arguments(tool.input_schema, arguments)
        if tool.approval_required:
            if not context.approval_token:
                raise ApprovalRequired(name, arguments)
            try:
                self.approvals.consume(context.approval_token, context.subject, name, arguments)
            except ApprovalDenied:
                raise
        return tool.handler(arguments)
