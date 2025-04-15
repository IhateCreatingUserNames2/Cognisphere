# cognisphere_adk/mcp/server_installer.py
"""
MCP Server Installer for Cognisphere
Handles installation and management of MCP server packages
"""

import os
import sys
import json
import subprocess
import tempfile
import venv
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from sympy import true


class MCPServerInstaller:
    """
    Handles installation and management of MCP server packages
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the MCP Server Installer

        Args:
            base_path: Base path for server environments (defaults to ~/.cognisphere/mcp_servers)
        """
        self.base_path = base_path or os.path.expanduser("~/.cognisphere/mcp_servers")
        os.makedirs(self.base_path, exist_ok=True)

    def create_isolated_environment(self, server_id: str) -> str:
        """
        Create an isolated environment for an MCP server

        Args:
            server_id: Unique server identifier

        Returns:
            Path to the environment
        """
        server_path = os.path.join(self.base_path, server_id)

        # Create server directory
        os.makedirs(server_path, exist_ok=True)

        # Create Python virtual environment
        venv_path = os.path.join(server_path, "venv")
        if not os.path.exists(venv_path):
            venv.create(venv_path, with_pip=True)

        # Create node_modules directory
        node_modules_path = os.path.join(server_path, "node_modules")
        os.makedirs(node_modules_path, exist_ok=True)

        # Create package.json if it doesn't exist
        package_json_path = os.path.join(server_path, "package.json")
        if not os.path.exists(package_json_path):
            with open(package_json_path, "w") as f:
                json.dump({
                    "name": f"cognisphere-mcp-server-{server_id}",
                    "version": "1.0.0",
                    "private": true,
                    "dependencies": {}
                }, f, indent=2)

        return server_path

    def install_server_package(self, server_id: str, package_name: str) -> bool:
        """
        Install an NPM package for an MCP server

        Args:
            server_id: Server identifier
            package_name: NPM package to install

        Returns:
            True if successful
        """
        server_path = os.path.join(self.base_path, server_id)

        # Ensure environment exists
        if not os.path.exists(server_path):
            self.create_isolated_environment(server_id)

        try:
            # Run npm install in the server directory
            subprocess.run(
                ["npm", "install", package_name, "--save"],
                cwd=server_path,
                check=True,
                capture_output=True,
                text=True
            )

            # Update package.json (already done by npm install --save)
            return True

        except subprocess.SubprocessError as e:
            print(f"Error installing package {package_name}: {e}")
            return False

    def launch_server(self, server_config: Dict[str, Any]) -> subprocess.Popen:
        """
        Launch an MCP server process

        Args:
            server_config: Server configuration with command, args, env

        Returns:
            Process object
        """
        server_id = server_config.get("id")
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not server_id or not command:
            raise ValueError("Server ID and command are required")

        server_path = os.path.join(self.base_path, server_id)

        # Ensure environment exists
        if not os.path.exists(server_path):
            self.create_isolated_environment(server_id)

        # Prepare environment variables
        full_env = os.environ.copy()
        full_env.update(env)

        # Determine full command path
        if command == "npx":
            # For Node.js commands
            full_command = ["npx"]
            full_command.extend(args)
        elif command.endswith(".py"):
            # For Python scripts, use the venv Python
            venv_python = os.path.join(server_path, "venv", "bin", "python")
            full_command = [venv_python, command]
            full_command.extend(args)
        else:
            # Other commands
            full_command = [command]
            full_command.extend(args)

        # Launch the server process
        process = subprocess.Popen(
            full_command,
            cwd=server_path,
            env=full_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )

        return process

    def clean_environment(self, server_id: str) -> bool:
        """
        Clean up a server environment

        Args:
            server_id: Server identifier

        Returns:
            True if successful
        """
        server_path = os.path.join(self.base_path, server_id)

        if os.path.exists(server_path):
            try:
                shutil.rmtree(server_path)
                return True
            except Exception as e:
                print(f"Error cleaning environment for {server_id}: {e}")
                return False

        return True  # Already doesn't exist


class MCPServerManager:
    """
    Manages MCP Server configurations, installation, and connections
    """

    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.expanduser('~/.cognisphere/mcp_servers.json')
        self.servers = self._load_servers()
        self.installer = MCPServerInstaller()

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
            env: Dict[str, str] = None,
            install_package: str = None
    ):
        """
        Add a new MCP server configuration

        Args:
            name: Optional server name (generated if not provided)
            command: Command to launch the server
            args: Arguments for the server
            env: Environment variables for the server
            install_package: Optional NPM package to install

        Returns:
            Server ID
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

        # Prepare environment and install package if needed
        self.installer.create_isolated_environment(server_id)
        if install_package:
            self.installer.install_server_package(server_id, install_package)

        return server_id

    def _save_servers(self):
        """Save server configurations to file"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.servers, f, indent=2)

    def remove_server(self, server_id: str):
        """Remove a server configuration"""
        if server_id in self.servers:
            # Clean up server environment
            self.installer.clean_environment(server_id)

            # Remove from configuration
            del self.servers[server_id]
            self._save_servers()

    def get_server(self, server_id: str) -> Dict[str, Any]:
        """Retrieve a specific server configuration"""
        return self.servers.get(server_id)

    def list_servers(self) -> List[Dict[str, Any]]:
        """List all configured servers"""
        return list(self.servers.values())

    def launch_server(self, server_id: str) -> subprocess.Popen:
        """
        Launch an MCP server

        Args:
            server_id: Server identifier

        Returns:
            Process object
        """
        server_config = self.get_server(server_id)
        if not server_config:
            raise ValueError(f"Server {server_id} not found")

        process = self.installer.launch_server(server_config)

        # Update server status
        server_config["status"] = "running"
        server_config["last_connected"] = datetime.utcnow().isoformat()
        self._save_servers()

        return process