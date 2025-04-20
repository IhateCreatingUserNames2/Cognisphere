# cognisphere/mcpIntegration/mcp_manager.py
"""
Centralized MCP management for Cognisphere
Uses Python MCP SDK to handle all MCP server integration
"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

from google.adk.tools.tool_context import ToolContext
from google.adk.tools import BaseTool
from google.adk.tools.mcp_tool.mcp_tool import MCPTool

from app_globals import mcp_tools

logger = logging.getLogger(__name__)


class MCPManager:
    """
    Single unified manager for all MCP server connections and tool discovery.
    Uses Python MCP SDK for standardized integration.
    """

    def __init__(self):
        """Initialize the MCP Manager."""
        self.connected_servers = {}
        self.discovered_tools = []
        self.exit_stacks = {}

    async def discover_and_connect_servers(self, mcp_config: Dict[str, Dict[str, Any]]) -> List[BaseTool]:
        """
        Discover and connect to all configured MCP servers.

        Args:
            mcp_config: Dictionary of server configurations from claude_desktop_config.json or similar
                        Example: {"server_name": {"command": "python", "args": ["server.py"]}}

        Returns:
            List of ADK-compatible BaseTool objects representing all discovered MCP tools
        """
        all_tools = []

        for server_id, config in mcp_config.items():
            try:
                tools = await self.connect_to_server(
                    server_id=server_id,
                    command=config.get("command"),
                    args=config.get("args", []),
                    env=config.get("env", {})
                )
                all_tools.extend(tools)
                logger.info(f"Connected to server {server_id} with {len(tools)} tools")
            except Exception as e:
                logger.error(f"Failed to connect to server {server_id}: {e}")

        self.discovered_tools = all_tools
        return all_tools

    async def connect_to_server(
            self,
            server_id: str,
            command: str,
            args: List[str],
            env: Dict[str, str]
    ) -> List[BaseTool]:
        try:
            # Create a new exit stack for this connection
            exit_stack = AsyncExitStack()
            self.exit_stacks[server_id] = exit_stack

            # Configure connection parameters
            connection_params = StdioServerParameters(
                command=command,
                args=args,
                env=env
            )

            print(f"Attempting to connect to MCP server: {server_id}")

            # Use a timeout for connecting to the server
            read_stream, write_stream = await asyncio.wait_for(
                stdio_client(connection_params).__aenter__(),
                timeout=10.0
            )
            # guarantee entry/exit do stdio_client e ClientSession ocorram no mesmo escopo
            read_stream, write_stream = await exit_stack.enter_async_context(
                stdio_client(connection_params)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Inicializa a sessão (timeout opcional)
            await asyncio.wait_for(session.initialize(), timeout=5.0)
            # Lista as ferramentas MCP (timeout opcional)
            raw_tools = await asyncio.wait_for(session.list_tools(), timeout=5.0)
            tools_list = raw_tools.tools if hasattr(raw_tools, "tools") else raw_tools

            adk_tools = []
            for mcp_tool in tools_list:
                try:
                    if isinstance(mcp_tool, tuple):
                        print(f"Tool tuple format: {mcp_tool}")
                        if len(mcp_tool) >= 2:
                            name = mcp_tool[0]
                            description = mcp_tool[1]
                            params = mcp_tool[2] if len(mcp_tool) > 2 else {}
                            from mcp.types import Tool as McpTool
                            proper_tool = McpTool(name=name, description=description, inputSchema=params)
                            tool = MCPTool(mcp_tool=proper_tool, mcp_session=session)
                            tool.server_id = server_id
                            adk_tools.append(tool)
                    elif hasattr(mcp_tool, 'name'):
                        tool = MCPTool(mcp_tool=mcp_tool, mcp_session=session)
                        tool.server_id = server_id
                        adk_tools.append(tool)
                    else:
                        print(f"Skipping unsupported tool format: {type(mcp_tool)}")
                except Exception as tool_error:
                    print(f"Error creating MCPTool: {tool_error}")
                    import traceback
                    traceback.print_exc()
                    continue
            # ──────────────────────────────────────────────────────────────

            # Store the connection in our registry
            self.connected_servers[server_id] = {
                "exit_stack": exit_stack,
                "tools": adk_tools,
                "session": session
            }

            print(
                f"Successfully connected to server {server_id} with "
                f"{len(adk_tools)} tools"
            )
            return adk_tools

        except asyncio.TimeoutError:
            print(f"Timeout connecting to MCP server: {server_id}")
            await exit_stack.aclose()
            raise ValueError(f"Timeout connecting to MCP server: {server_id}")
        except Exception as e:
            print(f"Error connecting to MCP server: {server_id}: {e}")
            import traceback
            traceback.print_exc()

            # Clean up resources
            if server_id in self.exit_stacks:
                try:
                    await self.exit_stacks[server_id].aclose()
                    del self.exit_stacks[server_id]
                except Exception as cleanup_error:
                    print(f"Error during cleanup: {cleanup_error}")

            raise

    async def close_server(self, server_id: str):
        """
        Close connection to an MCP server.

        Args:
            server_id: Server identifier
        """
        if server_id in self.exit_stacks:
            try:
                await self.exit_stacks[server_id].aclose()
                del self.exit_stacks[server_id]
            except Exception as e:
                logger.error(f"Error closing connection to MCP server {server_id}: {e}")

        if server_id in self.connected_servers:
            del self.connected_servers[server_id]

    async def close_all(self):
        """Close all MCP server connections."""
        for server_id in list(self.exit_stacks.keys()):
            await self.close_server(server_id)

    def get_tool_by_name(self, server_id: str, tool_name: str) -> Optional[BaseTool]:
        """
        Get a specific tool from a connected server by name.

        Args:
            server_id: ID of the server
            tool_name: Name of the tool to find

        Returns:
            The tool if found, None otherwise
        """
        if server_id in self.connected_servers:
            server_tools = self.connected_servers[server_id].get("tools", [])
            for tool in server_tools:
                if tool.name == tool_name:
                    return tool
        return None

    def get_all_tools(self) -> List[BaseTool]:
        """
        Get all tools from all connected MCP servers.

        Returns:
            List of all available tools
        """
        all_tools = []
        for server_id, server in self.connected_servers.items():
            all_tools.extend(server.get("tools", []))
        return all_tools

    async def execute_tool(
            self,
            server_id: str,
            tool_name: str,
            arguments: Dict[str, Any],
            tool_context: ToolContext | None = None,
    ):
        """
        Executa uma ferramenta MCP já conectada.

        Args:
            server_id:  ID do servidor MCP
            tool_name:  Nome exato da tool
            arguments:  Dict de argumentos para a tool
            tool_context: ToolContext opcional (cria mínimo se None)

        Returns:
            Resultado devolvido por tool.run_async()
        """
        tool = self.get_tool_by_name(server_id, tool_name)
        if tool is None:
            raise ValueError(f"Tool '{tool_name}' não encontrada em '{server_id}'")

        if tool_context is None:
            tool_context = ToolContext(agent_name="orchestrator", state={}, session=None)

        return await tool.run_async(args=arguments, tool_context=tool_context)


    def get_server_tools(self, server_id: str):
        """
        Convenience helper – devolve a lista de ferramentas do servidor
        ou [] se o servidor não estiver conectado.
        """
        return self.connected_servers.get(server_id, {}).get("tools", [])