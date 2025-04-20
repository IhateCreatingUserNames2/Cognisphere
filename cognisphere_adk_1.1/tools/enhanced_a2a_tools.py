# cognisphere_adk/tools/enhanced_a2a_tools.py

import asyncio
from typing import Dict, Any, List, Optional
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

# Remove the old globals; instead, take adapters as parameters:
def make_a2a_and_mcp_tools(
    a2a_adapter,  # instance of MCPA2AAdapter
    mcp_adapter   # instance of MCPAdapter
) -> List[FunctionTool]:
    async def connect_to_agent(
        url: str,
        query: str,
        tool_context: ToolContext = None
    ) -> Dict[str, Any]:
        if not url.startswith(("http://", "https://", "mcp://")):
            url = f"mcp://{url}"
        return await a2a_adapter.connect_to_agent(url, query)

    async def discover_agents(
        urls: Optional[List[str]] = None,
        tool_context: ToolContext = None
    ) -> Dict[str, Any]:
        urls = urls or []
        return await a2a_adapter.discover_a2a_agents(urls)

    async def list_mcp_tools(
        server_id: Optional[str] = None,
        tool_context: ToolContext = None
    ) -> Dict[str, Any]:
        result = await mcp_adapter.get_all_tools()
        if server_id and result.get("status") == "success":
            tools = [t for t in result["tools"] if t["server_id"] == server_id]
            return {"status": "success", "tools": tools, "count": len(tools)}
        return result

    async def call_mcp_tool(
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_context: ToolContext = None
    ) -> Dict[str, Any]:
        return await mcp_adapter.call_tool(server_id, tool_name, arguments)

    return [
        FunctionTool(connect_to_agent),
        FunctionTool(discover_agents),
        FunctionTool(list_mcp_tools),
        FunctionTool(call_mcp_tool),
    ]
