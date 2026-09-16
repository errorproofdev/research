from __future__ import annotations

from research_agent_mcp.auth import ApprovalAuthority, AuthorizationContext
from research_agent_mcp.protocol import MCPServer, PROTOCOL_VERSION
from research_agent_mcp.tools import Tool, ToolRegistry

SECRET = b"deterministic-test-secret-32-bytes-minimum"


def request(method, params=None, request_id=1, approval_token=None):
    params = dict(params or {})
    metadata = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1"},
    }
    if approval_token:
        metadata["io.errorproofdev/approvalToken"] = approval_token
    params["_meta"] = metadata
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def make_server(clock=lambda: 1_000, consumed_path=None):
    effects = []
    authority = ApprovalAuthority(SECRET, clock=clock, consumed_path=consumed_path)
    tools = [
        Tool(
            "research_search", "Search", "Search stored sources",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
            "research:read", False, lambda args: {"query": args["query"]},
        ),
        Tool(
            "research_fetch", "Fetch", "Fetch an external URL",
            {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False},
            "research:fetch", True, lambda args: effects.append(args["url"]) or {"queued": args["url"]},
        ),
        Tool(
            "broken_tool", "Broken", "Always fails",
            {"type": "object", "properties": {}, "additionalProperties": False},
            "research:read", False, lambda args: (_ for _ in ()).throw(RuntimeError("secret-internal-detail")),
        ),
    ]
    return MCPServer(ToolRegistry(tools, authority)), authority, effects


def test_tools_list_is_filtered_by_scope():
    server, _, _ = make_server()
    context = AuthorizationContext("alice", frozenset({"research:read"}))
    response = server.handle(request("tools/list"), context)
    assert [tool["name"] for tool in response["result"]["tools"]] == ["research_search", "broken_tool"]


def test_read_tool_executes_without_approval():
    server, _, _ = make_server()
    context = AuthorizationContext("alice", frozenset({"research:read"}))
    response = server.handle(request("tools/call", {"name": "research_search", "arguments": {"query": "MCP"}}), context)
    assert response["result"]["structuredContent"] == {"query": "MCP"}


def test_missing_scope_is_denied_even_for_known_tool():
    server, _, _ = make_server()
    response = server.handle(
        request("tools/call", {"name": "research_fetch", "arguments": {"url": "https://example.com"}}),
        AuthorizationContext("alice", frozenset({"research:read"})),
    )
    assert response["error"]["code"] == -32001


def test_sensitive_tool_returns_argument_bound_approval_request():
    server, _, effects = make_server()
    context = AuthorizationContext("alice", frozenset({"research:fetch"}))
    response = server.handle(
        request("tools/call", {"name": "research_fetch", "arguments": {"url": "https://example.com"}}), context
    )
    assert response["error"]["code"] == -32002
    assert response["error"]["data"]["tool"] == "research_fetch"
    assert len(response["error"]["data"]["argumentsSha256"]) == 64
    assert effects == []


def test_valid_approval_executes_once_and_replay_is_denied():
    server, authority, effects = make_server()
    context = AuthorizationContext("alice", frozenset({"research:fetch"}))
    arguments = {"url": "https://example.com"}
    token = authority.issue("alice", "research_fetch", arguments, nonce="once")
    call = request("tools/call", {"name": "research_fetch", "arguments": arguments}, approval_token=token)
    assert server.handle(call, context)["result"]["structuredContent"]["queued"] == arguments["url"]
    replay = server.handle(call, context)
    assert replay["error"]["data"]["reason"] == "approval_already_used"
    assert effects == [arguments["url"]]


def test_approval_replay_is_denied_after_restart(tmp_path):
    ledger = tmp_path / "consumed.json"
    server, authority, _ = make_server(consumed_path=ledger)
    context = AuthorizationContext("alice", frozenset({"research:fetch"}))
    arguments = {"url": "https://example.com"}
    token = authority.issue("alice", "research_fetch", arguments, nonce="survives-restart")
    call = request("tools/call", {"name": "research_fetch", "arguments": arguments}, approval_token=token)
    assert "result" in server.handle(call, context)

    restarted, _, effects = make_server(consumed_path=ledger)
    replay = restarted.handle(call, context)
    assert replay["error"]["data"]["reason"] == "approval_already_used"
    assert effects == []


def test_approval_is_bound_to_subject_tool_and_arguments():
    server, authority, effects = make_server()
    original = {"url": "https://example.com"}
    token = authority.issue("alice", "research_fetch", original, nonce="bound")
    changed = {"url": "https://attacker.example"}
    response = server.handle(
        request("tools/call", {"name": "research_fetch", "arguments": changed}, approval_token=token),
        AuthorizationContext("alice", frozenset({"research:fetch"})),
    )
    assert response["error"]["data"]["reason"] == "approval_arguments_changed"
    assert effects == []


def test_expired_approval_is_denied():
    now = [1_000]
    server, authority, _ = make_server(clock=lambda: now[0])
    arguments = {"url": "https://example.com"}
    token = authority.issue("alice", "research_fetch", arguments, ttl_seconds=1, nonce="expired")
    now[0] = 1_001
    response = server.handle(
        request("tools/call", {"name": "research_fetch", "arguments": arguments}, approval_token=token),
        AuthorizationContext("alice", frozenset({"research:fetch"})),
    )
    assert response["error"]["data"]["reason"] == "approval_expired"


def test_protocol_metadata_and_schema_are_enforced():
    server, _, _ = make_server()
    context = AuthorizationContext("alice", frozenset({"research:read"}))
    missing_meta = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert server.handle(missing_meta, context)["error"]["code"] == -32602
    invalid_args = request("tools/call", {"name": "research_search", "arguments": {"query": 42}})
    assert server.handle(invalid_args, context)["error"]["data"]["reason"] == "invalid_type:query:string"
    unknown = server.handle(request("prompts/list"), context)
    assert unknown["error"]["code"] == -32601


def test_tool_failures_are_sanitized_and_audited():
    server, _, _ = make_server()
    context = AuthorizationContext("alice", frozenset({"research:read"}))
    response = server.handle(request("tools/call", {"name": "broken_tool", "arguments": {}}), context)
    assert response["error"] == {"code": -32000, "message": "Tool execution failed"}
    assert "secret-internal-detail" not in str(response)
    assert server.audit_log[-1]["tool"] == "broken_tool"
    assert server.audit_log[-1]["outcome"] == "Tool execution failed"
