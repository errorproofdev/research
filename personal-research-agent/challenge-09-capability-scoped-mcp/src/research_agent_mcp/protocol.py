from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from .auth import ApprovalDenied, AuthorizationContext, AuthorizationDenied, arguments_hash
from .tools import ApprovalRequired, InvalidToolArguments, ToolRegistry

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "personal-research-agent", "version": "0.9.0"}


class ProtocolProblem(ValueError):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class MCPServer:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.audit_log: list[dict[str, Any]] = []

    @staticmethod
    def _result(request_id: str | int, result: dict[str, Any]) -> dict[str, Any]:
        result.setdefault("_meta", {})["io.modelcontextprotocol/serverInfo"] = SERVER_INFO
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, problem: ProtocolProblem) -> dict[str, Any]:
        error: dict[str, Any] = {"code": problem.code, "message": problem.message}
        if problem.data is not None:
            error["data"] = problem.data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    @staticmethod
    def _validate(request: Any) -> tuple[str | int, str, dict[str, Any], dict[str, Any]]:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            raise ProtocolProblem(-32600, "Invalid Request")
        request_id = request.get("id")
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            raise ProtocolProblem(-32600, "Invalid Request")
        method = request.get("method")
        params = request.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            raise ProtocolProblem(-32600, "Invalid Request")
        metadata = params.get("_meta")
        if not isinstance(metadata, dict):
            raise ProtocolProblem(-32602, "Missing request metadata")
        if metadata.get("io.modelcontextprotocol/protocolVersion") != PROTOCOL_VERSION:
            raise ProtocolProblem(-32602, "Unsupported protocol version")
        if not isinstance(metadata.get("io.modelcontextprotocol/clientCapabilities"), dict):
            raise ProtocolProblem(-32602, "Missing client capabilities")
        return request_id, method, params, metadata

    def handle(self, request: Any, context: AuthorizationContext) -> dict[str, Any]:
        request_id = request.get("id") if isinstance(request, dict) else None
        method = "invalid"
        tool_name: str | None = None
        args_digest: str | None = None
        outcome = "protocol_error"
        try:
            request_id, method, params, metadata = self._validate(request)
            if method == "tools/list":
                outcome = "allowed"
                return self._result(request_id, {"tools": self.registry.list_for(context)})
            if method != "tools/call":
                raise ProtocolProblem(-32601, "Method not found")

            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(tool_name, str) or not isinstance(arguments, dict):
                raise ProtocolProblem(-32602, "Invalid tool call parameters")
            args_digest = arguments_hash(arguments)
            approval_token = metadata.get("io.errorproofdev/approvalToken")
            call_context = replace(context, approval_token=approval_token)
            try:
                structured = self.registry.call(tool_name, arguments, call_context)
            except KeyError as exc:
                raise ProtocolProblem(-32602, "Unknown tool") from exc
            except InvalidToolArguments as exc:
                raise ProtocolProblem(-32602, "Invalid tool arguments", {"reason": str(exc)}) from exc
            except AuthorizationDenied as exc:
                raise ProtocolProblem(-32001, "Authorization denied", {"reason": str(exc)}) from exc
            except ApprovalRequired as exc:
                raise ProtocolProblem(
                    -32002,
                    "Approval required",
                    {"tool": exc.tool, "argumentsSha256": exc.arguments_sha256},
                ) from exc
            except ApprovalDenied as exc:
                raise ProtocolProblem(-32003, "Approval denied", {"reason": str(exc)}) from exc
            except Exception as exc:
                raise ProtocolProblem(-32000, "Tool execution failed") from exc

            outcome = "allowed"
            return self._result(request_id, {
                "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
                "structuredContent": structured,
                "isError": False,
            })
        except ProtocolProblem as problem:
            outcome = problem.message
            return self._error(request_id, problem)
        finally:
            self.audit_log.append({
                "subject": context.subject,
                "method": method,
                "tool": tool_name,
                "arguments_sha256": args_digest,
                "outcome": outcome,
            })
