# cognisphere_adk/data_models/memory.py
import datetime
import uuid
"""cognisphere_adk/data_models/memory.py """

class Memory:
    """Represents a memory entry in the Cognisphere system."""

    def __init__(
            self,
            content,
            memory_type,
            emotion_data=None,
            source="user",
            identity_id=None,  # New field
            source_identity=None  # New field
    ):
        self.id = str(uuid.uuid4())
        self.content = content
        self.type = memory_type  # explicit, emotional, flashbulb, etc.
        self.creation_time = datetime.datetime.utcnow().isoformat()
        self.emotion_data = emotion_data or {
            'emotion_type': 'neutral',
            'score': 0.5,
            'valence': 0.5,
            'arousal': 0.5
        }
        self.source = source
        # Identity fields
        self.identity_id = identity_id  # Identity this memory belongs to
        self.source_identity = source_identity  # Identity that created this memory

    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type,
            "creation_time": self.creation_time,
            "emotion_data": self.emotion_data,
            "source": self.source,
            "identity_id": self.identity_id,
            "source_identity": self.source_identity
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary."""
        memory = cls(
            content=data["content"],
            memory_type=data["type"],
            emotion_data=data.get("emotion_data"),
            source=data.get("source", "user"),
            identity_id=data.get("identity_id"),
            source_identity=data.get("source_identity")
        )
        memory.id = data["id"]
        memory.creation_time = data["creation_time"]
        return memory