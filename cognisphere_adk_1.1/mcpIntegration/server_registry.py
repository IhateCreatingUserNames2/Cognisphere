# cognisphere/mcpIntegration/server_registry.py
from typing import Dict, Any, Optional, List
import os
import importlib
import sys

from google.adk.tools import BaseTool, ToolContext


class MCPServerRegistry:
    """
    Manages registration and discovery of MCP servers
    """
    def __init__(self):
        """
        Initialize the MCP Server Registry
        """
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._server_paths: Dict[str, str] = {}

    def register_server(
            self,
            name: str,
            server_type: str = 'stdio',
            command: Optional[str] = None,
            module_path: Optional[str] = None,
            config: Optional[Dict[str, Any]] = None
    ):
        """
        Register an MCP server with the registry
        """
        server_config = {
            'name': name,
            'type': server_type,
            'command': command,
            'module_path': module_path,
            'config': config or {}
        }

        # Validate unique name
        if name in self._servers:
            raise ValueError(f"Server with name '{name}' already registered")

        self._servers[name] = server_config

        # Store module path if provided
        if module_path:
            self._server_paths[name] = module_path

    def get_server(self, name: str) -> Dict[str, Any]:
        """
        Retrieve a registered server's configuration
        """
        if name not in self._servers:
            raise ValueError(f"No server registered with name '{name}'")

        return self._servers[name]

    def list_servers(self) -> List[str]:
        """
        List all registered server names
        """
        return list(self._servers.keys())

    def dynamically_import_server(self, name: str):
        """
        Dynamically import an MCP server module
        """
        if name not in self._server_paths:
            raise ValueError(f"No importable module found for server '{name}'")

        try:
            # Add the directory to Python path if needed
            module_dir = os.path.dirname(self._server_paths[name])
            if module_dir not in sys.path:
                sys.path.insert(0, module_dir)

            # Import the module
            module = importlib.import_module(
                os.path.basename(self._server_paths[name]).replace('.py', '')
            )

            return module
        except ImportError as e:
            raise ValueError(f"Failed to import server module for '{name}': {e}")


class MCPServerTool(BaseTool):
    """
    A tool representing a specific MCP server and its capabilities
    """
    def __init__(
            self,
            server_name: str,
            server_registry: MCPServerRegistry
    ):
        """
        Initialize an MCP Server Tool
        """
        # Retrieve server configuration
        server_config = server_registry.get_server(server_name)

        super().__init__(
            name=f"mcp_server_{server_name}",
            description=f"MCP Server Tool for {server_name}",
            is_long_running=True  # MCP interactions can be complex
        )

        self.server_name = server_name
        self.server_registry = server_registry

        # Placeholders for server capabilities
        self._resources = []
        self._tools = []
        self._prompts = []

        # Imported server module
        self._server_module = None

    async def _initialize_server(self):
        """
        Dynamically import and prepare the MCP server module
        """
        # Import the server module
        self._server_module = self.server_registry.dynamically_import_server(self.server_name)

    async def run_async(self, args: Dict[str, Any], tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        """
        Execute an action on the MCP server
        """
        # Ensure server module is loaded
        if not self._server_module:
            await self._initialize_server()

        operation = args.get('operation')

        try:
            # Placeholder implementation - would need to be adapted based on specific server implementation
            if operation == 'list_tools':
                # Assuming the server module has a way to list tools
                if hasattr(self._server_module, 'list_tools'):
                    tools = await self._server_module.list_tools()
                    return {
                        "status": "success",
                        "tools": tools
                    }

            elif operation == 'call_tool':
                tool_name = args.get('tool_name')
                tool_args = args.get('arguments', {})

                if not tool_name:
                    return {
                        "status": "error",
                        "message": "tool_name is required"
                    }

                # Assuming the server module has a way to call tools
                if hasattr(self._server_module, 'call_tool'):
                    result = await self._server_module.call_tool(tool_name, tool_args)
                    return {
                        "status": "success",
                        "result": result
                    }

            else:
                return {
                    "status": "error",
                    "message": f"Unsupported operation: {operation}"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"MCP server operation error: {str(e)}"
            }