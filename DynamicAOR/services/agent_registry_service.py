# cognisphere_adk/services/agent_registry_service.py
import os
import json
import uuid
from typing import List, Optional, Dict, Any
from data_models.registered_agent import RegisteredAgent
import config  # To get the base data path


class AgentRegistryService:
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            base_data_path = config.DATABASE_CONFIG.get("path", "./cognisphere_data")
            self.storage_path = os.path.join(base_data_path, "registered_agents")
        else:
            self.storage_path = storage_path

        os.makedirs(self.storage_path, exist_ok=True)
        self._agents_cache: Dict[str, RegisteredAgent] = {}
        self._load_all_agents_from_storage()

    def _get_agent_file_path(self, agent_id: str) -> str:
        return os.path.join(self.storage_path, f"{agent_id}.json")

    def _load_all_agents_from_storage(self):
        self._agents_cache.clear()
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json"):
                agent_id = filename[:-5]  # Remove .json
                try:
                    with open(self._get_agent_file_path(agent_id), 'r') as f:
                        data = json.load(f)
                        self._agents_cache[agent_id] = RegisteredAgent(**data)
                except (IOError, json.JSONDecodeError, TypeError) as e:
                    print(f"Error loading agent config {filename}: {e}")

    def register_agent(self, agent_config: RegisteredAgent) -> RegisteredAgent:
        if not isinstance(agent_config, RegisteredAgent):
            raise TypeError("agent_config must be an instance of RegisteredAgent")

        # Ensure agent_id is set
        if not agent_config.agent_id:
            agent_config.agent_id = str(uuid.uuid4())

        file_path = self._get_agent_file_path(agent_config.agent_id)
        try:
            with open(file_path, 'w') as f:
                json.dump(agent_config.model_dump(), f, indent=2)  # Use model_dump for Pydantic
            self._agents_cache[agent_config.agent_id] = agent_config
            return agent_config
        except IOError as e:
            print(f"Error saving agent {agent_config.name}: {e}")
            raise

    def get_agent_config(self, agent_id: str) -> Optional[RegisteredAgent]:
        if agent_id in self._agents_cache:
            return self._agents_cache[agent_id]

        file_path = self._get_agent_file_path(agent_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    agent = RegisteredAgent(**data)
                    self._agents_cache[agent_id] = agent
                    return agent
            except (IOError, json.JSONDecodeError, TypeError) as e:
                print(f"Error loading agent config for {agent_id}: {e}")
        return None

    def list_agents(self) -> List[RegisteredAgent]:
        # Ensure cache is up-to-date if files were added/removed externally
        # For simplicity here, we rely on the cache. A more robust system
        # might check file modification times or use a database.
        self._load_all_agents_from_storage()  # Refresh cache
        return list(self._agents_cache.values())

    def find_agents_by_capability(self, capability: str) -> List[RegisteredAgent]:
        self._load_all_agents_from_storage()  # Refresh cache
        matched_agents = []
        for agent in self._agents_cache.values():
            if capability.lower() in [cap.lower() for cap in agent.capabilities]:
                matched_agents.append(agent)
        return matched_agents

    def find_agent_by_name(self, name: str) -> Optional[RegisteredAgent]:
        self._load_all_agents_from_storage()  # Refresh cache
        for agent in self._agents_cache.values():
            if agent.name.lower() == name.lower():
                return agent
        return None

    def delete_agent(self, agent_id: str) -> bool:
        if agent_id in self._agents_cache:
            del self._agents_cache[agent_id]

        file_path = self._get_agent_file_path(agent_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError as e:
                print(f"Error deleting agent file {agent_id}: {e}")
                return False
        return False  # Agent not found