# cognisphere_adk/mcpIntegration/server_installer.py
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
from .mcp_shared_environment import MCPSharedEnvironment


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
        self.shared_env = MCPSharedEnvironment()

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
                    "name": f"cognisphere-mcpIntegration-server-{server_id}",
                    "version": "1.0.0",
                    "private": True,
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

        # Determine full command
        # On Windows, need special handling for npx
        is_windows = sys.platform == "win32"

        if command == "npx":
            # Extract the package name from args
            package_name = None
            filtered_args = []

            for arg in args:
                if arg.startswith("@modelcontextprotocol/"):
                    package_name = arg
                else:
                    filtered_args.append(arg)

            if package_name and package_name.startswith("@modelcontextprotocol/"):
                # Use the shared environment for MCP packages
                npx_command, package_args = self.shared_env.get_npx_command(package_name)

                # Prepare the full command correctly for Windows and Unix
                if is_windows:
                    # On Windows, we need shell=True for npx.cmd
                    full_command = npx_command
                    cmd_args = []

                    # Add -y flag if not present
                    if "-y" not in filtered_args:
                        cmd_args.append("-y")

                    # Add the package arguments
                    cmd_args.extend(package_args)

                    # Add remaining arguments
                    cmd_args.extend([arg for arg in filtered_args if arg != "-y"])

                    print(f"Windows command: {full_command} {' '.join(cmd_args)}")

                    # Launch the server process with shell=True for Windows
                    process = subprocess.Popen(
                        [full_command] + cmd_args,
                        cwd=server_path,
                        env=full_env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,  # Line buffered
                        shell=is_windows  # Use shell on Windows
                    )

                    return process
                else:
                    # Unix version (list-based command)
                    full_command = [npx_command]

                    # Add -y flag if not present
                    if "-y" not in filtered_args:
                        full_command.append("-y")

                    # Add the package arguments
                    full_command.extend(package_args)

                    # Add remaining arguments
                    full_command.extend([arg for arg in filtered_args if arg != "-y"])
            else:
                # For other npx commands, use system npx with appropriate extension
                if is_windows:
                    full_command = "npx.cmd"
                    cmd_args = args
                else:
                    full_command = ["npx"]
                    full_command.extend(args)
        else:
            # Non-npx command
            if is_windows:
                # Check if command exists and append .exe or .cmd if needed
                if not command.endswith(('.exe', '.cmd', '.bat')) and shutil.which(command) is None:
                    for ext in ['.exe', '.cmd', '.bat']:
                        if shutil.which(f"{command}{ext}"):
                            command = f"{command}{ext}"
                            break

                full_command = command
                cmd_args = args
            else:
                full_command = [command]
                full_command.extend(args)

        # Launch the server process
        if is_windows and not isinstance(full_command, list):
            # Windows with string command
            process = subprocess.Popen(
                [full_command] + (cmd_args if 'cmd_args' in locals() else args),
                cwd=server_path,
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                shell=is_windows  # Use shell on Windows
            )
        else:
            # Unix or Windows with list command
            process = subprocess.Popen(
                full_command if isinstance(full_command, list) else [full_command] + args,
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

    def launch_server(self, server_config: Dict[str, Any]) -> subprocess.Popen:
        """
        Launch an MCP server process

        Args:
            server_config: Server configuration with command, args, env

        Returns:
            Process object
        """
        import shutil
        import sys
        import os

        server_id = server_config.get("id")
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not server_id or not command:
            raise ValueError("Server ID and command are required")

        # Use the installer's base path
        server_path = os.path.join(self.installer.base_path, server_id)

        # Ensure environment exists
        if not os.path.exists(server_path):
            self.installer.create_isolated_environment(server_id)

        # Prepare environment variables
        full_env = os.environ.copy()
        full_env.update(env)

        # Is this Windows?
        is_windows = sys.platform == "win32"
        shell = is_windows

        # Find the proper command executable
        if is_windows:
            # For Windows, find the proper command with extension
            if command == "npx":
                cmd_path = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"
            elif command == "npm":
                cmd_path = shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
            elif command == "node":
                cmd_path = shutil.which("node.exe") or shutil.which("node") or "node.exe"
            else:
                # For other commands
                cmd_path = shutil.which(command) or command

            # Print for debugging
            print(f"Command path: {cmd_path}")

            # Build command line
            cmd_line = [cmd_path] + args
        else:
            # For non-Windows systems
            cmd_line = [command] + args

        # Print full command for debugging
        print(f"Executing: {' '.join(cmd_line)}")
        print(f"Working directory: {server_path}")

        # Launch the server process with proper shell settings
        try:
            process = subprocess.Popen(
                cmd_line,
                cwd=server_path,
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                shell=shell  # Use shell on Windows
            )

            # Update server status
            server_config["status"] = "running"
            server_config["process"] = process  # Keep a reference to the process

            # Optional: Read a bit from stderr to check for immediate errors
            if process.stderr:
                stderr_data = process.stderr.readline()
                if stderr_data:
                    print(f"Server initial output: {stderr_data}")

            return process
        except Exception as e:
            print(f"Error launching server: {e}")
            import traceback
            traceback.print_exc()
            raise