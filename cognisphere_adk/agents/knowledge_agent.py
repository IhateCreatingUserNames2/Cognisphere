# cognisphere_adk/agents/knowledge_agent.py
from google.adk.agents import Agent
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any, List, Optional
import uuid
import json
import asyncio


class KnowledgeStorageTool(BaseTool):
    """
    A comprehensive tool for storing, retrieving, and managing knowledge
    """

    def __init__(
            self,
            name: str = "knowledge_storage",
            description: str = "Advanced knowledge storage and retrieval system"
    ):
        super().__init__(
            name=name,
            description=description
        )
        # In-memory knowledge base (replace with persistent storage in production)
        self._knowledge_base: Dict[str, Dict[str, Any]] = {}
        self._embeddings: Dict[str, List[float]] = {}

    def _generate_id(self) -> str:
        """Generate a unique identifier for knowledge entries"""
        return str(uuid.uuid4())

    def _validate_knowledge_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Validate the structure of a knowledge entry

        Required fields:
        - type: str (e.g., 'fact', 'concept', 'theory')
        - content: str
        - tags: List[str]
        - metadata: Dict (optional)
        """
        required_fields = ['type', 'content', 'tags']

        for field in required_fields:
            if field not in entry:
                return False

        if not isinstance(entry['type'], str):
            return False

        if not isinstance(entry['content'], str):
            return False

        if not isinstance(entry['tags'], list):
            return False

        return True

    async def run_async(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """
        Primary method for knowledge management

        Supported operations:
        - store: Store new knowledge
        - retrieve: Retrieve knowledge by ID or query
        - update: Update existing knowledge
        - delete: Remove knowledge entry
        - search: Search knowledge base
        """
        operation = args.get('operation', 'retrieve')

        try:
            if operation == 'store':
                return await self._store_knowledge(args, tool_context)
            elif operation == 'retrieve':
                return await self._retrieve_knowledge(args, tool_context)
            elif operation == 'update':
                return await self._update_knowledge(args, tool_context)
            elif operation == 'delete':
                return await self._delete_knowledge(args, tool_context)
            elif operation == 'search':
                return await self._search_knowledge(args, tool_context)
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported operation: {operation}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Knowledge operation error: {str(e)}"
            }

    async def _store_knowledge(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """Store new knowledge entry"""
        entry = args.get('entry', {})

        # Validate entry
        if not self._validate_knowledge_entry(entry):
            return {
                "status": "error",
                "message": "Invalid knowledge entry format"
            }

        # Generate unique ID
        entry_id = self._generate_id()
        entry['id'] = entry_id

        # Optional: Generate embedding if embedding service available
        embedding_service = getattr(tool_context, 'embedding_service', None)
        if embedding_service:
            try:
                embedding = embedding_service.encode(entry['content'])
                self._embeddings[entry_id] = embedding
            except Exception as e:
                print(f"Embedding generation error: {e}")

        # Store entry
        self._knowledge_base[entry_id] = entry

        return {
            "status": "success",
            "id": entry_id,
            "message": "Knowledge entry stored successfully"
        }

    async def _retrieve_knowledge(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """Retrieve knowledge by ID"""
        entry_id = args.get('id')

        if not entry_id:
            return {
                "status": "error",
                "message": "Entry ID is required"
            }

        entry = self._knowledge_base.get(entry_id)

        if not entry:
            return {
                "status": "error",
                "message": f"No knowledge entry found with ID {entry_id}"
            }

        return {
            "status": "success",
            "entry": entry
        }

    async def _update_knowledge(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """Update an existing knowledge entry"""
        entry_id = args.get('id')
        updates = args.get('updates', {})

        if not entry_id or not updates:
            return {
                "status": "error",
                "message": "Entry ID and updates are required"
            }

        if entry_id not in self._knowledge_base:
            return {
                "status": "error",
                "message": f"No knowledge entry found with ID {entry_id}"
            }

        # Update entry
        current_entry = self._knowledge_base[entry_id]
        current_entry.update(updates)

        # Revalidate
        if not self._validate_knowledge_entry(current_entry):
            return {
                "status": "error",
                "message": "Updated entry fails validation"
            }

        return {
            "status": "success",
            "id": entry_id,
            "message": "Knowledge entry updated successfully"
        }

    async def _delete_knowledge(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """Delete a knowledge entry"""
        entry_id = args.get('id')

        if not entry_id:
            return {
                "status": "error",
                "message": "Entry ID is required"
            }

        if entry_id not in self._knowledge_base:
            return {
                "status": "error",
                "message": f"No knowledge entry found with ID {entry_id}"
            }

        # Remove entry
        del self._knowledge_base[entry_id]

        # Remove embedding if exists
        if entry_id in self._embeddings:
            del self._embeddings[entry_id]

        return {
            "status": "success",
            "id": entry_id,
            "message": "Knowledge entry deleted successfully"
        }

    async def _search_knowledge(self, args: Dict[str, Any], tool_context: ToolContext) -> Dict[str, Any]:
        """
        Search knowledge base
        Supports:
        - Text search
        - Tag search
        - Semantic search (if embedding service available)
        """
        query = args.get('query', '')
        tags = args.get('tags', [])
        search_type = args.get('search_type', 'text')
        limit = args.get('limit', 10)

        results = []

        if search_type == 'text':
            # Simple text search
            results = [
                entry for entry in self._knowledge_base.values()
                if query.lower() in entry['content'].lower()
            ]

        elif search_type == 'tags':
            # Tag search
            results = [
                entry for entry in self._knowledge_base.values()
                if any(tag.lower() in [t.lower() for t in entry['tags']] for tag in tags)
            ]

        elif search_type == 'semantic':
            # Semantic search using embeddings
            embedding_service = getattr(tool_context, 'embedding_service', None)
            if not embedding_service:
                return {
                    "status": "error",
                    "message": "Embedding service not available for semantic search"
                }

            # Generate query embedding
            try:
                query_embedding = embedding_service.encode(query)

                # Compute similarity (cosine similarity)
                def cosine_similarity(v1: List[float], v2: List[float]) -> float:
                    """Compute cosine similarity between two vectors"""
                    import numpy as np
                    v1_norm = np.array(v1)
                    v2_norm = np.array(v2)
                    return np.dot(v1_norm, v2_norm) / (np.linalg.norm(v1_norm) * np.linalg.norm(v2_norm))

                # Rank entries by similarity
                similarity_scores = []
                for entry_id, entry_embedding in self._embeddings.items():
                    similarity = cosine_similarity(query_embedding, entry_embedding)
                    similarity_scores.append((similarity, self._knowledge_base[entry_id]))

                # Sort by similarity and get top results
                results = [
                    entry for _, entry in
                    sorted(similarity_scores, key=lambda x: x[0], reverse=True)[:limit]
                ]

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Semantic search error: {str(e)}"
                }

        return {
            "status": "success",
            "results": results,
            "count": len(results)
        }


def create_knowledge_agent(model="gpt-4o-mini"):
    """
    Creates a Knowledge Agent for comprehensive knowledge management

    Args:
        model: The LLM model to use

    Returns:
        An Agent configured for knowledge operations
    """
    knowledge_storage_tool = KnowledgeStorageTool()

    knowledge_agent = Agent(
        name="knowledge_agent",
        model=model,
        description="Agent specialized in advanced knowledge management and retrieval",
        instruction="""You are the Knowledge Agent, responsible for:
        1. Storing structured knowledge entries
        2. Retrieving and searching knowledge efficiently
        3. Managing a comprehensive knowledge base

        Your core capabilities include:
        - Storing knowledge with rich metadata
        - Searching knowledge through multiple methods:
          * Text-based search
          * Tag-based filtering
          * Semantic similarity search
        - Updating and deleting knowledge entries

        Knowledge Entry Requirements:
        - Must have a type (e.g., 'fact', 'concept', 'theory')
        - Must have content
        - Must have associated tags
        - Can include optional metadata

        Principles:
        - Maintain knowledge integrity
        - Ensure efficient storage and retrieval
        - Support multiple search paradigms
        - Protect sensitive or private information

        When managing knowledge:
        1. Validate all knowledge entries
        2. Use appropriate search techniques
        3. Provide context about stored or retrieved knowledge
        4. Respect data privacy and usage rights

        Your goal is to create a dynamic, searchable knowledge repository
        that can support complex information management needs.""",
        tools=[knowledge_storage_tool]
    )

    return knowledge_agent