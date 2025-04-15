# cognisphere_adk/web/mcp_routes.py
"""
MCP Web Routes for Cognisphere
Provides Flask routes for MCP server management
"""

import os
import json
from flask import Blueprint, request, jsonify, Response, current_app

# Use absolute imports instead of relative imports
try:
    from cognisphere_adk.mcp.server_installer import MCPServerManager
    from cognisphere_adk.mcp.toolset import MCPToolset
except ImportError:
    # Fall back to local imports if package is not correctly installed
    import sys
    import importlib.util

    # Dynamically import the modules by constructing the path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)

    # Now try to import from the mcp module directly
    try:
        from mcp.server_installer import MCPServerManager
        from mcp.toolset import MCPToolset
    except ImportError:
        # Final fallback - try to load the modules directly by file path
        installer_path = os.path.join(project_root, 'mcp', 'server_installer.py')
        toolset_path = os.path.join(project_root, 'mcp', 'toolset.py')

        if os.path.exists(installer_path) and os.path.exists(toolset_path):
            installer_spec = importlib.util.spec_from_file_location("server_installer", installer_path)
            toolset_spec = importlib.util.spec_from_file_location("toolset", toolset_path)

            server_installer = importlib.util.module_from_spec(installer_spec)
            toolset_module = importlib.util.module_from_spec(toolset_spec)

            installer_spec.loader.exec_module(server_installer)
            toolset_spec.loader.exec_module(toolset_module)

            MCPServerManager = server_installer.MCPServerManager
            MCPToolset = toolset_module.MCPToolset
        else:
            print("WARNING: Could not import MCP modules. MCP functionality will be disabled.")


            # Create placeholder classes to avoid errors
            class DummyMCPServerManager:
                def __init__(self):
                    self.connected_servers = {}

                def list_servers(self):
                    return []

                def add_server(self, **kwargs):
                    return "dummy_server_id"

                def remove_server(self, server_id):
                    pass

                def get_server(self, server_id):
                    return None

                def _save_servers(self):
                    pass


            class DummyMCPToolset:
                def __init__(self):
                    self.connected_servers = {}

                def get_mcp_tools(self):
                    return []

                async def close_server(self, server_id):
                    pass


            MCPServerManager = DummyMCPServerManager
            MCPToolset = DummyMCPToolset

# Create Blueprint
mcp_bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')

# Initialize server manager
server_manager = MCPServerManager()

# Global toolset for managing connections
toolset = MCPToolset()


@mcp_bp.route('/servers', methods=['GET'])
def list_servers():
    """List all configured MCP servers"""
    return jsonify({
        "servers": server_manager.list_servers()
    })


@mcp_bp.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    data = request.json

    # Extract server details
    name = data.get('name')
    command = data.get('command')
    args = data.get('args', [])
    env = data.get('env', {})
    install_package = data.get('install_package')

    # Validate required fields
    if not command:
        return jsonify({"error": "Command is required"}), 400

    try:
        # Add server
        server_id = server_manager.add_server(
            name=name,
            command=command,
            args=args,
            env=env,
            install_package=install_package if hasattr(server_manager, 'install_package') else None
        )

        return jsonify({
            "status": "success",
            "server_id": server_id,
            "message": f"Server {name or server_id} added successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>', methods=['DELETE'])
async def remove_server(server_id):
    """Remove an MCP server"""
    try:
        # Close connection if active
        if hasattr(toolset, 'close_server'):
            await toolset.close_server(server_id)

        # Remove server
        server_manager.remove_server(server_id)

        return jsonify({
            "status": "success",
            "message": f"Server {server_id} removed successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>/connect', methods=['POST'])
async def connect_server(server_id):
    """Connect to an MCP server and retrieve tools"""
    try:
        # Import here to avoid circular imports
        try:
            from google.adk.tools.mcp_tool.mcp_toolset import StdioServerParameters
        except ImportError:
            from mcp.client import StdioServerParameters

        # Get server config
        server_config = server_manager.get_server(server_id)
        if not server_config:
            return jsonify({"error": f"Server {server_id} not found"}), 404

        # Launch server if the method exists
        if hasattr(server_manager, 'launch_server'):
            process = server_manager.launch_server(server_id)

        # Create connection parameters
        connection_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config['args'],
            env=server_config['env']
        )

        # Register server with toolset if the method exists
        if hasattr(toolset, 'register_server'):
            tools = await toolset.register_server(server_id, connection_params)
        else:
            tools = []

        # Return list of available tools
        return jsonify({
            "status": "success",
            "server_id": server_id,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "is_long_running": tool.is_long_running if hasattr(tool, 'is_long_running') else False
                }
                for tool in tools
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>/disconnect', methods=['POST'])
async def disconnect_server(server_id):
    """Disconnect from an MCP server"""
    try:
        # Close connection if the method exists
        if hasattr(toolset, 'close_server'):
            await toolset.close_server(server_id)

        # Update server status
        server_config = server_manager.get_server(server_id)
        if server_config:
            server_config["status"] = "not_connected"
            server_manager._save_servers()

        return jsonify({
            "status": "success",
            "message": f"Server {server_id} disconnected successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/tools', methods=['GET'])
def list_tools():
    """List all available MCP tools from connected servers"""
    tools = []

    try:
        # Collect tools from all connected servers
        if hasattr(toolset, 'connected_servers'):
            for server_id, server in toolset.connected_servers.items():
                if "tools" in server:
                    for tool in server["tools"]:
                        tools.append({
                            "name": tool.name,
                            "description": tool.description,
                            "server_id": server_id,
                            "is_long_running": tool.is_long_running if hasattr(tool, 'is_long_running') else False
                        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "tools": tools,
        "count": len(tools)
    })


def register_mcp_blueprint(app):
    """Register the MCP blueprint with the Flask app"""
    try:
        app.register_blueprint(mcp_bp)

        # Add MCP routes to the A2A server (agent.json)
        try:
            from cognisphere_adk.a2a.server import get_agent_card
        except ImportError:
            # Try alternative import paths
            try:
                from a2a.server import get_agent_card
            except ImportError:
                # Create a dummy function if server module not found
                def get_agent_card():
                    return {"name": "Cognisphere", "skills": [], "capabilities": []}

        # Update agent card with MCP tools
        original_agent_card = get_agent_card()
        if "skills" not in original_agent_card:
            original_agent_card["skills"] = []

        # Add MCP skill if not already present
        mcp_skill = {
            "id": "mcp-connection",
            "name": "MCP Connection",
            "description": "Connect to and use external tools via Model Context Protocol"
        }

        if not any(skill.get("id") == "mcp-connection" for skill in original_agent_card["skills"]):
            original_agent_card["skills"].append(mcp_skill)

        # Update capabilities
        if "capabilities" not in original_agent_card:
            original_agent_card["capabilities"] = []

        if "mcp" not in original_agent_card["capabilities"]:
            original_agent_card["capabilities"].append("mcp")

        print("MCP Blueprint registered successfully")
    except Exception as e:
        print(f"Error registering MCP Blueprint: {e}")