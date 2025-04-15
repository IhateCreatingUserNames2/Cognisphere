# cognisphere_adk/data_models/identity.py
"""
Data model for Identity representation in Cognisphere.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional


class Identity:
    """Represents an identity context within the Cognisphere system."""

    def __init__(
            self,
            name: str,
            description: str = "",
            identity_type: str = "user_created",
            characteristics: Optional[Dict[str, Any]] = None,
            tone: str = "neutral",
            personality: str = "balanced",
            instruction: str = ""
    ):
        """
        Initialize a new Identity.

        Args:
            name: Name of the identity
            description: Brief description of the identity
            identity_type: Type of identity (system, user_created, etc.)
            characteristics: Dictionary of defining characteristics
            tone: Tone of voice (cheerful, serious, etc.)
            personality: Personality traits
            instruction: Specific instructions for how to embody this identity
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.type = identity_type
        self.creation_time = datetime.utcnow().isoformat()
        self.last_accessed = self.creation_time
        self.characteristics = characteristics or {}
        self.tone = tone
        self.personality = personality
        self.instruction = instruction
        self.linked_narratives = {}  # narrative_id -> relationship details
        self.linked_memories = []  # list of memory IDs
        self.metadata = {
            "access_count": 0,
            "creation_source": "user",
            "last_modified": self.creation_time
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert identity to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "creation_time": self.creation_time,
            "last_accessed": self.last_accessed,
            "characteristics": self.characteristics,
            "tone": self.tone,
            "personality": self.personality,
            "instruction": self.instruction,
            "linked_narratives": self.linked_narratives,
            "linked_memories": self.linked_memories,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create an Identity object from dictionary."""
        identity = cls(
            name=data["name"],
            description=data.get("description", ""),
            identity_type=data.get("type", "user_created"),
            characteristics=data.get("characteristics", {}),
            tone=data.get("tone", "neutral"),
            personality=data.get("personality", "balanced"),
            instruction=data.get("instruction", "")
        )
        identity.id = data["id"]
        identity.creation_time = data["creation_time"]
        identity.last_accessed = data.get("last_accessed", identity.creation_time)
        identity.linked_narratives = data.get("linked_narratives", {})
        identity.linked_memories = data.get("linked_memories", [])
        identity.metadata = data.get("metadata", {})
        return identity

    def record_access(self):
        """Record that this identity was accessed."""
        self.last_accessed = datetime.utcnow().isoformat()
        self.metadata["access_count"] = self.metadata.get("access_count", 0) + 1

    def add_linked_narrative(self, narrative_id: str, relationship: str = "primary"):
        """Add a link to a narrative thread."""
        self.linked_narratives[narrative_id] = {
            "relationship": relationship,
            "linked_at": datetime.utcnow().isoformat()
        }

    def add_linked_memory(self, memory_id: str):
        """Add a link to a memory."""
        if memory_id not in self.linked_memories:
            self.linked_memories.append(memory_id)