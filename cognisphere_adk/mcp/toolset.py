# cognisphere_adk/mcp/toolset.py
"""
MCP Toolset Integration for Cognisphere ADK
Provides bidirectional integration between ADK tools and MCP
"""

import asyncio
import json
import contextlib
from typing import Dict, Any, List, Tuple, Optional, AsyncGenerator

from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext

# These are the required MCP imports for the client functionality
try:
    from mcp import types as mcp_types
    from mcp.client import ClientSession, StdioServerParameters, SseServerParams
    from mcp.client.stdio import stdio_client

    HAS_MCP = True
except ImportError:
    # Fallback for when MCP isn't installed
    HAS_MCP = False


    # Create placeholder classes to avoid further errors
    class DummyTypes:
        class Tool:
            def __init__(self, name, description, parameters=None):
                self.name = name
                self.description = description
                self.parameters = parameters or {}

        class TextContent:
            def __init__(self, type, text):
                self.type = type
                self.text = text


    mcp_types = DummyTypes()


class MCPToolset:
    """
    MCP Toolset provides bidirectional integration between ADK and MCP

    This class manages the connection to MCP servers and converts between
    ADK tools and MCP tools.
    """

    def __init__(self):
        """Initialize the MCP Toolset."""
        if not HAS_MCP:
            print("WARNING: MCP package not installed. Limited functionality available.")
        self.connected_servers = {}
        self.available_tools = {}

    @staticmethod
    async def from_server(connection_params, timeout=30):
        """
        Create a toolset from an MCP server

        Args:
            connection_params: Either StdioServerParameters or SseServerParams
            timeout: Connection timeout in seconds

        Returns:
            Tuple of (list of ADK tools, exit_stack for cleanup)
        """
        if not HAS_MCP:
            raise ImportError("MCP package is required but not installed. "
                              "Install with 'pip install mcp[cli]'")

        from google.adk.tools.mcp_tool.mcp_tool import MCPTool

        # Create exit stack for cleanup
        exit_stack = contextlib.AsyncExitStack()

        try:
            # Create client session based on connection parameters type
            if isinstance(connection_params, StdioServerParameters):
                # Start the server process
                read_stream, write_stream = await exit_stack.enter_async_context(
                    await asyncio.wait_for(
                        contextlib.aclosing(stdio_client(connection_params)),
                        timeout
                    )
                )

                # Create client session
                session = await exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

            elif isinstance(connection_params, SseServerParams):
                # For SSE connection - need to handle SseServerParams.connect specifically
                from mcp.client.sse import sse_client
                session = await exit_stack.enter_async_context(
                    await asyncio.wait_for(
                        sse_client(connection_params.url, connection_params.headers),
                        timeout
                    )
                )
            else:
                raise ValueError(f"Unsupported connection parameters: {type(connection_params)}")

            # Initialize the session
            await session.initialize()

            # List available tools
            mcp_tools = await session.list_tools()

            # Convert MCP tools to ADK tools
            adk_tools = []
            for mcp_tool in mcp_tools:
                tool = MCPTool(
                    name=mcp_tool.name,
                    description=mcp_tool.description or "",
                    mcp_tool_schema=mcp_tool,
                    session=session
                )
                adk_tools.append(tool)

            return adk_tools, exit_stack

        except Exception as e:
            # Clean up resources if an error occurs
            await exit_stack.aclose()
            raise ValueError(f"Failed to connect to MCP server: {e}")

    def get_mcp_tools(self) -> List[BaseTool]:
        """
        Collect tools from all connected MCP servers

        Returns:
            List of MCP tools from connected servers
        """
        tools = []
        for server_id, server in self.connected_servers.items():
            if "tools" in server:
                tools.extend(server["tools"])
        return tools

    @staticmethod
    def adk_to_mcp_tool_type(adk_tool: BaseTool) -> mcp_types.Tool:
        """
        Convert an ADK tool to an MCP tool schema

        Args:
            adk_tool: ADK BaseTool or FunctionTool

        Returns:
            MCP Tool schema
        """
        if not HAS_MCP:
            raise ImportError("MCP package is required but not installed. "
                              "Install with 'pip install mcp[cli]'")

        # Extract parameters from the tool's function signature
        parameters = {}

        if isinstance(adk_tool, FunctionTool) and hasattr(adk_tool, 'func'):
            import inspect
            from typing import get_type_hints

            # Get function signature
            sig = inspect.signature(adk_tool.func)
            type_hints = get_type_hints(adk_tool.func)

            # Process parameters
            for param_name, param in sig.parameters.items():
                # Skip tool_context parameter
                if param_name == 'tool_context':
                    continue

                param_type = type_hints.get(param_name, str)
                param_schema = {"type": "string"}  # Default

                # Map Python types to JSON Schema types
                if param_type == int:
                    param_schema = {"type": "number", "format": "integer"}
                elif param_type == float:
                    param_schema = {"type": "number"}
                elif param_type == bool:
                    param_schema = {"type": "boolean"}
                elif param_type == list or str(param_type).startswith("typing.List"):
                    param_schema = {"type": "array", "items": {"type": "string"}}
                elif param_type == dict or str(param_type).startswith("typing.Dict"):
                    param_schema = {"type": "object"}

                # Get default value if any
                default = param.default if param.default is not inspect.Parameter.empty else None
                if default is not None:
                    param_schema["default"] = default

                parameters[param_name] = param_schema

        # Create MCP Tool schema
        return mcp_types.Tool(
            name=adk_tool.name,
            description=adk_tool.description,
            parameters=parameters
        )

    @staticmethod
    async def mcp_server_from_adk_tools(tools: List[BaseTool], server_name: str = "cognisphere-mcp"):
        """
        Create an MCP server exposing ADK tools

        Args:
            tools: List of ADK tools to expose
            server_name: Name of the MCP server

        Returns:
            MCP Server instance
        """
        if not HAS_MCP:
            raise ImportError("MCP package is required but not installed. "
                              "Install with 'pip install mcp[cli]'")

        # These are required for server functionality
        try:
            from mcp.server.lowlevel import Server, NotificationOptions
            from mcp.server.models import InitializationOptions
        except ImportError:
            raise ImportError("MCP server packages are not installed. "
                              "Install with 'pip install mcp[cli]'")

        # Create server
        app = Server(server_name)

        # Convert ADK tools to MCP tool schemas
        mcp_tools = []
        tool_map = {}

        for tool in tools:
            mcp_tool = MCPToolset.adk_to_mcp_tool_type(tool)
            mcp_tools.append(mcp_tool)
            tool_map[mcp_tool.name] = tool

        # Implement list_tools handler
        @app.list_tools()
        async def list_tools() -> List[mcp_types.Tool]:
            return mcp_tools

        # Implement call_tool handler
        @app.call_tool()
        async def call_tool(
                name: str, arguments: Dict[str, Any]
        ) -> List[mcp_types.TextContent]:
            if name not in tool_map:
                return [mcp_types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Tool '{name}' not found"})
                )]

            try:
                # Execute the ADK tool
                adk_tool = tool_map[name]
                result = await adk_tool.run_async(
                    args=arguments,
                    tool_context=None  # No ADK context in MCP server
                )

                # Convert result to MCP format
                response_text = json.dumps(result, indent=2)
                return [mcp_types.TextContent(type="text", text=response_text)]

            except Exception as e:
                return [mcp_types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Error executing tool: {str(e)}"})
                )]

        return app

    async def register_server(self, server_id: str, connection_params):
        """
        Register and connect to an MCP server

        Args:
            server_id: Unique identifier for the server
            connection_params: Either StdioServerParameters or SseServerParams

        Returns:
            List of ADK tools from the server
        """
        if not HAS_MCP:
            raise ImportError("MCP package is required but not installed. "
                              "Install with 'pip install mcp[cli]'")

        tools, exit_stack = await self.from_server(connection_params)

        self.connected_servers[server_id] = {
            "exit_stack": exit_stack,
            "tools": tools
        }

        return tools

    async def close_server(self, server_id: str):
        """
        Close connection to an MCP server

        Args:
            server_id: Server identifier
        """
        if server_id in self.connected_servers:
            server = self.connected_servers[server_id]
            if "exit_stack" in server:
                await server["exit_stack"].aclose()
            del self.connected_servers[server_id]

    async def close_all(self):
        """Close all MCP server connections"""
        for server_id in list(self.connected_servers.keys()):
            await self.close_server(server_id)