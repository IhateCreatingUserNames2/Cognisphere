# cognisphere_adk/data_models/registered_agent.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

class RegisteredAgent(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str  # For LLM-based selection and user understanding
    capabilities: List[str] = Field(default_factory=list) # Keywords or formal capability URIs
    module_path: str  # e.g., "agents.weather_agent"
    creation_function: str  # e.g., "create_weather_agent"
    default_model: Optional[str] = "openai/gpt-4o-mini" # Default model for this agent
    initial_instruction_prompt: Optional[str] = "" # Default instruction
    required_tools: List[str] = Field(default_factory=list) # Names of tools this agent might need from global tools
    # Future fields: permissions, version, author, etc.

    class Config:
        validate_assignment = True # Ensure fields are validated on assignment too