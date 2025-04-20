# cognisphere_adk/tools/memory_tools.py
import asyncio
from google.adk.tools.tool_context import ToolContext
from data_models.memory import Memory
from services_container import get_db_service, get_embedding_service
from typing import Optional, Dict, Any, List


# helper to run blocking calls in the default executor
async def _to_thread(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)

async def create_memory(
        tool_context: ToolContext,
        content: str,
        memory_type: str,
        emotion_type: str = "neutral",
        emotion_score: float = 0.5,
        source: str = "user",
        identity_specific: bool = False
) -> dict:
    db_service = get_db_service()
    embedding_service = get_embedding_service()

    if not db_service or not embedding_service:
        return {"status": "error", "message": "Services not available"}

    active_id = tool_context.state.get("active_identity_id")
    identity_metadata = tool_context.state.get("identity_metadata", {})

    emotion_data = {
        "emotion_type": emotion_type,
        "score": emotion_score,
        "valence": 0.7 if emotion_type in ["joy", "excitement", "curiosity"] else 0.3,
        "arousal": 0.8 if emotion_score > 0.7 else 0.5
    }

    memory = Memory(
        content=content,
        memory_type=memory_type,
        emotion_data=emotion_data,
        source=source,
        identity_id=active_id if identity_specific else None,
        source_identity=active_id,
    )

    # embedding_service.encode is blocking → push to thread pool
    embedding = await _to_thread(embedding_service.encode, content)
    if not embedding:
        return {"status": "error", "message": "Could not generate embedding"}

    memory_id = await _to_thread(db_service.add_memory, memory, embedding)

    tool_context.state["last_memory_id"] = memory_id
    if identity_specific and active_id:
        identity_data = tool_context.state.get(f"identity:{active_id}", {})
        identity_data.setdefault("linked_memories", []).append(memory_id)
        tool_context.state[f"identity:{active_id}"] = identity_data

    return {
        "status": "success",
        "memory_id": memory_id,
        "message": f"Memory of type '{memory_type}' created successfully",
        "identity_context": identity_metadata.get("name", "Default") if active_id else "None"
    }

async def recall_memories(
        tool_context: ToolContext,
        query: str,
        limit: int = 5,
        emotion_filter: Optional[str] = None,
        identity_filter: Optional[str] = None,
        include_all_identities: bool = False,
) -> dict:
    db_service = get_db_service()
    embedding_service = get_embedding_service()
    if not db_service or not embedding_service:
        return {"status": "error", "message": "Services not available"}

    active_id = tool_context.state.get("active_identity_id")
    query_embedding = await _to_thread(embedding_service.encode, query)
    if not query_embedding:
        return {"status": "error", "message": "Could not generate embedding"}

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
        results = await _to_thread(
            db_service.query_memories,
            query_embedding,
            limit,
            filters if (filters := {}) else None,
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