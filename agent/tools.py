"""
agent/tools.py — superseded by agent/mcp_server.py.

Tool implementations have moved to the MCP server (agent/mcp_server.py),
which exposes them over the Model Context Protocol (SSE).
The agent (agent/agent.py) now discovers and calls tools via MCP client session
rather than importing from this module directly.

This file is kept for reference only.
"""
