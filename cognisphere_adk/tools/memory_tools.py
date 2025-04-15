# cognisphere_adk/tools/memory_tools.py
from google.adk.tools.tool_context import ToolContext
from data_models.memory import Memory
from services_container import get_db_service, get_embedding_service
from typing import Optional, Dict, Any, List


def create_memory(
        tool_context: ToolContext,
        content: str,
        memory_type: str,
        emotion_type: str = "neutral",
        emotion_score: float = 0.5,
        source: str = "user",
        identity_specific: bool = False  # New parameter
) -> dict:
    """
    Creates a new memory in the system.

    Args:
        tool_context: Tool context provided by the ADK framework.
        content: The content of the memory
        memory_type: Type of memory (explicit, emotional, flashbulb, procedural, liminal)
        emotion_type: The primary emotion (joy, sadness, fear, etc.)
        emotion_score: Intensity of the emotion (0.0-1.0)
        source: Where the memory came from (user, system, reflection)
        identity_specific: Whether this memory is specific to the current identity

    Returns:
        dict: Information about the created memory
    """
    # Access services from container
    db_service = get_db_service()
    embedding_service = get_embedding_service()

    if not db_service or not embedding_service:
        return {"status": "error", "message": "Services not available"}

    # Get active identity information
    active_id = tool_context.state.get("active_identity_id")
    identity_metadata = tool_context.state.get("identity_metadata", {})

    # Create emotion data
    emotion_data = {
        "emotion_type": emotion_type,
        "score": emotion_score,
        "valence": 0.7 if emotion_type in ["joy", "excitement", "curiosity"] else 0.3,
        "arousal": 0.8 if emotion_score > 0.7 else 0.5
    }

    # Create memory object with identity information
    memory = Memory(
        content=content,
        memory_type=memory_type,
        emotion_data=emotion_data,
        source=source,
        identity_id=active_id if identity_specific else None,  # Only tag if specifically for this identity
        source_identity=active_id  # Always record which identity created it
    )

    # Generate embedding
    embedding = embedding_service.encode(content)
    if not embedding:
        return {"status": "error", "message": "Could not generate embedding"}

    # Store in database
    memory_id = db_service.add_memory(memory, embedding)

    # Save last memory to state
    tool_context.state["last_memory_id"] = memory_id

    # If this is identity-specific, also store it in the identity's linked memories
    if identity_specific and active_id:
        identity_data = tool_context.state.get(f"identity:{active_id}")
        if identity_data:
            if "linked_memories" not in identity_data:
                identity_data["linked_memories"] = []
            identity_data["linked_memories"].append(memory_id)
            tool_context.state[f"identity:{active_id}"] = identity_data

    return {
        "status": "success",
        "memory_id": memory_id,
        "message": f"Memory of type '{memory_type}' created successfully",
        "identity_context": identity_metadata.get("name", "Default") if active_id else "None"
    }


def recall_memories(
        tool_context: ToolContext,
        query: str,
        limit: int = 5,
        emotion_filter: Optional[str] = None,
        identity_filter: Optional[str] = None,  # New parameter
        include_all_identities: bool = False  # New parameter
) -> dict:
    """
    Recalls memories based on a query and optional filters.

    Args:
        tool_context: Tool context provided by the ADK framework
        query: Query text to search for
        limit: Maximum number of memories to return
        emotion_filter: Optional filter for emotional content
        identity_filter: Optional filter for specific identity
        include_all_identities: Whether to include memories from all identities

    Returns:
        dict: Query results
    """
    # Access services from container
    db_service = get_db_service()
    embedding_service = get_embedding_service()

    if not db_service or not embedding_service:
        return {"status": "error", "message": "Services not available"}

    # Get active identity
    active_id = tool_context.state.get("active_identity_id")

    # Generate embedding for query
    query_embedding = embedding_service.encode(query)
    if not query_embedding:
        return {"status": "error", "message": "Could not generate embedding for query"}

    try:
        # Build filters
        filters = {}

        # Apply identity filtering logic
        if identity_filter:
            # Explicit filter overrides defaults
            filters["identity_id"] = identity_filter
        elif not include_all_identities and active_id:
            # By default, include:
            # 1. Memories specific to current identity
            # 2. Memories created by current identity
            # 3. Memories not tied to any identity (shared/global)
            filters["$or"] = [
                {"identity_id": active_id},
                {"source_identity": active_id},
                {"identity_id": None}
            ]

        # Add emotion filter if specified
        if emotion_filter:
            if "$or" in filters:
                # We need to combine filters carefully
                for condition in filters["$or"]:
                    condition["emotion_type"] = emotion_filter
            else:
                filters["emotion_type"] = emotion_filter

        # Query the database
        results = db_service.query_memories(
            query_embedding=query_embedding,
            n_results=limit,
            where=filters if filters else None
        )

        # Process results
        memories = []

        # Verificar a estrutura dos resultados
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        distances = results.get("distances", [])

        # Ensure valid lists with matching lengths
        if not (metadatas and documents and distances):
            return {"status": "success", "count": 0, "memories": [], "identity_context": active_id}

        # Process results based on their structure
        if isinstance(metadatas[0], list):
            for i, (metadata_list, document_list, distance_list) in enumerate(zip(metadatas, documents, distances)):
                for j, (metadata, document, distance) in enumerate(zip(metadata_list, document_list, distance_list)):
                    if not metadata or not isinstance(metadata, dict):
                        continue

                    # Calculate similarity score
                    similarity = 1.0 - min(1.0, distance)

                    # Extract emotion data
                    emotion_type = "neutral"
                    if "emotion_data" in metadata:
                        if isinstance(metadata["emotion_data"], dict):
                            emotion_type = metadata["emotion_data"].get("emotion_type", "neutral")
                        elif isinstance(metadata["emotion_data"], str):
                            try:
                                import json
                                emotion_data = json.loads(metadata["emotion_data"])
                                emotion_type = emotion_data.get("emotion_type", "neutral")
                            except:
                                pass

                    # Get identity information
                    memory_identity_id = metadata.get("identity_id")
                    identity_name = "Unknown"
                    if memory_identity_id:
                        identity_data = tool_context.state.get(f"identity:{memory_identity_id}")
                        if identity_data:
                            identity_name = identity_data.get("name", "Unknown")

                    # Add to results
                    memories.append({
                        "id": metadata.get("id", f"unknown-{i}-{j}"),
                        "content": document,
                        "type": metadata.get("type", "unknown"),
                        "emotion": emotion_type,
                        "relevance": similarity,
                        "identity_id": memory_identity_id,
                        "identity_name": identity_name
                    })
        else:
            # Handle flat list structure
            for i, (metadata, document, distance) in enumerate(zip(metadatas, documents, distances)):
                if not metadata or not isinstance(metadata, dict):
                    continue

                # Similar processing to above
                similarity = 1.0 - min(1.0, distance)

                # Extract emotion data (simplified)
                emotion_type = metadata.get("emotion_type", "neutral")

                # Get identity information
                memory_identity_id = metadata.get("identity_id")
                identity_name = "Unknown"
                if memory_identity_id:
                    identity_data = tool_context.state.get(f"identity:{memory_identity_id}")
                    if identity_data:
                        identity_name = identity_data.get("name", "Unknown")

                memories.append({
                    "id": metadata.get("id", f"unknown-{i}"),
                    "content": document,
                    "type": metadata.get("type", "unknown"),
                    "emotion": emotion_type,
                    "relevance": similarity,
                    "identity_id": memory_identity_id,
                    "identity_name": identity_name
                })

        # Sort by relevance
        memories.sort(key=lambda x: x["relevance"], reverse=True)

        # Save recalled memories to state
        tool_context.state["last_recalled_memories"] = memories

        # Get current identity name
        current_identity_name = "Default"
        if active_id:
            identity_data = tool_context.state.get(f"identity:{active_id}")
            if identity_data:
                current_identity_name = identity_data.get("name", "Default")

        return {
            "status": "success",
            "count": len(memories),
            "memories": memories[:limit],  # Limit results
            "identity_context": current_identity_name
        }
    except Exception as e:
        print(f"Error recalling memories: {e}")
        return {"status": "error", "message": f"Error recalling memories: {e}"}