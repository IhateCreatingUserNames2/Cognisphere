# cognisphere_adk/mcp/server_config.py
from datetime import datetime
from typing import Dict, Any, List
import os
import json
import uuid


class MCPServerManager:
    """
    Manages MCP Server configurations, installation, and connections
    """

    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.expanduser('~/.cognisphere/mcp_servers.json')
        self.servers = self._load_servers()

    def _load_servers(self) -> Dict[str, Dict[str, Any]]:
        """Load MCP server configurations"""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            return {}

        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def add_server(
            self,
            name: str = None,
            command: str = None,
            args: List[str] = None,
            env: Dict[str, str] = None
    ):
        """
        Add a new MCP server configuration

        Args:
            name: Optional server name (generated if not provided)
            command: Command to launch the server
            args: Arguments for the server
            env: Environment variables for the server
        """
        # Generate a unique ID if no name provided
        server_id = name or str(uuid.uuid4())

        # Validate required fields
        if not command:
            raise ValueError("Command is required to add an MCP server")

        # Create server configuration
        server_config = {
            "id": server_id,
            "command": command,
            "args": args or [],
            "env": env or {},
            "created_at": datetime.utcnow().isoformat(),
            "last_connected": None,
            "status": "not_connected"
        }

        # Add or update server
        self.servers[server_id] = server_config

        # Save configuration
        self._save_servers()

        return server_id

    def _save_servers(self):
        """Save server configurations to file"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.servers, f, indent=2)

    def remove_server(self, server_id: str):
        """Remove a server configuration"""
        if server_id in self.servers:
            del self.servers[server_id]
            self._save_servers()

    def get_server(self, server_id: str) -> Dict[str, Any]:
        """Retrieve a specific server configuration"""
        return self.servers.get(server_id)

    def list_servers(self) -> List[Dict[str, Any]]:
        """List all configured servers"""
        return list(self.servers.values())