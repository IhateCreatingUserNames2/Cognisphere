"""
AIRA Web Routes for Cognisphere
-------------------------------
Provides Flask routes for AIRA integration, allowing Cognisphere to:
1. Serve as an A2A agent endpoint
2. Manage AIRA hub connections
3. Discover and interact with other agents
"""

import asyncio
import json
import traceback
from flask import Blueprint, request, jsonify, current_app

# Import AIRA modules
from ..aira.client import CognisphereAiraClient
from ..aira.tools import (
    setup_aira_client,
    register_all_cognisphere_tools_with_aira,
    aira_tools
)

# Create Blueprint
aira_bp = Blueprint('aira', __name__, url_prefix='/api/aira')


# Async helper function for Flask
def run_async(coroutine):
    """Run an async function from a synchronous Flask route."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


# Initialize AIRA client
aira_client = None


# ========== AIRA Hub Management Routes ==========

@aira_bp.route('/connect', methods=['POST'])
def connect_hub():
    """Connect to an AIRA hub."""
    global aira_client

    data = request.json
    hub_url = data.get('hub_url')
    agent_url = data.get('agent_url')
    agent_name = data.get('agent_name', 'Cognisphere')

    if not hub_url or not agent_url:
        return jsonify({
            "error": "Missing required parameters: hub_url and agent_url are required"
        }), 400

    try:
        # Initialize AIRA client
        aira_client = setup_aira_client(hub_url, agent_url, agent_name)

        # Start the client and register with hub
        result = run_async(aira_client.start())

        # Register Cognisphere tools with AIRA
        register_all_cognisphere_tools_with_aira()

        # Register AIRA tools with ADK's global orchestrator agent
        if hasattr(current_app, 'orchestrator_agent'):
            current_app.orchestrator_agent.tools.extend(aira_tools)

        return jsonify({
            "status": "success",
            "message": f"Connected to AIRA hub at {hub_url}",
            "hub_url": hub_url,
            "agent_url": agent_url
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to connect to AIRA hub: {str(e)}"
        }), 500


@aira_bp.route('/disconnect', methods=['POST'])
def disconnect_hub():
    """Disconnect from the AIRA hub."""
    global aira_client

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        # Clean up client resources
        hub_url = aira_client.hub_url
        run_async(aira_client.stop())
        aira_client = None

        # Remove AIRA tools from orchestrator agent
        if hasattr(current_app, 'orchestrator_agent'):
            current_app.orchestrator_agent.tools = [
                t for t in current_app.orchestrator_agent.tools
                if t not in aira_tools
            ]

        return jsonify({
            "status": "success",
            "message": f"Disconnected from AIRA hub at {hub_url}"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to disconnect from AIRA hub: {str(e)}"
        }), 500


@aira_bp.route('/status', methods=['GET'])
def hub_status():
    """Get current AIRA connection status."""
    global aira_client

    if not aira_client:
        return jsonify({
            "status": "disconnected",
            "connected": False
        })

    return jsonify({
        "status": "connected" if aira_client.registered else "connecting",
        "connected": aira_client.registered,
        "hub_url": aira_client.hub_url,
        "agent_url": aira_client.agent_url,
        "agent_name": aira_client.agent_name
    })


@aira_bp.route('/hubs', methods=['GET'])
def get_hubs():
    """Get available AIRA hubs."""
    global aira_client

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        hubs = run_async(aira_client.get_available_hubs())
        return jsonify({
            "status": "success",
            "hubs": hubs,
            "current_hub": aira_client.hub_url
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to get AIRA hubs: {str(e)}"
        }), 500


@aira_bp.route('/switch-hub', methods=['POST'])
def switch_hub():
    """Switch to a different AIRA hub."""
    global aira_client

    data = request.json
    hub_url = data.get('hub_url')

    if not hub_url:
        return jsonify({
            "error": "Missing required parameter: hub_url"
        }), 400

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        run_async(aira_client.switch_hub(hub_url))
        return jsonify({
            "status": "success",
            "message": f"Switched to AIRA hub at {hub_url}",
            "new_hub": hub_url
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to switch hub: {str(e)}"
        }), 500


# ========== AIRA Discovery Routes ==========

@aira_bp.route('/discover/agents', methods=['GET'])
def discover_agents():
    """Discover agents on the AIRA network."""
    global aira_client

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        agents = run_async(aira_client.discover_agents())
        return jsonify({
            "status": "success",
            "count": len(agents),
            "agents": agents
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to discover agents: {str(e)}"
        }), 500


@aira_bp.route('/discover/tools', methods=['GET'])
def discover_tools():
    """Discover tools from an agent on the AIRA network."""
    global aira_client

    agent_url = request.args.get('agent_url')

    if not agent_url:
        return jsonify({
            "error": "Missing required parameter: agent_url"
        }), 400

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        tools = run_async(aira_client.discover_agent_tools(agent_url))
        return jsonify({
            "status": "success",
            "agent_url": agent_url,
            "count": len(tools),
            "tools": tools
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to discover tools: {str(e)}"
        }), 500


@aira_bp.route('/invoke', methods=['POST'])
def invoke_tool():
    """Invoke a tool from an agent on the AIRA network."""
    global aira_client

    data = request.json
    agent_url = data.get('agent_url')
    tool_name = data.get('tool_name')
    parameters = data.get('parameters', {})

    if not agent_url or not tool_name:
        return jsonify({
            "error": "Missing required parameters: agent_url and tool_name are required"
        }), 400

    if not aira_client:
        return jsonify({
            "error": "Not connected to any AIRA hub"
        }), 400

    try:
        result = run_async(aira_client.invoke_agent_tool(agent_url, tool_name, parameters))
        return jsonify({
            "status": "success",
            "agent_url": agent_url,
            "tool_name": tool_name,
            "result": result
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to invoke tool: {str(e)}"
        }), 500


# ========== A2A Endpoint ==========

@aira_bp.route('/a2a', methods=['POST'])
def a2a_endpoint():
    """Handle A2A requests from other agents."""
    global aira_client

    if not aira_client:
        return jsonify({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32000,
                "message": "AIRA client not initialized"
            }
        }), 400

    try:
        # Get request body
        request_body = request.data.decode('utf-8')

        # Handle request through AIRA client
        response = run_async(aira_client.handle_a2a_request(request_body))

        # Return response
        return jsonify(response)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32000,
                "message": f"Error handling request: {str(e)}"
            }
        }), 500


@aira_bp.route('/.well-known/agent.json', methods=['GET'])
def well_known_agent():
    """Serve the agent card for A2A discovery."""
    global aira_client

    if not aira_client:
        return jsonify({
            "error": "AIRA client not initialized"
        }), 400

    try:
        # Generate agent card
        agent_card = aira_client._generate_agent_card()
        return jsonify(agent_card)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Failed to generate agent card: {str(e)}"
        }), 500


def register_aira_blueprint(app):
    """Register the AIRA blueprint with the Flask app."""
    app.register_blueprint(aira_bp)

    # Add routes to the /.well-known/agent.json at root level
    @app.route('/.well-known/agent.json')
    def root_agent_card():
        return well_known_agent()
