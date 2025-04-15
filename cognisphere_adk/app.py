"""# cognisphere_adk/app.py
Flask application serving as a Web UI for Cognisphere ADK.
"""

import os
import sys
import json
from typing import Dict, Any
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import asyncio
import importlib.util

# Import ADK components
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.genai import types
import litellm

# Import Cognisphere components
from agents.identity_agent import create_identity_agent
from agents.memory_agent import create_memory_agent
from agents.narrative_agent import create_narrative_agent
from agents.orchestrator_agent import create_orchestrator_agent
from services.database import DatabaseService
from services.embedding import EmbeddingService
import services_container
from callbacks.safety import content_filter_callback, tool_argument_validator
import config
from services.openrouter_setup import OpenRouterIntegration
from a2a.server import register_a2a_blueprint
from web.mcp_routes import register_mcp_blueprint

# Configure LiteLLM
litellm.drop_params = True  # Don't include certain params in request
litellm.set_verbose = True  # More detailed logging
litellm.success_callback = []  # Reset callbacks
litellm.failure_callback = []  # Reset callbacks
litellm.num_retries = 5  # Add retries

# Verify OpenRouter configuration
if not OpenRouterIntegration.configure_openrouter():
    raise RuntimeError("OpenRouter initialization failed – check API key")

# Initialize the Flask app
app = Flask(__name__)
print("Flask app initialized.")

# --- Initialize Services ---
print("Initializing DatabaseService...")
db_service = DatabaseService(db_path=config.DATABASE_CONFIG["path"])
print("DatabaseService initialized.")

print("Initializing EmbeddingService...")
embedding_service = EmbeddingService()
print("EmbeddingService initialized.")

# Initialize the service container
services_container.initialize_services(db_service, embedding_service)

# Initialize MCP toolset (if available)
try:
    # Try to import MCP components
    from mcp.toolset import MCPToolset
    from mcp.server_installer import MCPServerManager

    print("Initializing MCP components...")
    mcp_toolset = MCPToolset()
    mcp_server_manager = MCPServerManager()
    # Collect MCP tools
    mcp_tools = mcp_toolset.get_mcp_tools()
    print(f"MCP initialized with {len(mcp_tools)} tools")
except ImportError:
    print("MCP components not available - proceeding without MCP support")
    mcp_tools = []

# --- Create Session Service ---
print("Initializing SessionService...")
session_service = InMemorySessionService()
print("SessionService initialized.")

# Set environment variable for litellm
os.environ['LITELLM_LOG'] = 'DEBUG'

# --- Initialize Agents ---
print("Initializing Identity Agent...")
identity_agent = create_identity_agent(model=LiteLlm(model=config.MODEL_CONFIG["orchestrator"]))
print("Identity Agent initialized.")

# Set up sub-agents
print("Initializing Memory Agent...")
memory_agent = create_memory_agent(model=LiteLlm(model=config.MODEL_CONFIG["memory"]))
print("Memory Agent initialized.")

print("Initializing Narrative Agent...")
narrative_agent = create_narrative_agent(model=LiteLlm(model=config.MODEL_CONFIG["narrative"]))
print("Narrative Agent initialized.")

# Create orchestrator
print("Initializing Orchestrator Agent...")
orchestrator_agent = create_orchestrator_agent(
    model=LiteLlm(model=config.MODEL_CONFIG["orchestrator"]),
    memory_agent=memory_agent,
    narrative_agent=narrative_agent,
    identity_agent=identity_agent,
    mcp_tools=mcp_tools  # Pass collected MCP tools
)
print("Orchestrator Agent initialized.")

# Add safety callbacks if enabled
if config.SAFETY_CONFIG["enable_content_filter"]:
    orchestrator_agent.before_model_callback = content_filter_callback

if config.SAFETY_CONFIG["enable_tool_validation"]:
    orchestrator_agent.before_tool_callback = tool_argument_validator

# Create Runner
app_name = "cognisphere_adk"
runner = Runner(
    agent=orchestrator_agent,
    app_name=app_name,
    session_service=session_service
)

# --- Register the blueprints ---
register_a2a_blueprint(app)
print("A2A endpoints registered.")

register_mcp_blueprint(app)
print("MCP endpoints registered.")

# --- Helper Functions ---
def ensure_session(user_id: str, session_id: str) -> Session:
    """
    Ensure a session exists and is initialized with service objects.
    """
    session = session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )

    if not session:
        # Create a new session with initialized state
        initial_state = {
            "user_preference_temperature_unit": "Celsius"
        }

        session = session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state
        )

    return session


def initialize_default_identity():
    """
    Create a default identity if none exists
    """
    print("Initializing default identity...")
    default_session = ensure_session('default_user', 'default_session')

    # Check if identities catalog exists
    if "identities" not in default_session.state:
        default_session.state["identities"] = {}

    # Check if default identity exists
    if "default" not in default_session.state["identities"]:
        # Create default identity
        default_identity = {
            "id": "default",
            "name": "Cupcake",
            "description": "The default Cognisphere identity",
            "type": "system",
            "tone": "friendly",
            "personality": "helpful",
            "instruction": "You are Cupcake, the default identity.",
            "creation_time": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": {
                "creation_source": "system",
                "access_count": 0
            }
        }

        # Store identity
        default_session.state["identities"]["default"] = {
            "name": "Cupcake",
            "type": "system",
            "created": datetime.now().isoformat()
        }

        default_session.state["identity:default"] = default_identity
        default_session.state["active_identity_id"] = "default"
        print("Created default identity: Cupcake")
    else:
        print("Default identity already exists")

def process_message(user_id: str, session_id: str, message: str):
    """
    Process a user message through the orchestrator agent.
    This is a synchronous wrapper around the asynchronous function.
    """
    # Run the async code in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_message_async(user_id, session_id, message))
    finally:
        loop.close()

async def _process_message_async(user_id: str, session_id: str, message: str):
    """
    Process a user message through the orchestrator agent.
    """
    # Ensure session exists
    session = ensure_session(user_id, session_id)

    # Prepare the user's message in ADK format
    content = types.Content(role='user', parts=[types.Part(text=message)])

    try:
        final_response_text = "No response generated."
        all_events = []

        # Process the message through runner.run_async
        async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
        ):
            all_events.append(event)

            # Check if this is a final response event
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text

        # If no final response was found but we have events
        if final_response_text == "No response generated." and all_events:
            # Look for the last event with text content
            for event in reversed(all_events):
                if event.content and event.content.parts and hasattr(event.content.parts[0], 'text') and \
                        event.content.parts[0].text:
                    final_response_text = event.content.parts[0].text
                    break

    except Exception as e:
        print(f"Error during runner.run_async: {e}")
        final_response_text = f"Error processing message: {e}"

    return final_response_text


# --- Routes ---
@app.route('/')
def index():
    """Render the main UI page."""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages."""
    data = request.json
    user_message = data.get('message', '')
    user_id = data.get('user_id', 'default_user')
    session_id = data.get('session_id', 'default_session')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Process the message through the orchestrator
        response = process_message(user_id, session_id, user_message)

        # Return the response
        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in /api/chat: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/memories', methods=['GET'])
def get_memories():
    """Get recent memories."""
    print("Received request for /api/memories")
    user_id = request.args.get('user_id', 'default_user')
    session_id = request.args.get('session_id', 'default_session')

    try:
        # Ensure session exists
        session = ensure_session(user_id, session_id)

        # Get memories from session state if available
        memories = session.state.get("last_recalled_memories", [])

        # Ensure it's a list even if None
        if memories is None:
            memories = []

        # Verify each item has the expected properties
        for memory in memories.copy():  # Use copy to avoid modification during iteration
            if not isinstance(memory, dict):
                print(f"Warning: Invalid memory format found: {memory}")
                memories.remove(memory)
                continue

            # Ensure essential fields exist
            if "content" not in memory:
                memory["content"] = "Unknown content"
            if "type" not in memory:
                memory["type"] = "unknown"
            if "emotion" not in memory:
                memory["emotion"] = "neutral"
            if "relevance" not in memory:
                memory["relevance"] = 0.5

        return jsonify({
            'memories': memories,
            'count': len(memories)
        })
    except Exception as e:
        print(f"Error in /api/memories: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        print("Finished processing /api/memories")


@app.route('/api/identities', methods=['GET'])
def get_identities():
    """Get available identities."""
    print("Received request for /api/identities")
    user_id = request.args.get('user_id', 'default_user')
    session_id = request.args.get('session_id', 'default_session')

    try:
        # Ensure session exists
        session = ensure_session(user_id, session_id)

        # Get identities from session state
        identities_catalog = session.state.get("identities", {})
        active_id = session.state.get("active_identity_id")

        print(f"Found identities catalog: {identities_catalog}")
        print(f"Active identity: {active_id}")

        # Format the response
        identities = []
        for identity_id, basic_info in identities_catalog.items():
            # Get full identity data if available
            full_data = session.state.get(f"identity:{identity_id}")

            identity = {
                "id": identity_id,
                "name": basic_info.get("name", "Unknown"),
                "type": basic_info.get("type", "unknown"),
                "is_active": identity_id == active_id
            }

            # Add additional details if available
            if full_data:
                identity["description"] = full_data.get("description", "")
                identity["personality"] = full_data.get("personality", "")
                identity["tone"] = full_data.get("tone", "")

            identities.append(identity)

        return jsonify({
            'identities': identities,
            'active_identity_id': active_id,
            'count': len(identities)
        })
    except Exception as e:
        print(f"Error in /api/identities: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        print("Finished processing /api/identities")


@app.route('/api/identities/switch', methods=['POST'])
def switch_identity():
    """Switch the active identity."""
    print("Received request for /api/identities/switch")
    data = request.json
    user_id = data.get('user_id', 'default_user')
    session_id = data.get('session_id', 'default_session')
    identity_id = data.get('identity_id')

    if not identity_id:
        return jsonify({"error": "identity_id is required"}), 400

    try:
        # Ensure session exists
        session = ensure_session(user_id, session_id)

        # Check if identity exists and get the name
        identity_data = session.state.get(f"identity:{identity_id}")
        identity_name = "Unknown"
        if identity_data and isinstance(identity_data, dict):
            identity_name = identity_data.get("name", "Unknown")

        # Direct state manipulation for simple operations
        session.state["active_identity_id"] = identity_id
        session.state["identity_metadata"] = {
            "name": identity_name,
            "type": identity_data.get("type", "unknown") if identity_data else "unknown",
            "last_accessed": datetime.now().isoformat()
        }

        # Save the updated state
        session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )

        return jsonify({
            'status': 'success',
            'active_identity_id': identity_id,
            'active_identity_name': identity_name,
            'message': f"Switched to identity: {identity_name}"
        })
    except Exception as e:
        print(f"Error in /api/identities/switch: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        print("Finished processing /api/identities/switch")


@app.route('/api/narratives', methods=['GET'])
def get_narratives():
    """Get active narrative threads."""
    print("Received request for /api/narratives")
    user_id = request.args.get('user_id', 'default_user')
    session_id = request.args.get('session_id', 'default_session')

    try:
        # Get all threads from database
        threads = db_service.get_all_threads()

        # Filter for active threads
        active_threads = [thread.to_dict() for thread in threads if thread.status == "active"]

        return jsonify({
            'threads': active_threads,
            'count': len(active_threads)
        })
    except Exception as e:
        print(f"Error in /api/narratives: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        print("Finished processing /api/narratives")


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status information."""
    print("Received request for /api/status")
    try:
        # Check services
        components = {
            'database_service': bool(db_service),
            'embedding_service': bool(embedding_service),
            'memory_agent': bool(memory_agent),
            'narrative_agent': bool(narrative_agent),
            'orchestrator_agent': bool(orchestrator_agent),
            'identity_agent': bool(identity_agent),
            'runner': bool(runner)
        }

        return jsonify({
            'system_online': all(components.values()),
            'timestamp': datetime.now().isoformat(),
            'components': components
        })
    except Exception as e:
        print(f"Error in /api/status: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        print("Finished processing /api/status")


# --- Run the Application ---
if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)

    # Create a basic index.html template if it doesn't exist
    index_path = os.path.join('templates', 'index.html')
    if not os.path.exists(index_path):
        with open(index_path, 'w') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Cognisphere ADK</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f7f9fc;
        }
        .mcp-config-panel, .mcp-tools-panel {
            margin-top: 15px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
    }
    
        .mcp-server-item {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #eee;
            border-radius: 6px;
            background-color: #f9f9f9;
        }
        
        .mcp-tool-item {
            margin-bottom: 10px;
            padding: 8px;
            border: 1px solid #eee;
            border-radius: 4px;
            background-color: #f5f5f5;
        }
        
        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .server-header h4 {
            margin: 0;
        }
        
        .server-actions {
            display: flex;
            gap: 8px;
        }
        
        .server-details {
            font-size: 0.9em;
        }
        
        .server-details p {
            margin: 4px 0;
        }
        .container {
            display: flex;
            height: 100vh;
            max-width: 1400px;
            margin: 0 auto;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .chat-panel {
            flex: 2;
            display: flex;
            flex-direction: column;
            padding: 20px;
            background-color: white;
            border-right: 1px solid #ddd;
        }
        .info-panel {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background-color: #f0f4f8;
        }
        .chat-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .chat-header h1 {
            margin: 0;
            color: #4a6fa5;
        }
        .identity-selector {
            margin-left: 15px;
            display: flex;
            align-items: center;
        }
        .identity-selector select {
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ccc;
            margin-left: 5px;
        }
        .chat-history {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 8px;
            border: 1px solid #eee;
        }
        .chat-input {
            display: flex;
            gap: 10px;
        }
        .chat-input input {
            flex: 1;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 15px;
        }
        .chat-input button {
            padding: 12px 20px;
            background-color: #4a6fa5;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        .chat-input button:hover {
            background-color: #3a5a85;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px 15px;
            border-radius: 8px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .user {
            background-color: #e1f5fe;
            margin-left: auto;
            text-align: right;
            border-bottom-right-radius: 0;
        }
        .assistant {
            background-color: #f1f1f1;
            margin-right: auto;
            border-bottom-left-radius: 0;
        }
        .section {
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .section h2 {
            margin-top: 0;
            color: #4a6fa5;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        button.action {
            background-color: #4a6fa5;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
        }
        button.action:hover {
            background-color: #3a5a85;
        }
        .status {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #ddd;
        }
        .status-online {
            background-color: #4CAF50;
        }
        .status-offline {
            background-color: #f44336;
        }
        .memory-item, .thread-item, .identity-item {
            padding: 10px;
            border: 1px solid #eee;
            border-radius: 4px;
            margin-bottom: 10px;
            background-color: #fafbfc;
        }
        .identity-item.active {
            border: 1px solid #4a6fa5;
            background-color: #e6f2ff;
        }
        .thread-item h3, .identity-item h3 {
            margin-top: 0;
            color: #4a6fa5;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        .memory-item .relevance {
            font-size: 0.8em;
            color: #666;
        }
        .identity-actions {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
        }
        .identity-form {
            margin-top: 15px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            display: none; /* Hidden by default */
        }
        .identity-form.active {
            display: block;
        }
        .form-group {
            margin-bottom: 10px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .form-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-panel">
            <div class="chat-header">
                <h1>Cognisphere ADK</h1>
                <div class="status" style="margin-left: 15px;">
                    <div class="status-indicator" id="status-indicator"></div>
                    <span id="status-text">Checking status...</span>
                </div>
                <div class="identity-selector">
                    <label for="identity-select">Identity:</label>
                    <select id="identity-select">
                        <option value="">Loading...</option>
                    </select>
                </div>
            </div>
            <div class="chat-history" id="chat-history"></div>
            <div class="chat-input">
                <input type="text" id="user-input" placeholder="Ask Cognisphere something..." />
                <button id="send-button">Send</button>
            </div>
        </div>
        <div class="info-panel">
            <div class="section">
                <h2>System Status</h2>
                <div id="component-status">Loading...</div>
            </div>
            <div class="section">
                <h2>Current Identity</h2>
                <div id="current-identity">No active identity</div>
                <button class="action" id="create-identity-button">Create New Identity</button>
                
                <!-- Identity Creation Form -->
                <div class="identity-form" id="identity-form">
                    <div class="form-group">
                        <label for="identity-name">Name:</label>
                        <input type="text" id="identity-name" placeholder="Name of identity">
                    </div>
                    <div class="form-group">
                        <label for="identity-description">Description:</label>
                        <textarea id="identity-description" placeholder="Brief description"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="identity-tone">Tone:</label>
                        <select id="identity-tone">
                            <option value="friendly">Friendly</option>
                            <option value="professional">Professional</option>
                            <option value="casual">Casual</option>
                            <option value="formal">Formal</option>
                            <option value="enthusiastic">Enthusiastic</option>
                            <option value="serious">Companion</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="identity-personality">Personality:</label>
                        <input type="text" id="identity-personality" placeholder="e.g., curious, analytical, creative">
                    </div>
                    <div class="form-actions">
                        <button class="action" id="cancel-identity">Cancel</button>
                        <button class="action" id="save-identity">Create Identity</button>
                    </div>
                </div>
            </div>
            <div class="section">
                <h2>Identities</h2>
                <div id="identities">Loading...</div>
                <button class="action" id="refresh-identities-button">Refresh Identities</button>
            </div>
            <div class="section">
                <h2>Memories</h2>
                <div id="memories">Loading...</div>
                <button class="action" id="recall-button">Recall Memories</button>
            </div>
            <div class="section" id="mcp-section">
    <h2>MCP Integration</h2>
    <div class="mcp-status">
        <div class="status">
            <div class="status-indicator" id="mcp-status-indicator"></div>
            <span id="mcp-status-text">MCP Integration Status</span>
        </div>
        <button class="action" id="mcp-config-toggle">Configure MCP</button>
    </div>
    
    <!-- MCP Configuration Panel (Hidden by default) -->
    <div class="mcp-config-panel" id="mcp-config-panel" style="display: none;">
        <h3>Connected MCP Servers</h3>
        <div id="mcp-server-list">
            <p>No servers connected</p>
        </div>
        
        <h3>Add New MCP Server</h3>
        <div class="form-group">
            <label for="mcp-server-name">Server Name (optional):</label>
            <input type="text" id="mcp-server-name" placeholder="e.g., filesystem-server">
        </div>
        <div class="form-group">
            <label for="mcp-server-command">Command:</label>
            <input type="text" id="mcp-server-command" placeholder="e.g., npx">
        </div>
        <div class="form-group">
            <label for="mcp-server-args">Arguments (comma-separated):</label>
            <input type="text" id="mcp-server-args" placeholder="e.g., -y,@modelcontextprotocol/server-filesystem,/path/to/folder">
        </div>
        <div class="form-group">
            <label for="mcp-server-package">Install Package (optional):</label>
            <input type="text" id="mcp-server-package" placeholder="e.g., @modelcontextprotocol/server-filesystem">
        </div>
        <div class="form-group">
            <label for="mcp-server-env">Environment Variables (JSON):</label>
            <textarea id="mcp-server-env" placeholder='{"API_KEY": "your-key-here"}'></textarea>
        </div>
        <div class="form-actions">
            <button class="action" id="mcp-add-server-btn">Add Server</button>
            <button class="action" id="mcp-cancel-btn">Cancel</button>
        </div>
    </div>  
        <!-- MCP Tools Panel (Hidden by default) -->
        <div class="mcp-tools-panel" id="mcp-tools-panel" style="display: none;">
            <h3>Available MCP Tools</h3>
            <div id="mcp-tools-list">
                <p>No MCP tools available</p>
            </div>
        </div>
                <div class="section">
                <h2>Narrative Threads</h2>
                <div id="narrative-threads">Loading...</div>
                <button class="action" id="get-threads-button">Update Threads</button>
            </div>
            
            
                
           
        </div>
    </div>

   <script>
    // Global variables
    const USER_ID = 'default_user';
    const SESSION_ID = 'default_session';

    // Helper function for API calls
    async function fetchAPI(url, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            return { error: error.message };
        }
    }

    // Initialize the UI
    document.addEventListener('DOMContentLoaded', () => {
        const chatHistory = document.getElementById('chat-history');
        const userInput = document.getElementById('user-input');
        const sendButton = document.getElementById('send-button');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        const componentStatus = document.getElementById('component-status');
        const memoriesDiv = document.getElementById('memories');
        const narrativeThreadsDiv = document.getElementById('narrative-threads');
        const recallButton = document.getElementById('recall-button');
        const getThreadsButton = document.getElementById('get-threads-button');
        
        // mcp
        const mcpStatusIndicator = document.getElementById('mcp-status-indicator');
        const mcpStatusText = document.getElementById('mcp-status-text');
        const mcpConfigToggle = document.getElementById('mcp-config-toggle');
        const mcpConfigPanel = document.getElementById('mcp-config-panel');
        const mcpServerList = document.getElementById('mcp-server-list');
        const mcpToolsPanel = document.getElementById('mcp-tools-panel');
        const mcpToolsList = document.getElementById('mcp-tools-list');
        const mcpAddServerBtn = document.getElementById('mcp-add-server-btn');
        const mcpCancelBtn = document.getElementById('mcp-cancel-btn');
        
        // Identity-related elements
        const identitySelect = document.getElementById('identity-select');
        const identitiesDiv = document.getElementById('identities');
        const currentIdentityDiv = document.getElementById('current-identity');
        const refreshIdentitiesButton = document.getElementById('refresh-identities-button');
        const createIdentityButton = document.getElementById('create-identity-button');
        const identityForm = document.getElementById('identity-form');
        const saveIdentityButton = document.getElementById('save-identity');
        const cancelIdentityButton = document.getElementById('cancel-identity');
        
        // Toggle MCP configuration panel
        mcpConfigToggle.addEventListener('click', () => {
            const isVisible = mcpConfigPanel.style.display !== 'none';
            mcpConfigPanel.style.display = isVisible ? 'none' : 'block';
            mcpConfigToggle.textContent = isVisible ? 'Configure MCP' : 'Hide Configuration';
            
            // If showing, refresh server list
            if (!isVisible) {
                refreshMcpServers();
            }
        });
        
        // Cancel button
        mcpCancelBtn.addEventListener('click', () => {
            mcpConfigPanel.style.display = 'none';
            mcpConfigToggle.textContent = 'Configure MCP';
            
            // Clear input fields
            document.getElementById('mcp-server-name').value = '';
            document.getElementById('mcp-server-command').value = '';
            document.getElementById('mcp-server-args').value = '';
            document.getElementById('mcp-server-package').value = '';
            document.getElementById('mcp-server-env').value = '';
        });
        
        // Add server button
        mcpAddServerBtn.addEventListener('click', async () => {
            // Get input values
            const name = document.getElementById('mcp-server-name').value.trim();
            const command = document.getElementById('mcp-server-command').value.trim();
            const argsString = document.getElementById('mcp-server-args').value.trim();
            const packageName = document.getElementById('mcp-server-package').value.trim();
            const envJson = document.getElementById('mcp-server-env').value.trim();
            
            // Validate required fields
            if (!command) {
                alert('Command is required');
                return;
            }
            
            // Parse arguments
            const args = argsString ? argsString.split(',').map(arg => arg.trim()) : [];
            
            // Parse environment variables
            let env = {};
            if (envJson) {
                try {
                    env = JSON.parse(envJson);
                } catch (e) {
                    alert('Invalid JSON for environment variables');
                    return;
                }
            }
            
            // Show loading state
            mcpAddServerBtn.disabled = true;
            mcpAddServerBtn.textContent = 'Adding Server...';
            
            try {
                // Send request to add server
                const response = await fetch('/api/mcp/servers', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name,
                        command,
                        args,
                        env,
                        install_package: packageName
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert('MCP server added successfully');
                    
                    // Clear input fields
                    document.getElementById('mcp-server-name').value = '';
                    document.getElementById('mcp-server-command').value = '';
                    document.getElementById('mcp-server-args').value = '';
                    document.getElementById('mcp-server-package').value = '';
                    document.getElementById('mcp-server-env').value = '';
                    
                    // Refresh server list
                    refreshMcpServers();
                } else {
                    alert(`Error adding server: ${result.error || 'Unknown error'}`);
                }
            } catch (e) {
                alert(`Error adding server: ${e.message}`);
            } finally {
                // Reset button
                mcpAddServerBtn.disabled = false;
                mcpAddServerBtn.textContent = 'Add Server';
            }
        });
        
        // Refresh MCP servers
        async function refreshMcpServers() {
            try {
                // Fetch servers
                const response = await fetch('/api/mcp/servers');
                const data = await response.json();
                
                if (response.ok && data.servers) {
                    // Update MCP status
                    const serversCount = data.servers.length;
                    mcpStatusIndicator.className = `status-indicator ${serversCount > 0 ? 'status-online' : 'status-offline'}`;
                    mcpStatusText.textContent = `MCP Integration: ${serversCount} servers configured`;
                    
                    // Update server list
                    if (serversCount === 0) {
                        mcpServerList.innerHTML = '<p>No servers configured</p>';
                    } else {
                        mcpServerList.innerHTML = '';
                        
                        data.servers.forEach(server => {
                            const serverItem = document.createElement('div');
                            serverItem.className = 'mcp-server-item';
                            
                            const statusClass = server.status === 'running' ? 'status-online' : 'status-offline';
                            
                            serverItem.innerHTML = `
                                <div class="server-header">
                                    <div class="status">
                                        <div class="status-indicator ${statusClass}"></div>
                                        <h4>${server.id}</h4>
                                    </div>
                                    <div class="server-actions">
                                        <button class="action connect-server" data-id="${server.id}">
                                            ${server.status === 'running' ? 'Disconnect' : 'Connect'}
                                        </button>
                                        <button class="action remove-server" data-id="${server.id}">Remove</button>
                                    </div>
                                </div>
                                <div class="server-details">
                                    <p><strong>Command:</strong> ${server.command} ${server.args.join(' ')}</p>
                                    <p><strong>Status:</strong> ${server.status}</p>
                                    <p><strong>Created:</strong> ${new Date(server.created_at).toLocaleString()}</p>
                                </div>
                            `;
                            
                            mcpServerList.appendChild(serverItem);
                        });
                        
                        // Add event listeners for server actions
                        document.querySelectorAll('.connect-server').forEach(button => {
                            button.addEventListener('click', async () => {
                                const serverId = button.dataset.id;
                                const isConnected = button.textContent.trim() === 'Disconnect';
                                
                                if (isConnected) {
                                    await disconnectServer(serverId);
                                } else {
                                    await connectServer(serverId);
                                }
                                
                                // Refresh server list
                                refreshMcpServers();
                                
                                // Refresh tools list
                                refreshMcpTools();
                            });
                        });
                        
                        document.querySelectorAll('.remove-server').forEach(button => {
                            button.addEventListener('click', async () => {
                                const serverId = button.dataset.id;
                                
                                if (confirm(`Are you sure you want to remove server ${serverId}?`)) {
                                    // First disconnect if connected
                                    try {
                                        await disconnectServer(serverId);
                                    } catch (e) {
                                        // Ignore disconnection errors during removal
                                    }
                                    
                                    // Then remove
                                    await removeServer(serverId);
                                    
                                    // Refresh server list
                                    refreshMcpServers();
                                    
                                    // Refresh tools list
                                    refreshMcpTools();
                                }
                            });
                        });
                    }
                } else {
                    mcpStatusIndicator.className = 'status-indicator status-offline';
                    mcpStatusText.textContent = 'MCP Integration: Error fetching servers';
                }
            } catch (e) {
                mcpStatusIndicator.className = 'status-indicator status-offline';
                mcpStatusText.textContent = 'MCP Integration: Error fetching servers';
                console.error('Error fetching MCP servers:', e);
            }
        }
        
        // Connect to an MCP server
        async function connectServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}/connect`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    console.log(`Connected to server ${serverId}`);
                    console.log('Available tools:', result.tools);
                    
                    // Show and update tools panel
                    showMcpTools(result.tools);
                    
                    return true;
                } else {
                    alert(`Error connecting to server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error connecting to server: ${e.message}`);
                return false;
            }
        }
        
        // Disconnect from an MCP server
        async function disconnectServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}/disconnect`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    console.log(`Disconnected from server ${serverId}`);
                    return true;
                } else {
                    alert(`Error disconnecting from server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error disconnecting from server: ${e.message}`);
                return false;
            }
        }
        
        // Remove an MCP server
        async function removeServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    console.log(`Removed server ${serverId}`);
                    return true;
                } else {
                    alert(`Error removing server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error removing server: ${e.message}`);
                return false;
            }
        }
        
        // Show MCP tools
        function showMcpTools(tools) {
            // Show tools panel
            mcpToolsPanel.style.display = 'block';
            
            // Update tools list
            if (!tools || tools.length === 0) {
                mcpToolsList.innerHTML = '<p>No MCP tools available</p>';
            } else {
                mcpToolsList.innerHTML = '';
                
                tools.forEach(tool => {
                    const toolItem = document.createElement('div');
                    toolItem.className = 'mcp-tool-item';
                    
                    toolItem.innerHTML = `
                        <h4>${tool.name}</h4>
                        <p>${tool.description || 'No description available'}</p>
                        <p><small>${tool.is_long_running ? 'Long running' : 'Standard'} tool</small></p>
                    `;
                    
                    mcpToolsList.appendChild(toolItem);
                });
            }
        }
        
        // Refresh MCP tools
        async function refreshMcpTools() {
            try {
                const response = await fetch('/api/mcp/tools');
                const data = await response.json();
                
                if (response.ok) {
                    if (data.count > 0) {
                        showMcpTools(data.tools);
                    } else {
                        mcpToolsPanel.style.display = 'none';
                    }
                }
            } catch (e) {
                console.error('Error fetching MCP tools:', e);
            }
        }
        
        // Initial refresh
        refreshMcpServers();
        refreshMcpTools();

        // Chat functionality
        sendButton.addEventListener('click', sendMessage);
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            // Add user message to chat
            addMessageToChat('user', message);
            userInput.value = '';

            // Show thinking indicator
            addMessageToChat('assistant', 'Thinking...', 'thinking');

            // Send to backend
            const response = await fetchAPI('/api/chat', 'POST', { 
                message,
                user_id: USER_ID,
                session_id: SESSION_ID
            });

            // Remove thinking indicator and add response
            const thinkingElement = document.querySelector('.thinking');
            if (thinkingElement) {
                chatHistory.removeChild(thinkingElement);
            }

            if (response.error) {
                addMessageToChat('assistant', `Error: ${response.error}`);
            } else {
                addMessageToChat('assistant', response.response);

                // Refresh UI data after interaction
                updateMemories();
                updateNarrativeThreads();
                updateIdentities(); // Refresh identities too
            }
        }

        function addMessageToChat(role, content, className) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}${className ? ' ' + className : ''}`;
            messageDiv.textContent = content;
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // System status
        async function updateSystemStatus() {
            const status = await fetchAPI('/api/status');

            if (status.error) {
                statusIndicator.className = 'status-indicator status-offline';
                statusText.textContent = 'System Offline';
                return;
            }

            statusIndicator.className = 'status-indicator status-online';
            statusText.textContent = 'System Online';

            // Update component status
            const components = status.components;
            let componentHTML = '<ul style="list-style: none; padding: 0;">';
            for (const [name, isActive] of Object.entries(components)) {
                const statusClass = isActive ? 'status-online' : 'status-offline';
                const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                componentHTML += `<li style="display: flex; align-items: center; margin-bottom: 5px;">
                    <div class="status-indicator ${statusClass}" style="margin-right: 10px;"></div> ${label}
                </li>`;
            }
            componentHTML += '</ul>';
            componentStatus.innerHTML = componentHTML;
        }

        // Memories
        async function updateMemories() {
            const result = await fetchAPI(`/api/memories?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                memoriesDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            if (!result.memories || result.memories.length === 0) {
                memoriesDiv.innerHTML = '<p>No memories recalled yet.</p>';
                return;
            }

            let memoriesHTML = '';
            for (const memory of result.memories) {
                const relevancePercent = Math.round((memory.relevance || 0) * 100);
                const identityName = memory.identity_name ? `<div class="identity">Identity: ${memory.identity_name}</div>` : '';
                
                memoriesHTML += `
                    <div class="memory-item">
                        <div>${memory.content}</div>
                        ${identityName}
                        <div class="relevance">Type: ${memory.type || 'unknown'}, Emotion: ${memory.emotion || 'neutral'}, Relevance: ${relevancePercent}%</div>
                    </div>
                `;
            }

            memoriesDiv.innerHTML = memoriesHTML;
        }

        // Narrative threads
        async function updateNarrativeThreads() {
            const result = await fetchAPI(`/api/narratives?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                narrativeThreadsDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            if (!result.threads || result.threads.length === 0) {
                narrativeThreadsDiv.innerHTML = '<p>No active narrative threads.</p>';
                return;
            }

            let threadsHTML = '';
            for (const thread of result.threads) {
                const lastUpdated = new Date(thread.last_updated).toLocaleString();

                // Get linked identities if available
                let identitiesHTML = '';
                if (thread.linked_identity_names && thread.linked_identity_names.length > 0) {
                    identitiesHTML = `<div><strong>Linked Identities:</strong> ${thread.linked_identity_names.join(', ')}</div>`;
                }

                // Get last event if available
                let lastEventText = 'No events yet';
                if (thread.events && thread.events.length > 0) {
                    const lastEvent = thread.events[thread.events.length - 1];
                    lastEventText = lastEvent.content || 'Event with no content';
                }

                threadsHTML += `
                    <div class="thread-item">
                        <h3>${thread.title}</h3>
                        <div>${thread.description}</div>
                        <div><strong>Theme:</strong> ${thread.theme}</div>
                        ${identitiesHTML}
                        <div><strong>Latest:</strong> ${lastEventText}</div>
                        <div><strong>Last updated:</strong> ${lastUpdated}</div>
                    </div>
                `;
            }

            narrativeThreadsDiv.innerHTML = threadsHTML;
        }

        // Identity Management Functions
        async function updateIdentities() {
            const result = await fetchAPI(`/api/identities?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                identitiesDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                identitySelect.innerHTML = '<option value="">Error loading</option>';
                return;
            }

            if (!result.identities || result.identities.length === 0) {
                identitiesDiv.innerHTML = '<p>No identities created yet.</p>';
                identitySelect.innerHTML = '<option value="">No identities</option>';
                return;
            }

            // Update identities list
            let identitiesHTML = '';
            identitySelect.innerHTML = ''; // Clear previous options

            for (const identity of result.identities) {
                const isActive = identity.is_active;
                const activeClass = isActive ? 'active' : '';
                const activeText = isActive ? ' (Active)' : '';
                
                // Add to dropdown
                const option = document.createElement('option');
                option.value = identity.id;
                option.textContent = identity.name + activeText;
                option.selected = isActive;
                identitySelect.appendChild(option);
                
                // Add to identities section
                identitiesHTML += `
                    <div class="identity-item ${activeClass}">
                        <h3>${identity.name}${activeText}</h3>
                        <div>${identity.description || 'No description'}</div>
                        <div><strong>Type:</strong> ${identity.type}</div>
                        <div class="identity-actions">
                            ${!isActive ? 
                                `<button class="action switch-identity" data-id="${identity.id}">Switch to this identity</button>` : 
                                '<span>Current identity</span>'}
                        </div>
                    </div>
                `;
            }

            identitiesDiv.innerHTML = identitiesHTML;

            // Update current identity display
            const activeIdentity = result.identities.find(i => i.is_active);
            if (activeIdentity) {
                currentIdentityDiv.innerHTML = `
                    <div class="identity-item active">
                        <h3>${activeIdentity.name}</h3>
                        <div>${activeIdentity.description || 'No description'}</div>
                        <div><strong>Type:</strong> ${activeIdentity.type}</div>
                    </div>
                `;
            } else {
                currentIdentityDiv.innerHTML = '<p>No active identity</p>';
            }

            // Add event listeners to switch identity buttons
            document.querySelectorAll('.switch-identity').forEach(button => {
                button.addEventListener('click', async () => {
                    const identityId = button.dataset.id;
                    await switchIdentity(identityId);
                });
            });
        }

        async function switchIdentity(identityId) {
            // Show loading state
            currentIdentityDiv.innerHTML = '<div class="loading">Switching identity...</div>';
            
            // Request identity switch
            const result = await fetchAPI('/api/identities/switch', 'POST', {
                user_id: USER_ID,
                session_id: SESSION_ID,
                identity_id: identityId
            });
            
            // Handle response
            if (result.error) {
                currentIdentityDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }
            
            // Add system message about identity switch
            addMessageToChat('assistant', `Switched to identity: ${result.active_identity_name}`);
            
            // Refresh identities
            updateIdentities();
            
            // Also refresh memories and narratives as they may be filtered by identity
            updateMemories();
            updateNarrativeThreads();
        }

        // Identity creation form
        createIdentityButton.addEventListener('click', () => {
            identityForm.classList.add('active');
        });
        
        cancelIdentityButton.addEventListener('click', () => {
            identityForm.classList.remove('active');
            // Clear form fields
            document.getElementById('identity-name').value = '';
            document.getElementById('identity-description').value = '';
            document.getElementById('identity-personality').value = '';
        });
        
        saveIdentityButton.addEventListener('click', async () => {
            const name = document.getElementById('identity-name').value.trim();
            const description = document.getElementById('identity-description').value.trim();
            const tone = document.getElementById('identity-tone').value;
            const personality = document.getElementById('identity-personality').value.trim();
            
            if (!name) {
                alert('Please provide a name for the identity');
                return;
            }
            
            // Construct message to create identity
            const message = `Create a new identity with these details: 
                Name: ${name}
                Description: ${description}
                Tone: ${tone}
                Personality: ${personality}`;
            
            // Show thinking indicator
            addMessageToChat('assistant', 'Creating identity...', 'thinking');
            
            // Send to backend
            const response = await fetchAPI('/api/chat', 'POST', { 
                message,
                user_id: USER_ID,
                session_id: SESSION_ID
            });
            
            // Remove thinking indicator
            const thinkingElement = document.querySelector('.thinking');
            if (thinkingElement) {
                chatHistory.removeChild(thinkingElement);
            }
            
            if (response.error) {
                addMessageToChat('assistant', `Error: ${response.error}`);
            } else {
                addMessageToChat('assistant', response.response);
                
                // Reset and hide form
                identityForm.classList.remove('active');
                document.getElementById('identity-name').value = '';
                document.getElementById('identity-description').value = '';
                document.getElementById('identity-personality').value = '';
                
                // Refresh identities
                updateIdentities();
            }
        });

        // Identity dropdown change handler
        identitySelect.addEventListener('change', async () => {
            const selectedId = identitySelect.value;
            if (selectedId) {
                await switchIdentity(selectedId);
            }
        });

        // Button handlers
        recallButton.addEventListener('click', () => {
            memoriesDiv.innerHTML = '<div class="loading">Recalling memories...</div>';
            updateMemories();
        });

        getThreadsButton.addEventListener('click', () => {
            narrativeThreadsDiv.innerHTML = '<div class="loading">Updating threads...</div>';
            updateNarrativeThreads();
        });
        
        refreshIdentitiesButton.addEventListener('click', () => {
            identitiesDiv.innerHTML = '<div class="loading">Refreshing identities...</div>';
            updateIdentities();
        });

        // Initial data load
        updateSystemStatus();
        updateMemories();
        updateNarrativeThreads();
        updateIdentities();

        // Add a welcome message
        addMessageToChat('assistant', 'Welcome to Cognisphere ADK! How can I help you today?');

        // Refresh status every minute
        setInterval(updateSystemStatus, 60000);
    });
</script>
</body>
</html>''')
        print(f"Created template at {index_path}")

    # Run the app
    initialize_default_identity()
    print("Starting Flask app...")
    app.run(host='0.0.0.0', debug=True)
