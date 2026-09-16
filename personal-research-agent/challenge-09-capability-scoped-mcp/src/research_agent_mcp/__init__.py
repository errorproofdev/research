"""Capability-scoped MCP boundary for the personal research agent."""

from .auth import ApprovalAuthority, AuthorizationContext
from .protocol import MCPServer
from .tools import Tool, ToolRegistry

__all__ = ["ApprovalAuthority", "AuthorizationContext", "MCPServer", "Tool", "ToolRegistry"]
