#cognisphere/services/embedding.py

from sentence_transformers import SentenceTransformer




class EmbeddingService:
    """Provides embedding generation for text."""

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        """Initialize with a specific model."""
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name)
            self.available = True
        except:
            self.model = None
            self.available = False
            print(f"Warning: Embedding model {model_name} could not be initialized")

    def encode(self, text):
        """Generate embedding for text."""
        if not self.available:
            return None

        try:
            return self.model.encode(text).tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None