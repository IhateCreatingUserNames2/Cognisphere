# cognisphere_adk/mcpIntegration/mcp_manager.py
"""
Centralized MCP management for Cognisphere
Uses Python MCP SDK to handle all MCP server integration
"""

import os
import asyncio
import logging
import traceback
from typing import Dict, Any, List, Optional, Tuple


from mcp import ClientSession, StdioServerParameters, types as mcp_sdk_types
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# ADK specific imports
from google.adk.tools.tool_context import ToolContext
from google.adk.tools import BaseTool
from google.adk.tools.mcp_tool.mcp_tool import MCPTool

# Configure logger for this module
logger = logging.getLogger(__name__)


class MCPManager:
    """
    Single unified manager for all MCP server connections and tool discovery.
    Uses Python MCP SDK for standardized integration.
    """

    def __init__(self):
        """Initialize the MCP Manager."""
        self.connected_servers: Dict[str, Dict[str, Any]] = {}
        self.discovered_tools: List[BaseTool] = []
        self.exit_stacks: Dict[str, AsyncExitStack] = {}
        # Lazy load server_manager to avoid circular import issues at module load time
        self._server_manager_instance = None

    @property
    def server_manager(self):
        if self._server_manager_instance is None:
            from mcpIntegration.server_installer import MCPServerManager
            self._server_manager_instance = MCPServerManager()
        return self._server_manager_instance

    async def discover_and_connect_servers(self, mcp_server_configs: List[Dict[str, Any]]) -> List[BaseTool]:
        """
        Discover and connect to all configured MCP servers.

        Args:
            mcp_server_configs: List of server configuration dictionaries.
                                Each dict should have "id", "command", "args", "env".

        Returns:
            List of ADK-compatible BaseTool objects representing all discovered MCP tools.
        """
        all_adk_tools: List[BaseTool] = []
        logger.info(f"Discovering and connecting to {len(mcp_server_configs)} MCP server(s).")

        for server_config in mcp_server_configs:
            server_id = server_config.get("id")
            if not server_id:
                logger.warning(f"Skipping server config with no ID: {server_config.get('name', 'Unknown')}")
                continue

            try:
                logger.debug(f"Processing server config for ID: {server_id}")
                # Pass the whole config to connect_to_server
                adk_tools_from_server = await self.connect_to_server(
                    server_id=server_id,
                    server_config_from_registry=server_config
                )
                if adk_tools_from_server:  # Ensure it's not None or empty before extending
                    all_adk_tools.extend(adk_tools_from_server)
                logger.info(
                    f"Successfully processed server {server_id}, found {len(adk_tools_from_server or [])} tools.")
            except Exception as e:
                logger.error(f"Failed to connect or process server {server_id}: {e}", exc_info=True)

        self.discovered_tools = all_adk_tools
        logger.info(f"MCP discovery complete. Total ADK-wrapped MCP tools discovered: {len(all_adk_tools)}")
        return all_adk_tools

    async def connect_to_server(
            self,
            server_id: str,
            command: Optional[str] = None,
            args: Optional[List[str]] = None,
            env: Optional[Dict[str, str]] = None,
            server_config_from_registry: Optional[Dict[str, Any]] = None
    ) -> List[BaseTool]:
        """
        Connect to an MCP server with comprehensive error handling and resource management.
        Uses server_config_from_registry if command/args/env are not directly provided.

        Args:
            server_id: Server identifier.
            command: Optional command to launch the server (overrides registry config).
            args: Optional arguments for the server (overrides registry config).
            env: Optional environment variables (merged with registry config).
            server_config_from_registry: Full configuration dictionary from the registry.

        Returns:
            List of ADK tools provided by this server.
        """
        # Ensure BaseTool from ADK is used
        from google.adk.tools import BaseTool as ADKBaseTool

        # Close existing connection if any
        if server_id in self.connected_servers:
            logger.info(f"Server {server_id} already has an active or pending connection. Closing first.")
            try:
                await self.close_server(server_id)
            except Exception as close_error:
                logger.warning(f"Error closing existing connection for {server_id}: {close_error}", exc_info=True)

        exit_stack = AsyncExitStack()
        # Important: Store the exit_stack immediately so close_server can use it even if connection fails midway
        self.exit_stacks[server_id] = exit_stack

        try:
            _command: Optional[str] = command
            _args: List[str] = args if args is not None else []
            _env: Dict[str, str] = env if env is not None else {}

            if server_config_from_registry:
                if _command is None: _command = server_config_from_registry.get("command")
                if not _args: _args = server_config_from_registry.get("args",
                                                                      [])  # Only use registry if not directly provided
                # Merge env: direct params override registry, which overrides system env
                merged_env = {**os.environ, **server_config_from_registry.get("env", {}), **_env}
                _env = merged_env
            else:  # If no registry config, use direct params and system env
                _env = {**os.environ, **_env}

            if not _command:
                raise ValueError(f"No command specified for MCP server: {server_id}")

            # Standard MCP environment variables
            _env.setdefault("MCP_CONNECTION_TIMEOUT", "30")
            _env.setdefault("MCP_KEEP_ALIVE", "true")

            connection_params = StdioServerParameters(command=_command, args=_args, env=_env)
            logger.info(f"Attempting to connect to MCP server: {server_id}")
            logger.debug(f"Connection parameters for {server_id}: {connection_params}")

            # stdio_client itself is an async context manager.
            # We enter it using the exit_stack to ensure its __aexit__ is called.
            # It yields a tuple of (read_stream, write_stream).
            streams = await exit_stack.enter_async_context(stdio_client(connection_params))
            read_stream, write_stream = streams

            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            await asyncio.wait_for(session.initialize(), timeout=30.0)  # Increased timeout
            logger.debug(f"Session initialized for {server_id}.")

            raw_tools_response = await asyncio.wait_for(session.list_tools(), timeout=30.0)  # Increased timeout
            logger.debug(f"Raw tools response from {server_id}: {raw_tools_response}")

            mcp_tools_list = []
            if isinstance(raw_tools_response, list):
                mcp_tools_list = raw_tools_response
            elif hasattr(raw_tools_response, 'tools') and isinstance(raw_tools_response.tools, list):
                mcp_tools_list = raw_tools_response.tools
            elif raw_tools_response is None:  # Handle case where server returns no tools
                logger.info(f"Server {server_id} reported no tools (list_tools returned None).")
            else:
                logger.warning(f"Unexpected tools response format from {server_id}: {type(raw_tools_response)}")

            adk_tools: List[ADKBaseTool] = []
            for mcp_tool_data in mcp_tools_list:
                try:
                    proper_mcp_tool: Optional[mcp_sdk_types.Tool] = None
                    if isinstance(mcp_tool_data, mcp_sdk_types.Tool):
                        proper_mcp_tool = mcp_tool_data
                    elif isinstance(mcp_tool_data, dict):
                        proper_mcp_tool = mcp_sdk_types.Tool(
                            name=mcp_tool_data.get("name", f"UnnamedTool_{server_id}_{len(adk_tools)}"),
                            description=mcp_tool_data.get("description", ""),
                            inputSchema=mcp_tool_data.get("inputSchema", mcp_tool_data.get("parameters", {}))
                        )
                    else:
                        logger.warning(
                            f"Skipping tool with unrecognized data type: {type(mcp_tool_data)} for server {server_id}")
                        continue

                    if proper_mcp_tool:
                        tool = MCPTool(mcp_tool=proper_mcp_tool, mcp_session=session)
                        setattr(tool, 'server_id', server_id)  # Dynamically add server_id attribute
                        adk_tools.append(tool)

                except Exception as tool_creation_error:
                    tool_name_for_log = getattr(mcp_tool_data, 'name', str(mcp_tool_data))
                    logger.error(
                        f"Error creating ADK MCPTool for '{tool_name_for_log}' from {server_id}: {tool_creation_error}",
                        exc_info=True)

            connection_metadata = {
                "exit_stack": exit_stack,
                "tools": adk_tools,
                "session": session,
                "connection_params": connection_params.model_dump(),  # For Pydantic models
                "connected_at": asyncio.get_event_loop().time(),
                "status": "connected"
            }
            self.connected_servers[server_id] = connection_metadata
            logger.info(f"Successfully connected to server {server_id} with {len(adk_tools)} ADK tools.")
            return adk_tools

        except asyncio.TimeoutError:
            logger.error(f"Timeout during connection or operation with MCP server: {server_id}", exc_info=True)
            # Ensure exit_stack is closed if it was created for this attempt
            if server_id in self.exit_stacks:
                await self.exit_stacks[server_id].aclose()
                del self.exit_stacks[server_id]  # Remove it as it's now closed
            if server_id in self.connected_servers:  # Should not happen if timeout before storing
                del self.connected_servers[server_id]
            raise ValueError(f"Timeout connecting to MCP server: {server_id}")
        except Exception as e:
            logger.error(f"Generic error connecting to MCP server {server_id}: {e}", exc_info=True)
            if server_id in self.exit_stacks:
                await self.exit_stacks[server_id].aclose()
                del self.exit_stacks[server_id]
            if server_id in self.connected_servers:
                del self.connected_servers[server_id]
            raise

    async def close_server(self, server_id: str):
        """
        Close connection to an MCP server.
        """
        logger.info(f"Attempting to close connection to server {server_id}...")
        if server_id in self.exit_stacks:
            exit_stack_to_close = self.exit_stacks.pop(server_id)  # Remove before closing
            try:
                await exit_stack_to_close.aclose()
                logger.info(f"Successfully closed exit_stack for server {server_id}.")
            except Exception as e:
                logger.error(f"Error closing exit_stack for MCP server {server_id}: {e}", exc_info=True)
        else:
            logger.warning(f"No active exit_stack found for server {server_id} to close.")

        if server_id in self.connected_servers:
            del self.connected_servers[server_id]
            logger.info(f"Connection info for server {server_id} removed from registry.")

    async def close_all(self):
        """Close all MCP server connections."""
        logger.info("Closing all MCP server connections...")
        server_ids_to_close = list(self.connected_servers.keys())  # Iterate over a copy
        for server_id in server_ids_to_close:
            await self.close_server(server_id)
        logger.info("All MCP server connections processed for closure.")

    def get_tool_by_name(self, server_id: str, tool_name: str) -> Optional[BaseTool]:
        """Get a specific tool from a connected server by name."""
        server_info = self.connected_servers.get(server_id)
        if server_info:
            for tool in server_info.get("tools", []):
                if tool.name == tool_name:
                    return tool
        logger.warning(f"Tool '{tool_name}' not found on server '{server_id}'.")
        return None

    def get_all_tools(self) -> List[BaseTool]:
        """Get all tools from all connected MCP servers."""
        all_tools = []
        for server_info in self.connected_servers.values():
            all_tools.extend(server_info.get("tools", []))
        return all_tools

    async def check_connection_health(self, server_id: str) -> bool:
        """Check if a server connection is healthy."""
        server_info = self.connected_servers.get(server_id)
        if not server_info or server_info.get("status") != "connected":
            return False

        session = server_info.get("session")
        if not session:
            return False

        try:
            await asyncio.wait_for(session.list_tools(), timeout=10.0)
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed for server {server_id}: {e}")
            # Optionally, mark server as unhealthy or attempt to reconnect
            # server_info["status"] = "unhealthy"
            return False

    async def execute_tool(
            self,
            server_id: str,
            tool_name: str,
            arguments: Dict[str, Any],
            tool_context: Optional[ToolContext] = None,
    ) -> Any:
        """Execute an MCP tool with reconnection logic."""
        MAX_RETRIES = 2
        RETRY_DELAY = 3  # seconds
        TOOL_EXEC_TIMEOUT = 60.0  # seconds

        if tool_context is None:
            tool_context = ToolContext(agent_name="mcp_tool_executor", state={}, session=None)

        for attempt in range(MAX_RETRIES + 1):
            try:
                if server_id not in self.connected_servers or \
                        self.connected_servers[server_id].get("status") != "connected" or \
                        not await self.check_connection_health(server_id):  # Added health check
                    logger.info(
                        f"Server {server_id} not connected or unhealthy. Attempting to (re)connect (Attempt {attempt + 1}).")
                    server_config = self.server_manager.get_server(server_id)
                    if not server_config:
                        raise ValueError(f"No configuration found for server '{server_id}' to reconnect.")
                    await self.connect_to_server(server_id=server_id, server_config_from_registry=server_config)

                tool = self.get_tool_by_name(server_id, tool_name)
                if not tool:
                    # List available tools for better debugging
                    server_tools = self.get_server_tools(server_id)
                    available_tool_names = [t.name for t in server_tools]
                    logger.error(
                        f"Tool '{tool_name}' not found in server '{server_id}'. Available: {available_tool_names}")
                    raise ValueError(f"Tool '{tool_name}' not found. Available: {available_tool_names}")

                logger.info(
                    f"Executing tool '{tool_name}' on server '{server_id}' with args: {arguments} (Attempt {attempt + 1})")

                result = await asyncio.wait_for(
                    tool.run_async(args=arguments, tool_context=tool_context),
                    timeout=TOOL_EXEC_TIMEOUT
                )
                logger.info(f"Tool '{tool_name}' executed successfully on server '{server_id}'.")
                return result

            except asyncio.TimeoutError:
                logger.warning(f"Timeout executing tool '{tool_name}' on server '{server_id}' (Attempt {attempt + 1}).")
                if attempt >= MAX_RETRIES:
                    logger.error(f"Max retries reached for tool '{tool_name}' due to timeout.")
                    raise RuntimeError(f"Tool '{tool_name}' execution timed out after {MAX_RETRIES + 1} attempts.")
            except (ConnectionError, RuntimeError, ValueError) as e:  # Catch ValueError for config/tool not found
                logger.warning(
                    f"Error executing/connecting tool '{tool_name}' on server '{server_id}': {e} (Attempt {attempt + 1}).")
                if attempt >= MAX_RETRIES:
                    logger.error(f"Max retries reached for tool '{tool_name}'. Last error: {e}", exc_info=True)
                    raise RuntimeError(
                        f"Failed to execute tool '{tool_name}' after {MAX_RETRIES + 1} attempts. Last error: {e}")
            except Exception as unhandled_e:  # Catch any other unhandled exception
                logger.critical(f"Unhandled exception during tool execution for '{tool_name}': {unhandled_e}",
                                exc_info=True)
                raise  # Re-raise critical unhandled exceptions immediately

            if attempt < MAX_RETRIES:
                logger.info(f"Closing server {server_id} connection and sleeping for {RETRY_DELAY}s before retry.")
                await self.close_server(server_id)  # Ensure clean state before retry
                await asyncio.sleep(RETRY_DELAY)

        # Should not be reached if logic is correct, but as a fallback:
        raise RuntimeError(f"Tool execution for '{tool_name}' failed after all retries.")

    def get_server_tools(self, server_id: str) -> List[BaseTool]:
        """Get list of ADK tools from a connected server."""
        server_info = self.connected_servers.get(server_id)
        if server_info and server_info.get("status") == "connected":
            return server_info.get("tools", [])
        return []