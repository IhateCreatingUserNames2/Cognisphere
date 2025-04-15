# cognisphere_adk/tools/narrative_tools.py
from google.adk.tools.tool_context import ToolContext
from data_models.narrative import NarrativeThread
from services_container import get_db_service
from typing import Optional, Dict, Any, List


def create_narrative_thread(
        title: str,
        theme: str = "general",
        description: str = "",
        identity_id: Optional[str] = None,  # New parameter
        tool_context: ToolContext = None
) -> dict:
    """
    Creates a new narrative thread.

    Args:
        title: The title of the thread
        theme: The theme/category of the thread
        description: A description of the thread
        identity_id: Optional ID of the identity to associate with this thread
        tool_context: Tool context for accessing session state

    Returns:
        dict: Information about the created thread
    """
    # Access db_service from container
    db_service = get_db_service()

    if not db_service:
        return {"status": "error", "message": "Database service not available"}

    # Get active identity if none specified
    if not identity_id:
        identity_id = tool_context.state.get("active_identity_id")

    linked_identities = []
    if identity_id:
        linked_identities.append(identity_id)

        # Get identity data for context
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            identity_name = identity_data.get("name", "Unknown")
        else:
            identity_name = "Unknown"

    # Create thread object with identity link
    thread = NarrativeThread(
        title=title,
        theme=theme,
        description=description,
        linked_identities=linked_identities
    )

    # Store in database
    thread_id = db_service.save_thread(thread)

    # Save current thread ID to state
    if tool_context:
        tool_context.state["current_thread_id"] = thread_id

    # If identity is specified, also update identity's linked narratives
    if identity_id:
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            if "linked_narratives" not in identity_data:
                identity_data["linked_narratives"] = {}

            identity_data["linked_narratives"][thread_id] = {
                "relationship": "creator",
                "linked_at": thread.creation_time
            }

            tool_context.state[f"identity:{identity_id}"] = identity_data

            identity_context = f" for identity '{identity_name}'"
        else:
            identity_context = ""
    else:
        identity_context = ""

    return {
        "status": "success",
        "thread_id": thread_id,
        "message": f"Narrative thread '{title}' created successfully{identity_context}"
    }


def add_thread_event(
        thread_id: str,
        content: str,
        emotion: str = "neutral",
        impact: float = 0.5,
        identity_id: Optional[str] = None,  # New parameter
        tool_context: ToolContext = None
) -> dict:
    """
    Adds an event to a narrative thread.

    Args:
        thread_id: ID of the thread to add to
        content: Content of the event
        emotion: Emotional context of the event
        impact: Impact/significance score (0.0-1.0)
        identity_id: Optional ID of the identity creating this event
        tool_context: Tool context for accessing session state

    Returns:
        dict: Result of the operation
    """
    # Access db_service from container
    db_service = get_db_service()

    if not db_service:
        return {"status": "error", "message": "Database service not available"}

    # Get the thread
    thread = db_service.get_thread(thread_id)
    if not thread:
        return {"status": "error", "message": f"Thread with ID {thread_id} not found"}

    # Get active identity if none specified
    if not identity_id:
        identity_id = tool_context.state.get("active_identity_id")

    # Get identity name for context
    identity_name = "Unknown"
    if identity_id:
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            identity_name = identity_data.get("name", "Unknown")

    # Add event with identity information
    event_id = thread.add_event(content, emotion, impact, identity_id)

    # Save thread
    db_service.save_thread(thread)

    # Update identity-narrative link if needed
    if identity_id:
        # Initialize metadata if not present
        if not hasattr(thread, 'metadata') or thread.metadata is None:
            thread.metadata = {}

        # Add identity to linked_identities if not already present
        if "linked_identities" not in thread.metadata:
            thread.metadata["linked_identities"] = []

        if identity_id not in thread.metadata["linked_identities"]:
            thread.metadata["linked_identities"].append(identity_id)
            db_service.save_thread(thread)

        # Also update identity's linked_narratives
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            if "linked_narratives" not in identity_data:
                identity_data["linked_narratives"] = {}

            if thread_id not in identity_data["linked_narratives"]:
                identity_data["linked_narratives"][thread_id] = {
                    "relationship": "contributor",
                    "linked_at": thread.last_updated
                }

                tool_context.state[f"identity:{identity_id}"] = identity_data

        identity_context = f" by identity '{identity_name}'"
    else:
        identity_context = ""

    return {
        "status": "success",
        "event_id": event_id,
        "thread_id": thread_id,
        "message": f"Event added to thread successfully{identity_context}"
    }


def get_active_threads(
        limit: int = 5,
        identity_id: Optional[str] = None,  # New parameter
        tool_context: ToolContext = None
) -> dict:
    """
    Retrieves active narrative threads.

    Args:
        limit: Maximum number of threads to return
        identity_id: Optional filter for threads linked to a specific identity
        tool_context: Tool context for accessing session state

    Returns:
        dict: Active narrative threads
    """
    # Access db_service from container
    db_service = get_db_service()

    if not db_service:
        return {"status": "error", "message": "Database service not available"}

    # Get all threads
    all_threads = db_service.get_all_threads()

    # Use active identity if none specified
    if not identity_id:
        identity_id = tool_context.state.get("active_identity_id")

    # Get identity name for context
    identity_name = None
    if identity_id:
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            identity_name = identity_data.get("name")

    # Filter active threads
    active_threads = [thread for thread in all_threads if thread.status == "active"]

    # Apply identity filter if specified
    if identity_id:
        identity_threads = []

        for thread in active_threads:
            # Check if thread has metadata with linked_identities
            has_identity = False

            if hasattr(thread, 'metadata') and thread.metadata:
                linked_identities = thread.metadata.get("linked_identities", [])
                if identity_id in linked_identities:
                    has_identity = True

            if has_identity:
                identity_threads.append(thread)

        active_threads = identity_threads

    # Sort by importance
    active_threads.sort(key=lambda t: t.importance, reverse=True)

    # Limit results
    result_threads = active_threads[:limit]

    # Convert to dictionaries
    thread_dicts = []
    for thread in result_threads:
        thread_dict = thread.to_dict()

        # Add additional identity context
        if hasattr(thread, 'metadata') and thread.metadata:
            linked_identities = thread.metadata.get("linked_identities", [])

            # Get identity names
            identity_names = []
            for id in linked_identities:
                id_data = tool_context.state.get(f"identity:{id}")
                if id_data:
                    identity_names.append(id_data.get("name", "Unknown"))

            thread_dict["linked_identity_names"] = identity_names

        thread_dicts.append(thread_dict)

    response = {
        "status": "success",
        "count": len(thread_dicts),
        "threads": thread_dicts
    }

    # Add identity context if applicable
    if identity_name:
        response["identity_context"] = identity_name

    return response


def generate_narrative_summary(
        thread_id: Optional[str] = None,
        identity_id: Optional[str] = None,  # New parameter
        tool_context: ToolContext = None
) -> dict:
    """
    Generates a narrative summary for a thread or all active threads.

    Args:
        thread_id: Optional ID of specific thread to summarize
        identity_id: Optional filter for threads linked to a specific identity
        tool_context: Tool context for accessing session state

    Returns:
        dict: The narrative summary
    """
    # Access db_service from container
    db_service = get_db_service()

    if not db_service:
        return {"status": "error", "message": "Database service not available"}

    # Use active identity if none specified
    if not identity_id:
        identity_id = tool_context.state.get("active_identity_id")

    # Get identity name for context
    identity_name = None
    if identity_id:
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            identity_name = identity_data.get("name")

    if thread_id:
        # Get specific thread
        thread = db_service.get_thread(thread_id)
        if not thread:
            return {"status": "error", "message": f"Thread with ID {thread_id} not found"}

        # Check if this thread is linked to the specified identity
        identity_linked = False
        if identity_id and hasattr(thread, 'metadata') and thread.metadata:
            linked_identities = thread.metadata.get("linked_identities", [])
            if identity_id in linked_identities:
                identity_linked = True

        # Only include identity context if linked or no identity filter
        if not identity_id or identity_linked:
            # Generate summary for single thread
            summary = f"Thread: {thread.title}\nTheme: {thread.theme}\nStatus: {thread.status}\n\n"

            # Add identity context if applicable
            if hasattr(thread, 'metadata') and thread.metadata:
                linked_identities = thread.metadata.get("linked_identities", [])
                if linked_identities:
                    identity_names = []
                    for id in linked_identities:
                        id_data = tool_context.state.get(f"identity:{id}")
                        if id_data:
                            identity_names.append(id_data.get("name", "Unknown"))

                    if identity_names:
                        summary += f"Linked Identities: {', '.join(identity_names)}\n\n"

            # Add events summary
            if thread.events:
                summary += "Key events:\n"
                # Get last 5 events
                for i, event in enumerate(thread.events[-5:], 1):
                    event_identity = ""
                    if "identity_id" in event and event["identity_id"]:
                        id_data = tool_context.state.get(f"identity:{event['identity_id']}")
                        if id_data:
                            event_identity = f" [{id_data.get('name', 'Unknown')}]"

                    summary += f"{i}. {event['content']}{event_identity} ({event['emotion']})\n"
                else:
                    summary += "No events recorded yet."

                return {
                    "status": "success",
                    "thread_id": thread_id,
                    "summary": summary,
                    "identity_context": identity_name
                }
            else:
                return {
                    "status": "error",
                    "message": f"Thread is not linked to identity '{identity_name}'"
                }
        else:
            # Get all active threads
            all_threads = db_service.get_all_threads()
            active_threads = [thread for thread in all_threads if thread.status == "active"]

            # Apply identity filter if specified
            if identity_id:
                identity_threads = []

                for thread in active_threads:
                    # Check if thread has metadata with linked_identities
                    if hasattr(thread, 'metadata') and thread.metadata:
                        linked_identities = thread.metadata.get("linked_identities", [])
                        if identity_id in linked_identities:
                            identity_threads.append(thread)

                active_threads = identity_threads

            if not active_threads:
                message = "No active narrative threads"
                if identity_name:
                    message += f" for identity '{identity_name}'"

                return {"status": "success", "summary": message}

            # Generate summary for all active threads
            summary = "Active Narrative Threads"
            if identity_name:
                summary += f" for {identity_name}"
            summary += ":\n\n"

            for thread in active_threads[:3]:  # Summarize top 3
                summary += f"- {thread.title} ({thread.theme}): "
                if thread.events:
                    # Get most recent event
                    latest = thread.events[-1]

                    # Add identity context if available
                    event_identity = ""
                    if "identity_id" in latest and latest["identity_id"]:
                        id_data = tool_context.state.get(f"identity:{latest['identity_id']}")
                        if id_data:
                            event_identity = f" [{id_data.get('name', 'Unknown')}]"

                    summary += f"Most recent: {latest['content']}{event_identity}\n"
                else:
                    summary += "No events yet.\n"

            return {
                "status": "success",
                "summary": summary,
                "identity_context": identity_name
            }