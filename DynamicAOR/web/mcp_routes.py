# cognisphere_adk/web/mcp_routes.py
"""
MCP Web Routes for Cognisphere
Provides Flask routes for MCP server management
"""

import os
import json
import sys
import traceback
from flask import Blueprint, request, jsonify, current_app
import asyncio

# Import from app_globals instead of directly from app
import app_globals

# Create Blueprint
mcp_bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')

# Import the MCP components with robust error handling
try:
    # Add parent directory to sys.path if needed
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Import from the new location
    from mcpIntegration.server_installer import MCPServerManager
    from mcpIntegration.toolset import MCPToolset

    # Initialize server manager
    server_manager = MCPServerManager()

    # Global toolset for managing connections
    toolset = MCPToolset()

    # Flag for import success
    MCP_AVAILABLE = True

except ImportError as e:
    print(f"WARNING: Could not import MCP modules: {e}")
    traceback.print_exc()
    MCP_AVAILABLE = False


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


    server_manager = DummyMCPServerManager()
    toolset = DummyMCPToolset()


# Helper function to run async functions in Flask
def run_async(async_func, *args, **kwargs):
    """
    Improved helper function to run async functions in Flask with proper cleanup.

    This implementation avoids the issue of "attempted to exit cancel scope in different task"
    by ensuring proper task isolation.

    Args:
        async_func: The async function to run
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the async function
    """
    # Create a completely new event loop for this function
    loop = asyncio.new_event_loop()

    # Set it as the current event loop for this thread
    asyncio.set_event_loop(loop)

    try:
        # Create a new async task in this loop
        return loop.run_until_complete(async_func(*args, **kwargs))
    except Exception as e:
        print(f"Error in async execution: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Clean up the loop properly - very important!
        try:
            # Cancel all running tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            # Close the loop
            loop.close()
        except Exception as cleanup_error:
            print(f"Error during event loop cleanup: {cleanup_error}")


@mcp_bp.route('/test', methods=['GET'])
def test_mcp():
    """Simple test endpoint to verify MCP routes are working"""
    try:
        return jsonify({
            "status": "success",
            "message": "MCP routes working",
            "mcp_available": MCP_AVAILABLE
        })
    except Exception as e:
        print(f"Test endpoint error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers', methods=['POST'])
def add_and_connect_server():
    data = request.json
    # 1) Persist the server to your registry
    server_id = server_manager.add_server(
        name=data["name"],  # Changed 'id' to 'name'
        command=data["command"],
        args=data.get("args", []),
        env=data.get("env", {})
    )

    # Get the server configuration
    server_config = server_manager.get_server(server_id)

    # 2) Immediately spin it up
    tools = app_globals.run_async_in_event_loop(
        app_globals.mcp_manager.connect_to_server(
            server_id=server_id,
            command=server_config['command'],
            args=server_config.get('args', []),
            env=server_config.get('env', {})
        )
    )

    if tools and len(tools) > 0:
        print(f"Adding {len(tools)} tools to orchestrator")
        # Add tools to global mcp_tools list
        app_globals.mcp_tools.extend(tools)

        # Also directly add to orchestrator agent's tools if available
        if hasattr(current_app, 'orchestrator_agent'):
            print(f"Adding tools to orchestrator agent directly")
            current_app.orchestrator_agent.tools.extend(tools)

    # 4) Return both the server metadata and its tool list
    return jsonify({
        "status": "success",
        "server_id": server_id,
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "is_long_running": getattr(tool, "is_long_running", False)
            }
            for tool in tools or []
        ],
        "count": len(tools) if tools else 0
    })

@mcp_bp.route('/servers', methods=['GET'])
def list_servers():
    """List all configured MCP servers"""
    try:
        servers = server_manager.list_servers()

        # Remove non-serializable objects
        for server in servers:
            if 'process' in server:
                del server['process']

        return jsonify({
            "status": "success",
            "servers": servers
        })
    except Exception as e:
        print(f"Error listing servers: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    try:
        if not MCP_AVAILABLE:
            return jsonify({"error": "MCP integration is not available"}), 503

        data = request.json
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # Extract server details
        name = data.get('name')
        command = data.get('command')
        args = data.get('args', [])
        env = data.get('env', {})
        install_package = data.get('install_package')

        # Validate required fields
        if not command:
            return jsonify({"error": "Command is required"}), 400

        # Add server
        print(f"Adding server: {name}, command: {command}, args: {args}")
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
        print(f"Error adding server: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>', methods=['DELETE'])
def remove_server(server_id):
    """Remove an MCP server"""
    try:
        if not MCP_AVAILABLE:
            return jsonify({"error": "MCP integration is not available"}), 503

        # Close connection if active
        if hasattr(toolset, 'close_server'):
            run_async(toolset.close_server, server_id)

        # Remove server
        server_manager.remove_server(server_id)

        return jsonify({
            "status": "success",
            "message": f"Server {server_id} removed successfully"
        })

    except Exception as e:
        print(f"Error removing server: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>/connect', methods=['POST'])
def connect_server(server_id):
    """Connect to an MCP server and retrieve tools with improved error handling"""
    try:
        if not MCP_AVAILABLE:
            return jsonify({"error": "MCP integration is not available"}), 503

        # Get server config
        server_config = server_manager.get_server(server_id)
        if not server_config:
            return jsonify({"error": f"Server {server_id} not found"}), 404

        # Create connection parameters - dynamic import to avoid circular dependencies
        try:
            from google.adk.tools.mcp_tool.mcp_toolset import StdioServerParameters
        except ImportError:
            try:
                from mcp import StdioServerParameters
            except ImportError:
                return jsonify({"error": "Could not import StdioServerParameters"}), 500

        connection_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config['args'],
            env=server_config['env']
        )

        # Run the async connection in a separate thread
        # with proper timeout and error handling
        def connect_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    asyncio.wait_for(
                        toolset.register_server(server_id, connection_params),
                        timeout=30.0  # Reasonable timeout for server startup
                    )
                )
            except asyncio.TimeoutError:
                return {"error": f"Timeout connecting to server {server_id}"}
            except Exception as e:
                import traceback
                return {"error": f"Error connecting to server: {str(e)}", "traceback": traceback.format_exc()}
            finally:
                loop.close()

        # Execute in a separate thread to avoid blocking the Flask server
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(connect_async)
            result = future.result(timeout=35.0)  # Give slightly more time than the inner timeout

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return jsonify(result), 500

            # On success, result is the list of tools
            tools = result

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

    except concurrent.futures.TimeoutError:
        # Timeout waiting for the thread to complete
        return jsonify({
            "error": f"Operation timed out while connecting to server {server_id}"
        }), 504
    except Exception as e:
        print(f"Error connecting to server: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/servers/<server_id>/disconnect', methods=['POST'])
def disconnect_server(server_id):
    """Disconnect from an MCP server"""
    try:
        if not MCP_AVAILABLE:
            return jsonify({"error": "MCP integration is not available"}), 503

        # Close connection if the method exists
        if hasattr(toolset, 'close_server'):
            run_async(toolset.close_server, server_id)

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
        print(f"Error disconnecting server: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@mcp_bp.route('/tools', methods=['GET'])
def list_tools():
    """
    List all available MCP tools from servers connected by the global MCPManager.
    This endpoint now relies on app_globals.mcp_manager for connection state.
    """
    try:
        if not MCP_AVAILABLE:  # Assuming MCP_AVAILABLE is correctly set in this file's scope
            return jsonify({"error": "MCP integration is not available in this environment."}), 503

        mcp_manager = app_globals.mcp_manager
        if not mcp_manager:
            # This case should ideally not happen if app.py initializes it correctly.
            return jsonify({"error": "MCP Manager (app_globals.mcp_manager) is not initialized."}), 500

        # Get all ADK-wrapped MCP tools that the manager has discovered and connected.
        # The MCPManager's get_all_tools() method should return these.
        all_adk_wrapped_mcp_tools = mcp_manager.get_all_tools()  # Relies on MCPManager's internal state

        tools_response = []
        if isinstance(all_adk_wrapped_mcp_tools, list):
            for tool in all_adk_wrapped_mcp_tools:
                # The 'tool' objects here are expected to be instances of ADK's BaseTool,
                # specifically MCPTool which should have a 'server_id' attribute added by your MCPManager.
                tools_response.append({
                    "name": getattr(tool, 'name', 'UnknownToolName'),
                    "description": getattr(tool, 'description', 'No description available.'),
                    "server_id": getattr(tool, 'server_id', 'unknown_server_id'),  # MCPTool should have this
                    "is_long_running": getattr(tool, 'is_long_running', False)
                })
        else:
            current_app.logger.error(
                f"/api/mcp/tools: mcp_manager.get_all_tools() did not return a list. Got: {type(all_adk_wrapped_mcp_tools)}")
            # Fallback or error, depending on how strict you want to be
            # For now, return empty if the structure is not a list.
            pass

        # Optional: If no tools are found via the manager, you might log it or
        # indicate that no servers are currently connected or have reported tools.
        if not tools_response and not mcp_manager.connected_servers:
            current_app.logger.info("/api/mcp/tools: No MCP servers appear to be connected via MCPManager.")
        elif not tools_response and mcp_manager.connected_servers:
            current_app.logger.info("/api/mcp/tools: MCP servers are connected, but no tools were reported/formatted.")

        return jsonify({
            "status": "success",
            "tools": tools_response,
            "count": len(tools_response)
        })

    except Exception as e:
        # Use current_app.logger for Flask-specific logging if available and configured
        log_message = f"Error in /api/mcp/tools: {str(e)}\n{traceback.format_exc()}"
        if hasattr(current_app, 'logger'):
            current_app.logger.error(log_message)
        else:
            print(log_message)  # Fallback to print

        return jsonify({"error": "An internal error occurred while listing MCP tools.", "detail": str(e)}), 500


def register_mcp_blueprint(app):
    """Register the MCP blueprint with the Flask app"""
    try:
        app.register_blueprint(mcp_bp)
        print("MCP Blueprint registered successfully")
    except Exception as e:
        print(f"Error registering MCP Blueprint: {e}")
        traceback.print_exc()