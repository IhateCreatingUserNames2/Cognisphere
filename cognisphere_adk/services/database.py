#cognisphere/services/database.py
import chromadb
import json
import os

from data_models.narrative import NarrativeThread


class DatabaseService:
    def __init__(self, db_path="./cognisphere_data"): # Adjusted default path
        # No lock needed, initialize directly
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        
        # Ensure the ChromaDB path exists before initializing
        chroma_db_path = os.path.join(db_path) # Chroma persists directly in the given path
        os.makedirs(chroma_db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=chroma_db_path)
        self.collections = {}
        self.ensure_collection("memories")
        self.ensure_collection("narrative_threads")
        self.ensure_collection("entities")
        self.initialized = True # Mark as initialized

    def ensure_collection(self, name):
        """Ensure a collection exists."""
        try:
            self.collections[name] = self.client.get_collection(name=name)
        except:
            self.collections[name] = self.client.create_collection(name=name)
        return self.collections[name]

    def add_memory(self, memory, embedding):
        """Add a memory to the database."""
        collection = self.collections["memories"]

        # Obter o dicionário de memória
        memory_dict = memory.to_dict()

        # Serializar dados emocionais para JSON se for um dicionário
        if "emotion_data" in memory_dict and isinstance(memory_dict["emotion_data"], dict):
            import json
            memory_dict["emotion_data"] = json.dumps(memory_dict["emotion_data"])

        # Sanitize metadata - replace None values with appropriate defaults
        sanitized_metadata = {}
        for key, value in memory_dict.items():
            if value is None:
                # Replace None with empty string
                sanitized_metadata[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                # Keep primitive types as they are
                sanitized_metadata[key] = value
            else:
                # Convert any other complex types to string representation
                try:
                    sanitized_metadata[key] = str(value)
                except:
                    sanitized_metadata[key] = ""

        collection.add(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[sanitized_metadata]  # Use the sanitized version
        )

        return memory.id

    def query_memories(self, query_embedding, n_results=5, where=None):
        """Query memories by embedding similarity."""
        collection = self.collections["memories"]

        try:
            # Sanitize the 'where' filter if it exists
            if where:
                # Remove conditions with None values to prevent query errors
                sanitized_where = {}
                for key, value in where.items():
                    if value is not None:
                        if key == "$or" and isinstance(value, list):
                            # Handle $or operator specially
                            sanitized_or = []
                            for condition in value:
                                if isinstance(condition, dict):
                                    # Remove None values from each condition
                                    sanitized_condition = {k: v for k, v in condition.items() if v is not None}
                                    if sanitized_condition:  # Only add if not empty
                                        sanitized_or.append(sanitized_condition)
                            if sanitized_or:  # Only add if not empty
                                sanitized_where["$or"] = sanitized_or
                        else:
                            sanitized_where[key] = value

                # Use sanitized where filter
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=sanitized_where if sanitized_where else None,
                    include=["metadatas", "documents", "distances"]
                )
            else:
                # No where filter
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["metadatas", "documents", "distances"]
                )

            # Initialize empty results structure if the query returned nothing
            if not results:
                return {"metadatas": [[]], "documents": [[]], "distances": [[]]}

            # Ensure the results structure is consistent
            if "metadatas" not in results:
                results["metadatas"] = [[]]
            if "documents" not in results:
                results["documents"] = [[]]
            if "distances" not in results:
                results["distances"] = [[]]

            # Process metadatas as before but with better error handling
            import json
            metadatas = results.get("metadatas", [])
            if metadatas and isinstance(metadatas, list):
                # Handle direct list of metadata
                if metadatas and all(isinstance(m, dict) for m in metadatas):
                    for metadata in metadatas:
                        if metadata and "emotion_data" in metadata and isinstance(metadata["emotion_data"], str):
                            try:
                                metadata["emotion_data"] = json.loads(metadata["emotion_data"])
                            except json.JSONDecodeError:
                                # Provide a default if parsing fails
                                metadata["emotion_data"] = {"emotion_type": "neutral", "score": 0.5}

                # Handle nested list structure
                elif metadatas and isinstance(metadatas[0], list):
                    for metadata_list in metadatas:
                        for metadata in metadata_list:
                            if isinstance(metadata, dict) and "emotion_data" in metadata and isinstance(
                                    metadata["emotion_data"], str):
                                try:
                                    metadata["emotion_data"] = json.loads(metadata["emotion_data"])
                                except json.JSONDecodeError:
                                    # Provide a default if parsing fails
                                    metadata["emotion_data"] = {"emotion_type": "neutral", "score": 0.5}

            return results

        except Exception as e:
            print(f"Error in query_memories: {e}")
            # Return an empty result structure on error
            return {"metadatas": [[]], "documents": [[]], "distances": [[]]}

    def save_thread(self, thread):
        """Save a narrative thread."""
        # Save thread data to a JSON file
        threads_dir = os.path.join(self.db_path, "threads")
        os.makedirs(threads_dir, exist_ok=True)

        file_path = os.path.join(threads_dir, f"{thread.id}.json")
        with open(file_path, "w") as f:
            json.dump(thread.to_dict(), f, indent=2)

        return thread.id

    def get_thread(self, thread_id):
        """Get a narrative thread by ID."""
        file_path = os.path.join(self.db_path, "threads", f"{thread_id}.json")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return NarrativeThread.from_dict(data)
        except:
            return None

    def get_all_threads(self):
        """Get all narrative threads."""
        threads_dir = os.path.join(self.db_path, "threads")
        os.makedirs(threads_dir, exist_ok=True)

        threads = []
        for filename in os.listdir(threads_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(threads_dir, filename)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        threads.append(NarrativeThread.from_dict(data))
                except:
                    continue

        return threads
