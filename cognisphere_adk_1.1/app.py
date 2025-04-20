# -------------------- app.py --------------------

"""
# cognisphere_adk/app.py
Flask application serving as a Web UI for Cognisphere ADK.
"""

import os
from contextlib import AsyncExitStack
import importlib
import sys
import json
import time
import traceback
from typing import Dict, Any
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import asyncio
import logging
import importlib.util

# Create a global module to store shared objects
import app_globals
from agents.mcp_agent import create_mcp_agent
from tools.memory_tools import recall_memories

# Initialize the Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
print("Flask app initialized.")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

# ------ IMPORT SECTION ------
# Import components with try/except to handle potential errors

try:
    # Import the IdentityStore
    from data_models.identity_store import IdentityStore

    # Import ADK components
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.sessions import DatabaseSessionService, Session
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
except ImportError as e:
    print(f"Error importing required modules: {e}")
    traceback.print_exc()
    sys.exit(1)

# ---- Configure LiteLLM ----
try:
    litellm.drop_params = True  # Don't include certain params in request
    litellm.set_verbose = True  # More detailed logging
    litellm.success_callback = []  # Reset callbacks
    litellm.failure_callback = []  # Reset callbacks
    litellm.num_retries = 5  # Add retries

    # Verify OpenRouter configuration
    if not OpenRouterIntegration.configure_openrouter():
        print("Warning: OpenRouter initialization failed – check API key")
except Exception as e:
    print(f"Error configuring LiteLLM: {e}")
    traceback.print_exc()

# ---- Initialize Services ----
try:
    print("Initializing DatabaseService...")
    db_service = DatabaseService(db_path=config.DATABASE_CONFIG["path"])
    print("DatabaseService initialized.")

    print("Initializing EmbeddingService...")
    embedding_service = EmbeddingService()
    print("EmbeddingService initialized.")

    # Initialize the service container
    services_container.initialize_services(db_service, embedding_service)

    # Initialize the IdentityStore with robust error handling
    print("Initializing IdentityStore...")
    try:
        # Ensure the identities directory exists
        identities_dir = os.path.join(config.DATABASE_CONFIG["path"], "identities")
        os.makedirs(identities_dir, exist_ok=True)

        # Create IdentityStore
        identity_store = IdentityStore(identities_dir)

        # Verify default identity exists
        default_identities = identity_store.list_identities()
        if not any(identity['id'] == 'default' for identity in default_identities):
            print("Creating default 'Cupcake' identity...")
            from data_models.identity import Identity

            default_identity = Identity(
                name="Cupcake",
                description="The default Cognisphere identity",
                identity_type="system",
                tone="friendly",
                personality="helpful",
                instruction="You are Cupcake, the default identity for Cognisphere."
            )
            default_identity.id = "default"

            # Save the default identity
            identity_store.save_identity(default_identity)
            print("Default 'Cupcake' identity created successfully.")

        print("IdentityStore initialized.")

        # Add IdentityStore to services_container
        services_container.initialize_identity_store(identity_store)

    except Exception as identity_error:
        print(f"Critical error initializing IdentityStore: {identity_error}")
        print(traceback.format_exc())

        # Fallback: Create a new IdentityStore
        identity_store = IdentityStore()
        services_container.initialize_identity_store(identity_store)
        print("Fallback IdentityStore created.")

except Exception as e:
    print(f"Error initializing database services: {e}")
    traceback.print_exc()

# ---- Initialize MCP toolset ----
mcp_tools = []
function_tools = []


# Create a function to safely run async functions in the event loop
def run_async_in_event_loop(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # already in async context – just await
        return asyncio.ensure_future(coro)
    else:
        return asyncio.run(coro)


# Store these in app_globals for access without circular imports
app_globals.run_async_in_event_loop = run_async_in_event_loop

from mcpIntegration.server_installer import MCPServerManager

# ---- Initialize MCP Manager ----
try:
    # Import the MCP components
    from mcpIntegration.mcp_manager import MCPManager
    from google.adk.tools import FunctionTool
    from google.genai.types import FunctionDeclaration, Schema, Type
    from google.adk.tools.tool_context import ToolContext

    server_manager = MCPServerManager()
    print("Initializing MCP Manager...")
    mcp_manager = MCPManager()

    # Store manager in globals for access without circular imports
    app_globals.mcp_manager = mcp_manager


    # Connect to all configured MCP servers on startup
    # Novo startup async seguro com ExitStack
    async def startup_async():
        async with AsyncExitStack() as stack:
            tools = await mcp_manager.discover_and_connect_servers(mcp_config)
            for exit_stack in mcp_manager.exit_stacks.values():
                await stack.enter_async_context(exit_stack)
            return tools


    try:
        mcp_config_list = server_manager.list_servers()
        mcp_config = {server["id"]: server for server in mcp_config_list}

        tools = run_async_in_event_loop(startup_async())
        print("✅ MCP servers connected at startup.")
    except Exception as connect_error:
        print(f"❌ Error auto-connecting to MCP servers: {connect_error}")

    # Import MCP Tool functions
    from mcpIntegration.tool_handlers import list_mcp_tools, call_mcp_tool

    # Create function tools
    function_tools = [
        FunctionTool(list_mcp_tools),
        FunctionTool(call_mcp_tool)
    ]

    # Store tools in globals for access without circular imports
    app_globals.function_tools = function_tools

except ImportError as e:
    print(f"MCP components not available - proceeding without MCP support: {e}")
except Exception as e:
    print(f"Error initializing MCP: {e}")
    traceback.print_exc()

# ---- Create Session Service ----
try:
    print("Initializing SessionService...")
    db_url = "sqlite:///./cognisphere_sessions.db"
    session_service = DatabaseSessionService(db_url=db_url)
    print("SessionService initialized.")

    # Monkey‑patch append_event to skip events with no content
    _orig_append = session_service.append_event


    def _append_safe(session, event):
        if getattr(event, "content", None) is not None:
            return _orig_append(session, event)
        else:
            print(f"Skipping append for event {getattr(event, 'id', 'N/A')} with no content")


    session_service.append_event = _append_safe

    # Set environment variable for litellm
    os.environ['LITELLM_LOG'] = 'DEBUG'
except Exception as e:
    print(f"Error initializing session service: {e}")
    traceback.print_exc()

# ---- Initialize Agents ----
try:
    print("Initializing Identity Agent...")
    identity_agent = create_identity_agent(model=LiteLlm(model=config.MODEL_CONFIG["orchestrator"]))
    print("Identity Agent initialized.")

    print("Initializing MCP Agent...")
    mcp_agent = create_mcp_agent(model=LiteLlm(model=config.MODEL_CONFIG["orchestrator"]))
    app_globals.mcp_agent = mcp_agent  # Store in globals if needed

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
        mcp_agent=mcp_agent
    )
    print("Orchestrator Agent initialized.")
    app.orchestrator_agent = orchestrator_agent

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
except Exception as e:
    print(f"Error initializing agents: {e}")
    traceback.print_exc()


# ---- Register Blueprints Function ----
# This will be called after app initialization to avoid circular imports
def register_all_blueprints(app):
    try:
        # Import blueprints here to avoid circular imports
        from a2a.server import register_a2a_blueprint
        register_a2a_blueprint(app)
        print("A2A endpoints registered.")

        # Import mcp_routes dynamically
        import web.mcp_routes
        web.mcp_routes.register_mcp_blueprint(app)
        print("MCP endpoints registered.")

        # Register the AIRA blueprint
        from web.aira_routes import register_aira_blueprint
        register_aira_blueprint(app)
        print("AIRA endpoints registered.")
    except Exception as e:
        print(f"Error registering blueprints: {e}")
        traceback.print_exc()


# ---- Helper Functions ----
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

        # Ensure identity catalog is loaded into session state
        initialize_identity_state(session)

    return session


def initialize_identity_state(session: Session):
    # New robust method for initializing identity state
    print("Initializing identity state in session...")

    # Load identity catalog from storage
    identities_list = identity_store.list_identities()
    identities_catalog = {}

    # Convert to session state format
    for identity_info in identities_list:
        identity_id = identity_info["id"]
        identities_catalog[identity_id] = {
            "name": identity_info["name"],
            "type": identity_info["type"],
            "created": identity_info.get("creation_time", "")
        }

    # Store in session state
    session.state["identities"] = identities_catalog

    # Set default identity as active if no active identity
    if "active_identity_id" not in session.state:
        session.state["active_identity_id"] = "default"

    # Load active identity data
    active_id = session.state["active_identity_id"]
    active_identity = identity_store.get_identity(active_id)

    if active_identity:
        # Record access
        identity_store.record_identity_access(active_id)
        # Store in session state
        session.state[f"identity:{active_id}"] = active_identity.to_dict()
        session.state["identity_metadata"] = {
            "name": active_identity.name,
            "type": active_identity.type,
            "last_accessed": active_identity.last_accessed
        }
    else:
        # Fall back to default
        default_identity = identity_store.get_identity("default")
        if default_identity:
            session.state["active_identity_id"] = "default"
            session.state[f"identity:default"] = default_identity.to_dict()
            session.state["identity_metadata"] = {
                "name": default_identity.name,
                "type": default_identity.type,
                "last_accessed": default_identity.last_accessed
            }

    print(f"Loaded {len(identities_catalog)} identities, active identity: {session.state.get('active_identity_id')}")


def process_message(user_id: str, session_id: str, message: str):
    """
    Process a user message with retry mechanism for LiteLLM errors.
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the async function
            result = loop.run_until_complete(_process_message_async(user_id, session_id, message))

            # Close the loop
            loop.close()

            return result

        except Exception as e:
            retry_count += 1
            error_msg = f"Error (attempt {retry_count}/{max_retries}): {str(e)}"
            print(error_msg)
            traceback.print_exc()  # Add this to see the full error trace

            if retry_count < max_retries:
                print(f"Waiting 2 seconds before retry...")
                time.sleep(2)  # Wait before retrying
            else:
                return f"Error processing message: {str(e)}"

    return "Failed to process message after multiple attempts"


def _get_call_ids(part):
    """
    Devolve (call_id, resp_id) ou (None, None) se o atributo existir
    mas estiver vazio.
    """
    call = getattr(part, "function_call", None)
    resp = getattr(part, "function_response", None)
    call_id = getattr(call, "id", None) if call is not None else None
    resp_id = getattr(resp, "id", None) if resp is not None else None
    return call_id, resp_id


def process_session_memory(session, identity_id):
    """
    Transform session into meaningful memories by analyzing emotional content,
    extracting significant moments, and connecting them to identities.

    Args:
        session: The Session object containing the conversation
        identity_id: ID of the active identity
    """
    try:
        print(f"Processing session memory for session {session.id} with identity {identity_id}")

        # Skip if no events in the session
        if not session.events:
            print("No events to process")
            return

        # Extract user messages for analysis
        user_messages = []
        for event in session.events:
            if event.author == "user" and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    user_messages.append(text)

        if not user_messages:
            print("No user messages to process")
            return

        # 1. Analyze emotional content of the session
        from tools.emotion_tools import analyze_emotion

        # Combine messages for overall emotional analysis
        combined_text = " ".join(user_messages)
        emotion_data = analyze_emotion(combined_text)

        # 2. Extract key moments (most emotionally significant or newest)
        key_moments = []

        # Always include the most recent message
        if user_messages:
            key_moments.append({"content": user_messages[-1], "importance": 1.0})

        # Include any high-emotion messages
        if len(user_messages) > 1:
            for msg in user_messages[:-1]:  # Skip the last one we already added
                msg_emotion = analyze_emotion(msg)
                # If emotion score is high (not neutral)
                if msg_emotion["score"] > 0.7:
                    key_moments.append({"content": msg, "importance": msg_emotion["score"]})

        # 3. Create memories from key moments
        from data_models.memory import Memory

        # Get the database service
        db_service = services_container.get_db_service()
        embedding_service = services_container.get_embedding_service()

        if not db_service or not embedding_service:
            print("Database or embedding service not available")
            return

        # Create memories for each key moment
        for moment in key_moments:
            # Determine memory type based on content and emotion
            if emotion_data["emotion_type"] in ["joy", "excitement", "curiosity"]:
                memory_type = "emotional"
            elif emotion_data["score"] > 0.8:
                memory_type = "flashbulb"  # Highly significant memories
            else:
                memory_type = "explicit"  # Regular factual memories

            # Create the memory object
            memory = Memory(
                content=moment["content"],
                memory_type=memory_type,
                emotion_data=emotion_data,
                source="session",
                identity_id=identity_id,
                source_identity=identity_id
            )

            # Generate embedding and store in database
            embedding = embedding_service.encode(moment["content"])
            if embedding:
                db_service.add_memory(memory, embedding)
                print(f"Created {memory_type} memory: {moment['content'][:50]}...")

        # 4. Connect to narrative if appropriate
        # Check if there's a related narrative thread
        if hasattr(session.state, "current_thread_id") and session.state["current_thread_id"]:
            thread_id = session.state["current_thread_id"]
            thread = db_service.get_thread(thread_id)

            if thread:
                # Add an event to the thread
                thread.add_event(
                    content=f"Session {session.id} added {len(key_moments)} memories",
                    emotion=emotion_data["emotion_type"],
                    impact=emotion_data["score"],
                    identity_id=identity_id
                )

                # Save the thread
                db_service.save_thread(thread)

        print(f"Memory processing complete: Created {len(key_moments)} memories")

    except Exception as e:
        print(f"Error processing session memory: {e}")
        traceback.print_exc()


async def _process_message_async(user_id: str, session_id: str, message: str):
    # Retrieve previous session's context
    previous_sessions = session_service.list_sessions(
        app_name=app_name,
        user_id=user_id
    )

    # Get the most recent session before the current one
    context_memories = []
    if previous_sessions:
        # Modified code to handle different types of session responses
        session_ids = []

        # Check if it's a ListSessionsResponse with session_ids attribute
        if hasattr(previous_sessions, 'session_ids'):
            session_ids = previous_sessions.session_ids
        # Check if it's a list/tuple of strings (session IDs)
        elif isinstance(previous_sessions, (list, tuple)) and previous_sessions and isinstance(previous_sessions[0],
                                                                                               str):
            session_ids = previous_sessions

        # Now get full session objects for each ID
        full_sessions = []
        for sess_id in session_ids:
            if sess_id != session_id:  # Skip current session
                try:
                    full_session = session_service.get_session(
                        app_name=app_name,
                        user_id=user_id,
                        session_id=sess_id
                    )
                    if full_session and hasattr(full_session, 'last_update_time'):
                        full_sessions.append(full_session)
                except Exception as e:
                    print(f"Error getting session {sess_id}: {e}")
                    continue

        # Sort by last update time if we have full sessions
        if full_sessions:
            try:
                sorted_sessions = sorted(
                    full_sessions,
                    key=lambda s: getattr(s, 'last_update_time', 0),
                    reverse=True
                )

                # Get memories from previous sessions to inject context
                for prev_session in sorted_sessions[:3]:  # Limit to last 3 sessions
                    try:
                        memories_result = recall_memories(
                            tool_context=ToolContext(
                                state={},
                                agent_name="memory_agent"
                            ),
                            query=message,
                            limit=3,
                            identity_filter=None,
                            include_all_identities=False
                        )

                        # Check if memories_result is a valid dictionary with memories
                        if isinstance(memories_result, dict) and "memories" in memories_result:
                            context_memories.extend(memories_result.get("memories", []))
                    except Exception as memory_error:
                        print(f"Error recalling memories for session {prev_session.id}: {memory_error}")
                        continue
            except Exception as sort_error:
                print(f"Error sorting sessions: {sort_error}")

    # ------------- helpers internos -----------------------------------------
    def _extract_ids(part):
        """
        Returns (call_id, resp_id) or (None, None) if the attribute exists but is None.
        """
        call = getattr(part, "function_call", None)
        resp = getattr(part, "function_response", None)
        call_id = getattr(call, "id", None) if call is not None else None
        resp_id = getattr(resp, "id", None) if resp is not None else None
        return call_id, resp_id

    # ------------------------------------------------------------------------

    session = ensure_session(user_id, session_id)

    # Prepare message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=message)])

    final_response_text = "No response generated."
    pending_tool_calls = {}
    all_events = []

    try:
        # Create a safe wrapper for the iterator to catch any exceptions
        async def safe_run():
            async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content
            ):
                yield event

        async for event in safe_run():
            if event is None or event.content is None:
                print("Warning: Received None event from runner")
                continue

            all_events.append(event)  # Keep track of all events, even those without content initially

            # Only proceed with content-specific logic if there's usable content
            if not (event.content and event.content.parts):
                # Log if needed, but don't try to access parts[0]
                # print(f"Debug: Event {getattr(event, 'id', 'N/A')} has no content or parts.")
                continue

            # Additional safety check for parts (redundant if above check passes, but safe)
            if not event.content.parts:
                continue

            part = event.content.parts[0]
            if part is None:
                continue

            call_id, resp_id = _extract_ids(part)

            # ---------- Register pending / resolve pending -----------------
            if call_id:
                pending_tool_calls[call_id] = True
            if resp_id:
                pending_tool_calls.pop(resp_id, None)
            # -----------------------------------------------------------------

            # ---------- Final response from model -----------------------------
            if event.is_final_response() and hasattr(part, "text") and part.text is not None:
                final_response_text = part.text
            # -----------------------------------------------------------------

        # ... (fallback logic for final_response_text) ...

    except Exception as e:
        print(f"Error during runner.run_async: {e}")
        traceback.print_exc()  # Add this to see the full stack trace
        final_response_text = f"Error processing message: {e}"

    # ---------------- Persistence & memory ---------------------
    try:
        # --- FIX STARTS HERE ---
        # Only attempt to append the last event if it exists AND has content
        if all_events:
            last_event = all_events[-1]
            if last_event is not None and last_event.content is not None:
                try:
                    session_service.append_event(session, last_event)
                    print(f"Successfully appended event {getattr(last_event, 'id', 'N/A')}")

                    # Trigger memory and narrative processing only after successful append
                    process_session_memory(session, session.state.get("active_identity_id", "default"))

                except Exception as append_error:
                    print(f"Error appending event {getattr(last_event, 'id', 'N/A')}: {append_error}")
                    traceback.print_exc()
            elif last_event is not None:
                print(
                    f"Warning: Last event (ID: {getattr(last_event, 'id', 'N/A')}, Author: {getattr(last_event, 'author', 'N/A')}) has None content. Skipping append.")
            else:
                print("Warning: Last event was None. Skipping append.")
        else:
            print("Warning: No events were generated. Skipping append.")
        # --- FIX ENDS HERE ---

    except Exception as mem_error:
        print(f"Error during post-processing (memory/narrative): {mem_error}")
        traceback.print_exc()

    return final_response_text


# --- Routes ---
@app.route('/')
def index():
    """Render the main UI page."""
    return render_template('index.html')


@app.route('/api/sessions/all', methods=['GET'])
def get_all_sessions():
    """Get ALL sessions for a user - direct database query approach."""
    user_id = request.args.get('user_id', 'default_user')

    try:
        # DIRECT DATABASE QUERY to ensure we get ALL sessions
        import sqlite3

        # Get database path from the database URL in session_service
        db_path = "cognisphere_sessions.db"  # This should match your actual DB path

        # Define the app_name - this matches what's used in the Flask app
        app_name_value = "cognisphere_adk"  # This should match your app_name in app.py

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Updated query using update_time instead of last_update_time
        cursor.execute('''
            SELECT id, app_name, user_id, update_time, state
            FROM sessions
            WHERE app_name = ? AND user_id = ?
            ORDER BY update_time DESC
        ''', (app_name_value, user_id))

        all_sessions = []
        for row in cursor.fetchall():
            session_id, app_name, user_id, update_time, state_json = row

            # Extract a title/preview from the state
            title = f"Conversation {session_id[:8]}"
            try:
                # Parse state as JSON to extract more context
                state = json.loads(state_json)

                # Try to get a meaningful title from state or memories
                if 'last_orchestrator_response' in state:
                    title = state['last_orchestrator_response'][:50] + '...'
                elif 'last_recalled_memories' in state:
                    memories = state.get('last_recalled_memories', [])
                    if memories:
                        title = memories[0].get('content', title)[:50] + '...'
            except:
                pass  # Use default title if parsing fails

            all_sessions.append({
                'id': session_id,
                'timestamp': update_time,
                'title': title
            })

        conn.close()

        # Always ensure default is included
        default_exists = any(s['id'] == 'default_session' for s in all_sessions)
        if not default_exists:
            all_sessions.append({
                'id': 'default_session',
                'timestamp': time.time(),
                'title': 'Default conversation'
            })

        return jsonify({
            'sessions': all_sessions
        })

    except Exception as e:
        print(f"Error in get_all_sessions: {e}")
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'sessions': [{
                'id': 'default_session',
                'timestamp': time.time(),
                'title': 'Default conversation'
            }]
        })


@app.route('/api/sessions/create', methods=['POST'])
def create_session():
    """Create a new session explicitly."""
    user_id = request.json.get('user_id', 'default_user')

    # Generate a unique session ID
    session_id = f"session_{int(time.time())}"

    try:
        # Create session with initial state
        session = session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={
                "created_at": datetime.now().isoformat(),
                "active_identity_id": "default"
            }
        )

        return jsonify({
            "session_id": session_id,
            "created_at": session.last_update_time,
            "message": "New session created successfully"
        })
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# Update the get_sessions function in app.py
@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get available sessions for a user."""
    user_id = request.args.get('user_id', 'default_user')

    try:
        # Get all sessions for this user
        session_response = session_service.list_sessions(
            app_name=app_name,
            user_id=user_id
        )

        # Format session data for frontend
        session_data = []

        # Handle different types of session responses
        print(f"Session response type: {type(session_response)}")

        # If response is a ListSessionsResponse object with session_ids attribute
        if hasattr(session_response, 'session_ids'):
            for session_id in session_response.session_ids:
                try:
                    # Get full session to extract data
                    full_session = session_service.get_session(
                        app_name=app_name,
                        user_id=user_id,
                        session_id=session_id
                    )

                    # Get last update time - use time.time() as fallback
                    last_update = getattr(full_session, 'last_update_time', int(time.time()))

                    # Extract last message if available
                    last_message = None
                    if hasattr(full_session, 'events') and full_session.events:
                        for event in reversed(full_session.events):
                            if event.author == "user" and event.content and event.content.parts:
                                last_message = event.content.parts[0].text
                                break

                    # Escolhe o preview de forma mais amigável
                    if last_message:
                        preview_text = last_message[:50] + ('...' if len(last_message) > 50 else '')
                    else:
                        preview_text = "🆕 New conversation"

                    session_data.append({
                        "id": session_id,
                        "last_update": last_update,
                        "preview": preview_text
                    })

                except Exception as session_error:
                    print(f"Error processing session {session_id}: {session_error}")
                    # Include a default entry even on error
                    session_data.append({
                        "id": session_id,
                        "last_update": int(time.time()),
                        "preview": "Error loading session"
                    })

        # Handle tuple or list responses
        elif isinstance(session_response, (tuple, list)):
            for item in session_response:
                if isinstance(item, str):  # Session ID
                    session_data.append({
                        "id": item,
                        "last_update": int(time.time()),
                        "preview": f"Session {item[:8]}..."
                    })
                elif hasattr(item, 'id'):  # Session object
                    # Use getattr with default for safety
                    last_update = getattr(item, 'last_update_time', int(time.time()))
                    session_data.append({
                        "id": item.id,
                        "last_update": last_update,
                        "preview": f"Session conversation"
                    })

        # If no sessions found or unhandled type, create a default
        if not session_data:
            session_data.append({
                "id": "default_session",
                "last_update": int(time.time()),
                "preview": "Default conversation"
            })

        # Sort by last update time (newest first)
        session_data.sort(key=lambda x: x["last_update"], reverse=True)

        return jsonify({
            'sessions': session_data
        })

    except Exception as e:
        print(f"Error in /api/sessions: {e}")
        traceback.print_exc()
        # Return a minimal valid response to prevent UI errors
        return jsonify({
            'sessions': [{
                "id": "default_session",
                "last_update": int(time.time()),
                "preview": f"Error loading sessions: {str(e)}"
            }]
        }), 200  # Use 200 to keep frontend logic consistent


@app.route('/api/session/messages', methods=['GET'])
def get_session_messages():
    """Get messages for a specific session with robust error handling."""
    user_id = request.args.get('user_id', 'default_user')
    session_id = request.args.get('session_id')

    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    try:
        # Get the session
        session = session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )

        if not session:
            return jsonify({'error': 'Session not found'}), 404

        # Extract messages from events with robust error handling
        messages = []
        if hasattr(session, 'events'):
            for event in session.events:
                # Handle user messages
                if event.author == "user" and event.content and event.content.parts:
                    try:
                        text = event.content.parts[0].text
                        if text:
                            messages.append({
                                "role": "user",
                                "content": text,
                                "timestamp": getattr(event, 'timestamp', 0)
                            })
                    except (AttributeError, IndexError) as e:
                        print(f"Error extracting user message: {e}")
                        continue

                # Handle assistant responses
                elif event.author != "user" and event.is_final_response() and event.content and event.content.parts:
                    try:
                        text = event.content.parts[0].text
                        if text:
                            messages.append({
                                "role": "assistant",
                                "content": text,
                                "timestamp": getattr(event, 'timestamp', 0)
                            })
                    except (AttributeError, IndexError) as e:
                        print(f"Error extracting assistant message: {e}")
                        continue

        return jsonify({
            'session_id': session_id,
            'messages': messages
        })

    except Exception as e:
        print(f"Error in /api/session/messages: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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


@app.route('/api/mcp/debug', methods=['GET'])
def debug_mcp():
    """Debug endpoint to check MCP status"""
    try:
        # Import from app_globals
        mcp_manager = app_globals.mcp_manager

        # Check if manager exists
        if not mcp_manager:
            return jsonify({"error": "MCP manager not initialized"}), 500

        # Get list of connected servers
        connected = list(mcp_manager.connected_servers.keys())

        # Get server manager's list
        from mcpIntegration.server_installer import MCPServerManager
        server_manager = MCPServerManager()
        configured = server_manager.list_servers()

        return jsonify({
            "status": "success",
            "connected_servers": connected,
            "configured_servers": configured,
            "mcp_manager_type": str(type(mcp_manager))
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


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


# Identity-related API endpoints

@app.route('/api/identities', methods=['GET'])
def get_identities():
    """Get available identities with extensive error handling."""
    print("VERBOSE: Received request for /api/identities")

    try:
        # Get identity store from services container
        identity_store = services_container.get_identity_store()

        if not identity_store:
            print("CRITICAL: Identity store is None!")
            return jsonify({
                'error': 'Identity store not available',
                'identities': [],
                'active_identity_id': 'default',
                'count': 0
            }), 500

        # List identities with extensive logging
        try:
            identities_list = identity_store.list_identities()
            print(f"VERBOSE: Found {len(identities_list)} identities")
        except Exception as list_error:
            print(f"CRITICAL ERROR listing identities: {list_error}")
            print(f"VERBOSE Traceback: {traceback.format_exc()}")
            identities_list = [{
                "id": "default",
                "name": "Cupcake",
                "description": "Fallback System Identity",
                "type": "system"
            }]

        return jsonify({
            'identities': identities_list,
            'active_identity_id': 'default',
            'count': len(identities_list)
        })

    except Exception as e:
        print(f"CRITICAL UNHANDLED ERROR: {e}")
        print(f"VERBOSE Traceback: {traceback.format_exc()}")

        return jsonify({
            'error': str(e),
            'identities': [{
                "id": "default",
                "name": "Cupcake",
                "description": "Fallback Identity",
                "type": "system"
            }],
            'active_identity_id': 'default',
            'count': 1
        }), 500


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

        # Get identity store from services container
        identity_store = services_container.get_identity_store()

        # Get identity from persistent storage
        identity = identity_store.get_identity(identity_id)
        if not identity:
            return jsonify({
                "error": f"Identity with ID {identity_id} not found"
            }), 404

        # Record access in persistent storage
        identity_store.record_identity_access(identity_id)

        # Update session state
        session.state["active_identity_id"] = identity_id
        session.state[f"identity:{identity_id}"] = identity.to_dict()
        session.state["identity_metadata"] = {
            "name": identity.name,
            "type": identity.type,
            "last_accessed": identity.last_accessed
        }

        # Save session
        session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )

        return jsonify({
            'status': 'success',
            'active_identity_id': identity_id,
            'active_identity_name': identity.name,
            'message': f"Switched to identity: {identity.name}"
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
    # Register all blueprints after app is fully initialized
    register_all_blueprints(app)
    os.makedirs('templates', exist_ok=True)

    # Create a basic index.html template if it doesn't exist

    # Run the app

    try:
        print("Starting Flask app...")
        # Get local IP dynamically
        import socket

        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"Attempting to start server on:")

        # Add threading and detailed error handling
        app.run(
            host='localhost',
            port=8095,
            debug=True,
            threaded=True,  # Enable threading
            use_reloader=False  # Disable reloader to get full error traces
        )
    except Exception as e:
        print(f"CRITICAL SERVER START ERROR: {e}")
        print(traceback.format_exc())