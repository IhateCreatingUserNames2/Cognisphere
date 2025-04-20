# cognisphere/mcpIntegration/mcp_shared_environment.py
import os
import subprocess
import json
import logging
import sys
import shutil


class MCPSharedEnvironment:
    def __init__(self, base_path=None):
        """Initialize the shared MCP environment."""
        self.base_path = base_path or os.path.expanduser("~/.cognisphere/mcp_shared")
        self.node_modules_path = os.path.join(self.base_path, "node_modules")
        self.package_json_path = os.path.join(self.base_path, "package.json")

        # Ensure base directories exist
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(self.node_modules_path, exist_ok=True)

        # Create package.json if it doesn't exist
        if not os.path.exists(self.package_json_path):
            with open(self.package_json_path, "w") as f:
                json.dump({
                    "name": "cognisphere-mcpIntegration-shared",
                    "version": "1.0.0",
                    "private": True,
                    "dependencies": {}
                }, f, indent=2)

        # Initialize internal state
        self.installed_packages = self._load_installed_packages()

    def _load_installed_packages(self):
        """Load the list of installed packages from package.json."""
        try:
            with open(self.package_json_path, "r") as f:
                package_data = json.load(f)
                return package_data.get("dependencies", {})
        except (json.JSONDecodeError, IOError):
            return {}

    def _get_npm_command(self):
        """Get the appropriate npm command for the current platform."""
        if sys.platform == "win32":
            # Find npm.cmd in system PATH
            npm_path = shutil.which("npm.cmd")
            if npm_path:
                return npm_path
            # Fallback to Node.js installation paths
            possible_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'nodejs', 'npm.cmd'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'nodejs', 'npm.cmd')
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return path
            return "npm.cmd"  # Last resort
        return "npm"

    def ensure_package_installed(self, package_name):
        """
        Ensure a Node.js package is installed in the shared environment.

        Args:
            package_name: Name of the package to install

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if already installed
        if package_name in self.installed_packages:
            return True

        try:
            # Get appropriate npm command
            npm_command = self._get_npm_command()

            # Install the package
            logging.info(f"Installing {package_name} in shared environment")
            result = subprocess.run(
                [npm_command, "install", package_name, "--save"],
                cwd=self.base_path,
                check=True,
                capture_output=True,
                text=True,
                shell=sys.platform == "win32"  # Use shell on Windows
            )

            # Update internal state
            self.installed_packages = self._load_installed_packages()
            return True
        except subprocess.SubprocessError as e:
            logging.error(f"Error installing package {package_name}: {e}")
            return False

    def get_npx_command(self, package_name):
        """
        Get the command to run an npx package from the shared environment.

        Args:
            package_name: Name of the package to run

        Returns:
            tuple: (command, [args]) to use for subprocess
        """
        # Ensure the package is installed first
        self.ensure_package_installed(package_name)

        # Get appropriate npx command based on platform
        if sys.platform == "win32":
            # First try to find npx.cmd in the path
            npx_path = shutil.which("npx.cmd")
            if npx_path:
                return npx_path, [package_name]

            # If not found, check common locations
            possible_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'nodejs', 'npx.cmd'),
                os.path.join(os.environ.get('APPDATA', ''), 'npm', 'npx.cmd'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'nodejs', 'npx.cmd')
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    return path, [package_name]

            # Last resort - just use npx.cmd and rely on PATH
            return "npx.cmd", [package_name]
        else:
            # For non-Windows systems
            # Check if npx is in node_modules/.bin of shared environment
            local_npx = os.path.join(self.node_modules_path, ".bin", "npx")
            if os.path.exists(local_npx):
                return local_npx, [package_name]
            else:
                # Use system npx
                return "npx", [package_name]