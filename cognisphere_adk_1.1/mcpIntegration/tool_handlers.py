# cognisphere/mcpIntegration/tool_handlers.py
"""
Function-based MCP tool handlers for Cognisphere.
These serve as intermediaries between the Orchestrator and the MCP tools.
"""

import asyncio
from typing import Dict, Any, List, Optional
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext

# ✅ Use the global mcp_manager already initialized in app.py
import app_globals
mcp_manager = app_globals.mcp_manager


async def list_mcp_tools(server_id: Optional[str] = None, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    List available MCP tools, optionally filtered by server.

    Args:
        server_id: Optional server ID to filter tools
        tool_context: Tool context

    Returns:
        Dictionary with available tools
    """
    # Get all tools
    if server_id:
        if server_id in mcp_manager.connected_servers:
            tools = mcp_manager.connected_servers[server_id].get("tools", [])
        else:
            return {
                "status": "error",
                "message": f"Server '{server_id}' not connected",
                "tools": [],
                "count": 0
            }
    else:
        tools = mcp_manager.get_all_tools()

    # Convert to response format with name-based matching for server_id
    tool_list = [
        {
            "name": tool.name,
            "description": tool.description,
            "server_id": next(
                (sid for sid, srv in mcp_manager.connected_servers.items()
                 if any(t.name == tool.name for t in srv.get("tools", []))),
                "unknown"
            ),
            "is_long_running": getattr(tool, "is_long_running", False)
        }
        for tool in tools
    ]

    return {
        "status": "success",
        "tools": tool_list,
        "count": len(tool_list)
    }


async def call_mcp_tool(
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Call a specific MCP tool.

    Args:
        server_id: ID of the MCP server
        tool_name: Name of the tool to call
        arguments: Arguments for the tool
        tool_context: Tool context

    Returns:
        Tool execution result
    """
    try:
        # Create a minimal tool context if none provided
        if tool_context is None:
            tool_context = ToolContext(
                agent_name="orchestrator",
                state={},
                session=None
            )

        # Find the tool
        tool = mcp_manager.get_tool_by_name(server_id, tool_name)
        if not tool:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not found in server '{server_id}'"
            }


        # Call the tool inside a task to ensure timeout context is valid
        result = await asyncio.create_task(tool.run_async(args=arguments, tool_context=tool_context))

        return {
            "status": "success",
            "server_id": server_id,
            "tool_name": tool_name,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error calling tool: {str(e)}"
        }


# Create FunctionTools for use in agents
list_mcp_tools_tool = FunctionTool(list_mcp_tools)
call_mcp_tool_tool = FunctionTool(call_mcp_tool)

# List of all MCP tools
mcp_function_tools = [
    list_mcp_tools_tool,
    call_mcp_tool_tool
]