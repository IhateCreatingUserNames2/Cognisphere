# cognisphere_adk/mcpIntegration/toolset.py
"""
MCP Toolset Integration for Cognisphere ADK
Provides bidirectional integration between ADK tools and MCP
"""
from pydantic import BaseModel
import datetime
import sys
import shutil
import asyncio
import json
import contextlib
import subprocess
from typing import Dict, Any, List, Tuple, Optional, AsyncGenerator
from google.genai.types import FunctionDeclaration, Schema, Type
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import SseServerParams
from google.adk.tools.tool_context import ToolContext

from mcpIntegration.server_registry import MCPServerRegistry, MCPServerTool

# These are the required MCP imports for the client functionality
try:
    from mcp import types as mcp_types
    from mcp import ClientSession, StdioServerParameters, types, stdio_client

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

# Define a tiny Pydantic model for your entities:
class EntitySpec(BaseModel):
    name: str
    entityType: str
    observations: List[str]


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
        import asyncio
        import contextlib

        # Use a real AsyncExitStack
        exit_stack = contextlib.AsyncExitStack()

        try:
            # Create client session based on connection parameters type
            if isinstance(connection_params, StdioServerParameters):
                # Start the server process
                read_stream, write_stream = await stdio_client(connection_params).__aenter__()

                # Properly manage the streams
                read_stream = await exit_stack.enter_async_context(read_stream)
                write_stream = await exit_stack.enter_async_context(write_stream)

                # Create client session
                session = await exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

            elif isinstance(connection_params, SseServerParams):
                from mcp.client.sse import sse_client

                # Create SSE client session
                session = await exit_stack.enter_async_context(
                    sse_client(connection_params.url, connection_params.headers)
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
                    mcp_tool=mcp_tool,
                    mcp_session=session
                )

                adk_tools.append(tool)

            return adk_tools, exit_stack

        except Exception as e:
            # Ensure cleanup if an error occurs
            try:
                await exit_stack.aclose()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")

            raise ValueError(f"Failed to connect to MCP server: {e}")

    def get_available_tool(self, server_id, tool_name):
        """
        Get a specific tool from a connected server by name

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

    def discover_mcp_servers(self):
        """
        Dynamically discover and configure MCP servers
        """
        servers = []

        try:
            # Run npm list to find installed MCP servers
            result = subprocess.run(
                ["npm", "list", "-g", "--depth=0", "@modelcontextprotocol/*"],
                capture_output=True,
                text=True
            )

            # Parse installed packages
            installed_packages = result.stdout.splitlines()

            for package in installed_packages:
                if "@modelcontextprotocol/server-" in package:
                    server_name = package.split("server-")[1].split("@")[0]
                    servers.append({
                        "name": server_name,
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", f"@modelcontextprotocol/server-{server_name}"],
                        "optional": True
                    })

        except Exception as e:
            print(f"Error discovering MCP servers: {e}")

        return servers

    def get_mcp_tools(self) -> List[BaseTool]:
        """
        Collect tools from all connected MCP servers

        Returns:
            List of MCP tools from connected servers
        """
        tools = []

        # Collect tools from all connected servers
        for server_id, server in self.connected_servers.items():
            if "tools" in server:
                tools.extend(server["tools"])

        # If there are already connected tools, return them
        if tools:
            return tools

        try:
            # Find NPM in the system
            npm_cmd = shutil.which("npm")
            if not npm_cmd and sys.platform == "win32":
                # Try to find npm.cmd on Windows
                npm_cmd = shutil.which("npm.cmd")

            if not npm_cmd:
                print("NPM not found in PATH. MCP tool discovery will be limited.")
                return tools

            # Print found NPM path
            print(f"Found NPM at: {npm_cmd}")

            # Try to list installed MCP packages
            try:
                # Check for global packages
                global_cmd = [npm_cmd, "list", "-g", "--depth=0", "@modelcontextprotocol/*"]
                global_result = subprocess.run(
                    global_cmd,
                    capture_output=True,
                    text=True,
                    check=False  # Don't raise an exception if the command fails
                )

                # Print command and result for debugging
                print(f"Command: {' '.join(global_cmd)}")
                print(f"Result: {global_result.stdout}")
                print(f"Error: {global_result.stderr}")

                # Also check local packages
                local_cmd = [npm_cmd, "list", "--depth=0", "@modelcontextprotocol/*"]
                local_result = subprocess.run(
                    local_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )

                # Combine results
                installed_packages = []
                if global_result.returncode == 0:
                    installed_packages.extend(global_result.stdout.splitlines())
                if local_result.returncode == 0:
                    installed_packages.extend(local_result.stdout.splitlines())

                # Process found packages
                for package in installed_packages:
                    if "@modelcontextprotocol/server-" in package:
                        server_name = package.split("server-")[1].split("@")[0]
                        print(f"Found MCP server: {server_name}")
                        tools.append(MCPServerTool(
                            server_name=server_name,
                            server_registry=MCPServerRegistry()
                        ))
            except Exception as e:
                print(f"Error discovering MCP tools: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"Error in get_mcp_tools: {e}")
            import traceback
            traceback.print_exc()

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
                              "Install with 'pip install mcpIntegration[cli]'")

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
    async def mcp_server_from_adk_tools(tools: List[BaseTool], server_name: str = "cognisphere-mcpIntegration"):
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
                              "Install with 'pip install mcpIntegration[cli]'")

        # These are required for server functionality
        try:
            from mcpIntegration.server.lowlevel import Server, NotificationOptions
            from mcpIntegration.server.models import InitializationOptions
        except ImportError:
            raise ImportError("MCP server packages are not installed. "
                              "Install with 'pip install mcpIntegration[cli]'")

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

    # Update in mcpIntegration/toolset.py - change the register_server method

    async def register_server(self, server_id: str, connection_params):
        """
        Register and connect to an MCP server with improved error handling and task safety

        Args:
            server_id: Unique identifier for the server
            connection_params: Either StdioServerParameters or SseServerParams

        Returns:
            List of ADK tools from the server
        """
        if not HAS_MCP:
            raise ImportError("MCP package is required but not installed. "
                              "Install with 'pip install mcp[cli]'")

        # If server is already connected, close it first
        if server_id in self.connected_servers:
            try:
                await self.close_server(server_id)
            except Exception as e:
                print(f"Warning: Error closing existing connection to {server_id}: {e}")

        try:
            # Create a new AsyncExitStack for this connection
            from contextlib import AsyncExitStack
            exit_stack = AsyncExitStack()

            # We'll handle connecting directly instead of using from_server
            from google.adk.tools.mcp_tool.mcp_tool import MCPTool

            # Connect to the server based on connection type
            if isinstance(connection_params, StdioServerParameters):
                # Start the server process in a controlled environment
                print(f"Starting MCP server: {server_id}")
                try:
                    # Use a timeout for connecting to the server
                    connect_task = stdio_client(connection_params)
                    # Make sure we enter and exit in the same task
                    read_stream, write_stream = await exit_stack.enter_async_context(
                        connect_task
                    )

                    # Create session with proper error handling
                    session = await exit_stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )

                    # Initialize the session with timeout
                    await asyncio.wait_for(session.initialize(), timeout=5.0)

                    # Get tools with timeout
                    raw_tools = await asyncio.wait_for(session.list_tools(), timeout=5.0)

                    # Debug - print the actual type and content
                    print(f"Raw tools response type: {type(raw_tools)}")

                    # Process the raw tools response
                    mcp_tools = []

                    # Try to extract tools from various response formats
                    if hasattr(raw_tools, 'tools') and isinstance(raw_tools.tools, list):
                        # Handle ListToolsResult object
                        print(f"Found tools list attribute with {len(raw_tools.tools)} tools")
                        mcp_tools = raw_tools.tools
                    elif isinstance(raw_tools, list):
                        # Direct list of tools
                        mcp_tools = raw_tools
                    else:
                        # Try other methods to extract tools
                        print(f"Attempting to extract tools from format: {type(raw_tools)}")
                        # Try dictionary access
                        try:
                            if hasattr(raw_tools, 'get'):
                                tool_items = raw_tools.get('tools')
                                if isinstance(tool_items, list):
                                    print(f"Found tools via dictionary access with {len(tool_items)} items")
                                    mcp_tools = tool_items
                        except (TypeError, KeyError, AttributeError):
                            pass

                        # Last attempt - try to find tools attribute
                        if not mcp_tools and hasattr(raw_tools, '__dict__'):
                            print(f"Checking for tools in attributes: {dir(raw_tools)}")
                            for attr_name in dir(raw_tools):
                                if attr_name == 'tools' or attr_name == 'items':
                                    attr_value = getattr(raw_tools, attr_name)
                                    if isinstance(attr_value, list):
                                        print(f"Found tools in {attr_name} attribute")
                                        mcp_tools = attr_value
                                        break

                    print(f"Extracted {len(mcp_tools)} tools")

                    # Convert MCP tools to ADK tools
                    adk_tools = []
                    for mcp_tool in mcp_tools:
                        try:
                            # Handle different tool formats
                            if isinstance(mcp_tool, tuple):
                                # Debug the tuple structure
                                print(f"Tool tuple format: {mcp_tool}")
                                # Extract name and description from tuple
                                if len(mcp_tool) >= 2:
                                    name = str(mcp_tool[0])
                                    description = str(mcp_tool[1]) if len(mcp_tool) > 1 else ""
                                    params = mcp_tool[2] if len(mcp_tool) > 2 else {}

                                    # Create a proper MCP tool object
                                    from mcp.types import Tool as McpTool
                                    proper_tool = McpTool(
                                        name=name,
                                        description=description,
                                        inputSchema=params
                                    )
                                    tool = MCPTool(mcp_tool=proper_tool, mcp_session=session)
                                    adk_tools.append(tool)
                            elif hasattr(mcp_tool, 'name'):
                                # Standard tool format
                                tool = MCPTool(mcp_tool=mcp_tool, mcp_session=session)
                                adk_tools.append(tool)
                            elif isinstance(mcp_tool, dict) and 'name' in mcp_tool:
                                # Dictionary format
                                from mcp.types import Tool as McpTool
                                proper_tool = McpTool(
                                    name=mcp_tool['name'],
                                    description=mcp_tool.get('description', ''),
                                    inputSchema=mcp_tool.get('inputSchema', {})
                                )
                                tool = MCPTool(mcp_tool=proper_tool, mcp_session=session)
                                adk_tools.append(tool)
                            else:
                                print(f"Skipping unsupported tool format: {type(mcp_tool)}")
                                # Try to print some useful information about the tool
                                if hasattr(mcp_tool, '__dict__'):
                                    print(f"Tool attributes: {dir(mcp_tool)}")
                        except Exception as tool_error:
                            print(f"Error creating MCPTool: {tool_error}")
                            import traceback
                            traceback.print_exc()
                            continue

                    # Store the connection in our registry
                    self.connected_servers[server_id] = {
                        "exit_stack": exit_stack,
                        "tools": adk_tools,
                        "session": session
                    }

                    print(f"Successfully connected to server {server_id} with {len(adk_tools)} tools")
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
                    await exit_stack.aclose()
                    raise ValueError(f"Failed to connect to MCP server: {e}")

            else:
                # For other connection types (SSE), implement similar pattern
                raise ValueError(f"Unsupported connection type: {type(connection_params)}")

        except Exception as outer_error:
            print(f"Outer error in register_server: {outer_error}")
            import traceback
            traceback.print_exc()
            raise

    async def close_server(self, server_id: str):
        """
        Close connection to an MCP server with improved error handling

        Args:
            server_id: Server identifier
        """
        if server_id in self.connected_servers:
            server = self.connected_servers[server_id]

            # Clean up resources with proper error handling
            if "exit_stack" in server:
                try:
                    print(f"Closing connection to MCP server: {server_id}")
                    await server["exit_stack"].aclose()
                    print(f"Successfully closed connection to MCP server: {server_id}")
                except Exception as e:
                    print(f"Error closing connection to MCP server {server_id}: {e}")
                    import traceback
                    traceback.print_exc()

            # Remove from our registry regardless of cleanup success
            del self.connected_servers[server_id]

            # Update server status if possible
            try:
                from mcpIntegration.server_installer import MCPServerManager
                server_manager = MCPServerManager()
                server_config = server_manager.get_server(server_id)
                if server_config:
                    server_config["status"] = "not_connected"
                    server_manager._save_servers()
            except Exception as status_error:
                print(f"Warning: Could not update server status: {status_error}")

    async def close_all(self):
        """Close all MCP server connections"""
        for server_id in list(self.connected_servers.keys()):
            await self.close_server(server_id)