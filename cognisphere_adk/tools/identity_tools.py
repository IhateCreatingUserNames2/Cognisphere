# cognisphere_adk/tools/identity_tools.py
"""
Tools for identity management in Cognisphere.
"""

from google.adk.tools.tool_context import ToolContext
from data_models.identity import Identity
from data_models.memory import Memory
from data_models.narrative import NarrativeThread
from services_container import get_db_service, get_embedding_service
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from typing import Dict, Any, List, Optional


def create_identity(
        name: str,
        description: str = "",
        characteristics: Optional[Dict[str, Any]] = None,  # Change here
        tone: str = "neutral",
        personality: str = "balanced",
        instruction: str = "",
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Creates a new identity profile.

    Args:
        name: Name of the identity
        description: Brief description of the identity
        characteristics: Dictionary of defining characteristics
        tone: Tone of voice (cheerful, serious, etc.)
        personality: Personality traits
        instruction: Specific instructions for how to embody this identity
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about the created identity
    """
    # Inside the function, ensure characteristics is never None
    if characteristics is None:
        characteristics = {}

    # Create new identity object
    identity = Identity(
        name=name,
        description=description,
        characteristics=characteristics,  # Already guaranteed to be a dict
        tone=tone,
        personality=personality,
        instruction=instruction
    )

    # Store in session state
    identity_dict = identity.to_dict()
    identity_id = identity.id

    # Update identities catalog
    identities_catalog = tool_context.state.get("identities", {})
    identities_catalog[identity_id] = {
        "name": name,
        "type": identity.type,
        "created": identity.creation_time
    }
    tool_context.state["identities"] = identities_catalog

    # Store complete identity data
    tool_context.state[f"identity:{identity_id}"] = identity_dict

    # Create a default "system" identity if it doesn't exist
    if "default" not in identities_catalog:
        default_identity = Identity(
            name="Cupcake",
            description="The default Cognisphere identity",
            identity_type="system",
            tone="friendly",
            personality="helpful",
            instruction="You are Cupcake, the Cognisphere system's default identity."
        )
        default_id = "default"
        tool_context.state[f"identity:{default_id}"] = default_identity.to_dict()
        identities_catalog[default_id] = {
            "name": default_identity.name,
            "type": default_identity.type,
            "created": default_identity.creation_time
        }
        tool_context.state["identities"] = identities_catalog

    return {
        "status": "success",
        "identity_id": identity_id,
        "name": name,
        "message": f"Identity '{name}' created successfully"
    }


def switch_to_identity(
        identity_id: str,
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Switches the current context to a specific identity.

    Args:
        identity_id: ID of the identity to switch to
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about the identity switch
    """
    # Get current identity
    current_id = tool_context.state.get("active_identity_id")

    # Check if the requested identity exists
    identity_data = tool_context.state.get(f"identity:{identity_id}")
    if not identity_data:
        # Check if we're requesting the "default" identity
        if identity_id == "default":
            # Create default identity if it doesn't exist
            default_identity = Identity(
                name="Cupcake",
                description="The default Cognisphere identity",
                identity_type="system",
                tone="friendly",
                personality="helpful",
                instruction="You are Cupcake, the Cognisphere system's default identity."
            )
            identity_data = default_identity.to_dict()
            tool_context.state[f"identity:{identity_id}"] = identity_data

            # Update identities catalog
            identities_catalog = tool_context.state.get("identities", {})
            identities_catalog[identity_id] = {
                "name": default_identity.name,
                "type": default_identity.type,
                "created": default_identity.creation_time
            }
            tool_context.state["identities"] = identities_catalog
        else:
            return {
                "status": "error",
                "message": f"Identity with ID '{identity_id}' not found"
            }

    # Record access to the identity
    identity_obj = Identity.from_dict(identity_data)
    identity_obj.record_access()
    tool_context.state[f"identity:{identity_id}"] = identity_obj.to_dict()

    # Save previous identity state if needed
    if current_id:
        tool_context.state[f"identity:{current_id}:last_active"] = datetime.utcnow().isoformat()

    # Update active identity
    tool_context.state["active_identity_id"] = identity_id
    tool_context.state["identity_metadata"] = {
        "name": identity_obj.name,
        "type": identity_obj.type,
        "last_accessed": identity_obj.last_accessed
    }

    # Signal that identity context has changed
    tool_context.state["identity_context_changed"] = True

    return {
        "status": "success",
        "identity_id": identity_id,
        "name": identity_obj.name,
        "message": f"Switched to identity: {identity_obj.name}"
    }


def list_identities(
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Lists all available identities.

    Args:
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about available identities
    """
    # Get identities catalog
    identities_catalog = tool_context.state.get("identities", {})

    # Enhance with more details
    detailed_identities = []
    for identity_id, basic_info in identities_catalog.items():
        # Get full identity data
        identity_data = tool_context.state.get(f"identity:{identity_id}")
        if identity_data:
            # Extract relevant information
            detailed_identities.append({
                "id": identity_id,
                "name": identity_data.get("name", basic_info.get("name", "Unknown")),
                "description": identity_data.get("description", ""),
                "type": identity_data.get("type", basic_info.get("type", "unknown")),
                "created": identity_data.get("creation_time", basic_info.get("created", "")),
                "last_accessed": identity_data.get("last_accessed", ""),
                "is_active": identity_id == tool_context.state.get("active_identity_id")
            })

    # Sort by last accessed (most recent first)
    detailed_identities.sort(
        key=lambda x: x.get("last_accessed", ""),
        reverse=True
    )

    return {
        "status": "success",
        "identities": detailed_identities,
        "count": len(detailed_identities),
        "active_identity_id": tool_context.state.get("active_identity_id")
    }


def update_identity(
        identity_id: str,
        updates: Dict[str, Any],
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Updates an existing identity with new attributes.

    Args:
        identity_id: ID of the identity to update
        updates: Dictionary of attributes to update
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about the update
    """
    # Get the identity
    identity_data = tool_context.state.get(f"identity:{identity_id}")
    if not identity_data:
        return {
            "status": "error",
            "message": f"Identity with ID '{identity_id}' not found"
        }

    # Convert to object
    identity = Identity.from_dict(identity_data)

    # Apply updates
    allowed_fields = {
        "name", "description", "characteristics",
        "tone", "personality", "instruction"
    }

    updated_fields = []
    for field, value in updates.items():
        if field in allowed_fields:
            setattr(identity, field, value)
            updated_fields.append(field)

    # Update metadata
    identity.metadata["last_modified"] = datetime.utcnow().isoformat()

    # Save updated identity
    updated_data = identity.to_dict()
    tool_context.state[f"identity:{identity_id}"] = updated_data

    # Update catalog if name changed
    if "name" in updated_fields:
        identities_catalog = tool_context.state.get("identities", {})
        if identity_id in identities_catalog:
            identities_catalog[identity_id]["name"] = identity.name
            tool_context.state["identities"] = identities_catalog

    # Update active identity metadata if this is the active identity
    if identity_id == tool_context.state.get("active_identity_id"):
        tool_context.state["identity_metadata"] = {
            "name": identity.name,
            "type": identity.type,
            "last_accessed": identity.last_accessed
        }
        # Signal context change
        tool_context.state["identity_context_changed"] = True

    return {
        "status": "success",
        "identity_id": identity_id,
        "updated_fields": updated_fields,
        "message": f"Updated identity '{identity.name}' successfully"
    }


def link_identity_to_narrative(
        identity_id: str,
        narrative_id: str,
        relationship_type: str = "primary",
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Links an identity to a narrative thread with a specific relationship.

    Args:
        identity_id: ID of the identity
        narrative_id: ID of the narrative thread
        relationship_type: Type of relationship (primary, secondary, etc.)
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about the link
    """
    # Get the identity
    identity_data = tool_context.state.get(f"identity:{identity_id}")
    if not identity_data:
        return {
            "status": "error",
            "message": f"Identity with ID '{identity_id}' not found"
        }

    # Get the narrative
    db_service = get_db_service()
    narrative = db_service.get_thread(narrative_id)
    if not narrative:
        return {
            "status": "error",
            "message": f"Narrative thread with ID '{narrative_id}' not found"
        }

    # Update identity with link
    identity = Identity.from_dict(identity_data)
    identity.add_linked_narrative(narrative_id, relationship_type)
    tool_context.state[f"identity:{identity_id}"] = identity.to_dict()

    # Update narrative with link to identity
    if not hasattr(narrative, 'metadata') or narrative.metadata is None:
        narrative.metadata = {}

    if "linked_identities" not in narrative.metadata:
        narrative.metadata["linked_identities"] = []

    if identity_id not in narrative.metadata["linked_identities"]:
        narrative.metadata["linked_identities"].append(identity_id)

    # Save updated narrative
    db_service.save_thread(narrative)

    return {
        "status": "success",
        "identity_id": identity_id,
        "narrative_id": narrative_id,
        "relationship": relationship_type,
        "message": f"Linked identity '{identity.name}' to narrative '{narrative.title}'"
    }


def collect_identity_memories(
        identity_id: str,
        limit: int = 10,
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Collects memories associated with an identity.

    Args:
        identity_id: ID of the identity
        limit: Maximum number of memories to return
        tool_context: Tool context for accessing session state

    Returns:
        Dict with memories associated with the identity
    """
    # Get the identity
    identity_data = tool_context.state.get(f"identity:{identity_id}")
    if not identity_data:
        return {
            "status": "error",
            "message": f"Identity with ID '{identity_id}' not found"
        }

    identity = Identity.from_dict(identity_data)

    # Access services
    db_service = get_db_service()
    embedding_service = get_embedding_service()

    # Generate query embedding based on identity
    query_text = f"{identity.name} {identity.description}"
    query_embedding = embedding_service.encode(query_text)

    # Filter options for the database query
    filters = {
        "$or": [
            {"identity_id": identity_id},  # Memories explicitly tagged with this identity
            {"source_identity": identity_id}  # Memories created by this identity
        ]
    }

    # Query the database
    try:
        results = db_service.query_memories(
            query_embedding=query_embedding,
            n_results=limit,
            where=filters
        )

        # Process results
        memories = []

        # Extract memory documents and metadata
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, (document, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            if document and metadata:
                similarity = 1.0 - min(1.0, distance)
                memory_type = metadata.get("type", "unknown")
                emotion_data = metadata.get("emotion_data", {})

                if isinstance(emotion_data, str):
                    try:
                        emotion_data = json.loads(emotion_data)
                    except:
                        emotion_data = {"emotion_type": "neutral", "score": 0.5}

                memories.append({
                    "id": metadata.get("id", f"unknown-{i}"),
                    "content": document,
                    "type": memory_type,
                    "emotion": emotion_data.get("emotion_type", "neutral"),
                    "source": metadata.get("source", "unknown"),
                    "creation_time": metadata.get("timestamp", ""),
                    "relevance": similarity
                })

        # Sort by relevance
        memories.sort(key=lambda x: x["relevance"], reverse=True)

        return {
            "status": "success",
            "memories": memories,
            "count": len(memories),
            "identity_name": identity.name
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error querying memories: {str(e)}"
        }


def generate_identity_narrative(
        identity_id: str,
        title: Optional[str] = None,  # Change here
        theme: Optional[str] = None,  # Change here
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Generates a narrative thread based on an identity's memories.

    Args:
        identity_id: ID of the identity
        title: Optional title for the narrative
        theme: Optional theme for the narrative
        tool_context: Tool context for accessing session state

    Returns:
        Dict with information about the generated narrative
    """
    # Get the identity
    identity_data = tool_context.state.get(f"identity:{identity_id}")
    if not identity_data:
        return {
            "status": "error",
            "message": f"Identity with ID '{identity_id}' not found"
        }

    identity = Identity.from_dict(identity_data)

    # Collect memories for this identity
    memory_result = collect_identity_memories(identity_id, limit=20, tool_context=tool_context)

    if memory_result["status"] != "success":
        return memory_result

    memories = memory_result.get("memories", [])
    if not memories:
        return {
            "status": "error",
            "message": f"No memories found for identity '{identity.name}'"
        }

    # Access database service
    db_service = get_db_service()

    # Create a narrative thread
    thread_title = title or f"{identity.name}'s {theme or 'Story'}"
    thread_description = f"Narrative derived from {identity.name}'s experiences and memories"

    thread = NarrativeThread(
        title=thread_title,
        theme=theme or "identity",
        description=thread_description
    )

    # Initialize metadata
    thread.metadata = {
        "source": "identity_generation",
        "identity_id": identity_id,
        "identity_name": identity.name,
        "linked_identities": [identity_id]
    }

    # Add memories as events
    for memory in memories:
        impact = memory.get("relevance", 0.5)
        content = memory.get("content", "")
        emotion = memory.get("emotion", "neutral")

        thread.add_event(
            content=content,
            emotion=emotion,
            impact=impact
        )

    # Save the thread
    thread_id = db_service.save_thread(thread)

    # Link the identity to this narrative
    link_result = link_identity_to_narrative(
        identity_id=identity_id,
        narrative_id=thread_id,
        relationship_type="derived",
        tool_context=tool_context
    )

    return {
        "status": "success",
        "thread_id": thread_id,
        "title": thread_title,
        "event_count": len(thread.events),
        "message": f"Generated narrative from {identity.name}'s memories"
    }