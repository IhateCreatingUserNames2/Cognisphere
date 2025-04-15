# cognisphere_adk/data_models/identity_store.py

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from data_models.identity import Identity
import concurrent.futures  # para timeout na leitura de arquivos

class IdentityStore:
    def __init__(self, base_path: str = None):
        """
        Initialize the identity store with a storage location.

        Args:
            base_path: Base directory for identity storage, defaults to '{config_path}/identities'
        """
        self.base_path = base_path or os.path.join(os.environ.get(
            "COGNISPHERE_DB_PATH", "./cognisphere_data"), "identities")

        # Ensure storage directory exists
        os.makedirs(self.base_path, exist_ok=True)

        # Ensure catalog directory exists
        os.makedirs(os.path.dirname(self.get_catalog_path()), exist_ok=True)

        # Cache for identities
        self.identity_cache = {}
        self.catalog_cache = None

        # Create default identity if not exists
        self._ensure_default_identity()

    def _ensure_default_identity(self):
        """Ensures a default 'Cupcake' identity exists"""
        print("[VERBOSE] Ensuring default identity exists")
        try:
            # Get the catalog safely
            catalog = self.get_identity_catalog()

            # Check if default identity already exists
            if "default" not in catalog:
                print("[VERBOSE] Creating default identity")
                # Create default identity
                default_identity = Identity(
                    name="Cupcake",
                    description="The default Cognisphere identity",
                    identity_type="system",
                    tone="friendly",
                    personality="helpful",
                    instruction="You are Cupcake, the default identity for Cognisphere."
                )

                # Override the ID to ensure it's 'default'
                default_identity.id = "default"

                # Save the default identity
                self.save_identity(default_identity)

                print("Created default 'Cupcake' identity")
        except Exception as e:
            print(f"[ERROR] Error ensuring default identity: {e}")

    def get_identity_path(self, identity_id: str) -> str:
        """Gets the file path for an identity."""
        return os.path.join(self.base_path, f"{identity_id}.json")

    def get_catalog_path(self) -> str:
        """Gets the path to the identity catalog file."""
        return os.path.join(self.base_path, "catalog.json")

    def get_identity_catalog(self, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves the catalog of all identities.

        Args:
            refresh: Whether to refresh the cache

        Returns:
            Dictionary mapping identity IDs to basic information
        """
        print("[VERBOSE] Entering get_identity_catalog method")
        catalog_path = self.get_catalog_path()
        print(f"[VERBOSE] Catalog path: {catalog_path}")

        # Return cached catalog if available and not forced to refresh
        if self.catalog_cache is not None and not refresh:
            return self.catalog_cache

        # If catalog file doesn't exist, initialize an empty catalog
        if not os.path.exists(catalog_path):
            print("[VERBOSE] Catalog file does not exist. Creating empty catalog.")
            self.catalog_cache = {}
            self._save_catalog({})
            return {}

        # Read and parse catalog
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)
                self.catalog_cache = catalog_data if catalog_data else {}
                return self.catalog_cache
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Error reading identity catalog: {e}")
            # If there's an error, return an empty catalog
            self.catalog_cache = {}
            self._save_catalog({})
            return {}

    def _save_catalog(self, catalog: Dict[str, Dict[str, Any]]):
        """
        Saves the identity catalog to disk.

        Args:
            catalog: The catalog to save
        """
        catalog_path = self.get_catalog_path()
        try:
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=2)

            # Update cache
            self.catalog_cache = catalog
        except IOError as e:
            print(f"[ERROR] Error saving identity catalog: {e}")

    def save_identity_catalog(self, catalog: Dict[str, Dict[str, Any]]):
        """Saves the identity catalog to disk."""
        catalog_path = self.get_catalog_path()
        try:
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=2)
            self.catalog_cache = catalog
        except IOError as e:
            print(f"Error saving identity catalog: {e}")

    def get_identity(self, identity_id: str) -> Optional[Identity]:
        """Retrieves an identity by ID."""
        if identity_id in self.identity_cache:
            return self.identity_cache[identity_id]

        # Check if identity exists in catalog
        catalog = self.get_identity_catalog()
        if identity_id not in catalog:
            return None

        identity_path = self.get_identity_path(identity_id)
        if not os.path.exists(identity_path):
            return None

        try:
            # Use um executor para proteger a leitura com timeout (ex: 5 segundos)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: open(identity_path, 'r', encoding='utf-8').read())
                content = future.result(timeout=5)
            identity_data = json.loads(content)
            identity = Identity.from_dict(identity_data)
            self.identity_cache[identity_id] = identity
            return identity
        except Exception as e:
            print(f"Error reading identity {identity_id}: {e}")
            return None

    def save_identity(self, identity: Identity) -> bool:
        """Saves an identity to storage."""
        # Converts identity to dictionary
        identity_dict = identity.to_dict()

        # Update identity file
        identity_path = self.get_identity_path(identity.id)
        try:
            with open(identity_path, 'w', encoding='utf-8') as f:
                json.dump(identity_dict, f, indent=2)

            # Update cache
            self.identity_cache[identity.id] = identity

            # Update catalog
            catalog = self.get_identity_catalog()
            catalog[identity.id] = {
                "name": identity.name,
                "type": identity.type,
                "created": identity.creation_time
            }
            self.save_identity_catalog(catalog)

            return True
        except IOError as e:
            print(f"Error saving identity {identity.id}: {e}")
            return False

    def delete_identity(self, identity_id: str) -> bool:
        """Deletes an identity from storage."""
        if identity_id == "default":
            print("Cannot delete the default identity")
            return False

        catalog = self.get_identity_catalog()
        if identity_id in catalog:
            del catalog[identity_id]
            self.save_identity_catalog(catalog)

        if identity_id in self.identity_cache:
            del self.identity_cache[identity_id]

        identity_path = self.get_identity_path(identity_id)
        if os.path.exists(identity_path):
            try:
                os.remove(identity_path)
                return True
            except IOError as e:
                print(f"Error deleting identity file {identity_id}: {e}")
                return False
        return True

    def record_identity_access(self, identity_id: str) -> None:
        """
        Records that an identity was accessed.

        Args:
            identity_id: The ID of the accessed identity
        """
        identity = self.get_identity(identity_id)
        if identity:
            # Update access time
            identity.record_access()
            # Save updated identity
            self.save_identity(identity)

    def list_identities(self) -> List[Dict[str, Any]]:
        # Add verbose logging at the start
        print("[VERBOSE] Entering list_identities method")
        print(f"[VERBOSE] Base path: {self.base_path}")

        # Ensure base path exists
        import os
        if not os.path.exists(self.base_path):
            print(f"[CRITICAL] Base path does not exist: {self.base_path}")
            os.makedirs(self.base_path, exist_ok=True)

        # Always refresh the catalog to get the most up-to-date information
        catalog = self.get_identity_catalog(refresh=True)
        print(f"[VERBOSE] Catalog contents: {catalog}")

        identities = []
        for identity_id, basic_info in catalog.items():
            print(f"[VERBOSE] Processing identity: {identity_id}")

            try:
                # Attempt to get full identity details
                identity = self.get_identity(identity_id)

                if identity:
                    # Convert datetime to string explicitly
                    creation_time = str(identity.creation_time) if identity.creation_time else ""
                    last_accessed = str(identity.last_accessed) if identity.last_accessed else ""

                    identity_info = {
                        "id": identity_id,
                        "name": identity.name,
                        "description": identity.description,
                        "type": identity.type,
                        "tone": getattr(identity, 'tone', 'neutral'),
                        "personality": getattr(identity, 'personality', 'balanced'),
                        "creation_time": creation_time,
                        "last_accessed": last_accessed
                    }
                    print(f"[VERBOSE] Successfully processed identity: {identity_id}")
                else:
                    # Fallback to basic catalog information
                    print(f"[WARNING] Could not load full details for identity: {identity_id}")
                    identity_info = {
                        "id": identity_id,
                        "name": basic_info.get("name", "Unknown"),
                        "type": basic_info.get("type", "unknown"),
                        "creation_time": str(basic_info.get("created", ""))
                    }

                identities.append(identity_info)

            except Exception as e:
                print(f"[ERROR] Error processing identity {identity_id}: {e}")

        # If no identities found, create a default
        if not identities:
            print("[VERBOSE] No identities found. Creating default.")
            default_identity = {
                "id": "default",
                "name": "Cupcake",
                "description": "Default System Identity",
                "type": "system",
                "tone": "friendly",
                "personality": "helpful",
                "creation_time": datetime.utcnow().isoformat(),
                "last_accessed": datetime.utcnow().isoformat()
            }
            identities.append(default_identity)

        print(f"[VERBOSE] Returning {len(identities)} identities")
        return identities
