from __future__ import annotations

import json
import os
import sys

from .auth import ApprovalAuthority, AuthorizationContext
from .protocol import MCPServer
from .tools import Tool, ToolRegistry


def search_sources(arguments: dict) -> dict:
    query = arguments["query"].lower()
    corpus = [
        {"id": "S1", "title": "Agent memory", "text": "Durable agent state needs replayable events."},
        {"id": "S2", "title": "MCP safety", "text": "Sensitive tools should require user approval."},
    ]
    matches = [item for item in corpus if query in (item["title"] + " " + item["text"]).lower()]
    return {"matches": matches[: arguments.get("limit", 5)]}


def queue_safe_fetch(arguments: dict) -> dict:
    return {"url": arguments["url"], "status": "approved_for_safe_fetch"}


def create_server(secret: bytes, approval_state: str | None = None) -> MCPServer:
    approvals = ApprovalAuthority(secret, consumed_path=approval_state)
    tools = [
        Tool(
            name="research_search",
            title="Search research sources",
            description="Search already-ingested research sources.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            required_scope="research:read",
            approval_required=False,
            handler=search_sources,
        ),
        Tool(
            name="research_fetch",
            title="Fetch an external research source",
            description="Queue a URL for the SSRF-safe fetch boundary after explicit approval.",
            input_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
            required_scope="research:fetch",
            approval_required=True,
            handler=queue_safe_fetch,
        ),
    ]
    return MCPServer(ToolRegistry(tools, approvals))


def main() -> None:
    raw_secret = os.environ.get("RESEARCH_AGENT_MCP_SECRET")
    if not raw_secret or len(raw_secret.encode()) < 32:
        raise SystemExit("RESEARCH_AGENT_MCP_SECRET must contain at least 32 bytes")
    context = AuthorizationContext(
        subject=os.environ.get("RESEARCH_AGENT_MCP_SUBJECT", "local-user"),
        scopes=frozenset(filter(None, os.environ.get("RESEARCH_AGENT_MCP_SCOPES", "research:read").split(","))),
    )
    server = create_server(
        raw_secret.encode(),
        approval_state=os.environ.get("RESEARCH_AGENT_MCP_APPROVAL_STATE", ".research-agent-mcp-approvals.json"),
    )
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = server.handle(request, context)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
