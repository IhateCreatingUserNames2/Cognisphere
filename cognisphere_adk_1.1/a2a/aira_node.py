import aiohttp
import asyncio
import time
import hashlib
import json
import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, validator
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - AiraNode - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Resource(BaseModel):
    """Represents a shared resource in the AIRA network."""
    uri: str
    description: str
    type: str = "mcp_tool"
    version: str = "1.0.0"
    timestamp: float = Field(default_factory=time.time)

    @validator('uri')
    def validate_uri(cls, v):
        """Ensure URI is valid."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URI must start with http:// or https://")
        return v


class AiraNode:
    """
    Advanced AIRA Node for agent registration, discovery, and interaction.

    Provides comprehensive methods for:
    - Hub registration
    - Periodic heartbeats
    - Resource sharing
    - Agent discovery
    - Tool invocation
    """

    def __init__(
            self,
            hub_url: str,
            agent_url: str = None,
            agent_name: str = "Cognisphere",
            private_key: Optional[str] = None,
            registration_timeout: int = 30,
            heartbeat_interval: int = 30
    ):
        """
        Initialize AiraNode with comprehensive configuration.

        Args:
            hub_url: URL of the AIRA hub
            agent_url: URL where this agent is accessible
            agent_name: Name of the agent
            private_key: Optional private key for signatures
            registration_timeout: Timeout for registration requests
            heartbeat_interval: Interval between heartbeats
        """
        self.hub_url = hub_url.rstrip('/')
        self.agent_url = agent_url or f"http://{agent_name.lower()}.local"
        self.agent_name = agent_name
        self.private_key = private_key

        # Configuration
        self.registration_timeout = registration_timeout
        self.heartbeat_interval = heartbeat_interval

        # State management
        self.session: Optional[aiohttp.ClientSession] = None
        self.shared_resources: List[Resource] = []
        self.registration_status: Dict[str, Any] = {
            "registered": False,
            "last_registration_time": None,
            "registration_attempts": 0
        }

        # Heartbeat task management
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Logging setup
        self.logger = logger

    async def _ensure_session(self):
        """Ensure an aiohttp ClientSession is available."""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    def _generate_signature(self, data: dict) -> str:
        """
        Generate a cryptographic signature for the payload.

        Args:
            data: Dictionary to be signed

        Returns:
            Hexadecimal signature string
        """
        if not self.private_key:
            return ""

        try:
            return hashlib.sha256(
                json.dumps(data, sort_keys=True).encode() +
                self.private_key.encode()
            ).hexdigest()
        except Exception as e:
            self.logger.error(f"Signature generation failed: {e}")
            return ""

    async def register(self) -> Dict[str, Any]:
        """
        Register the agent with the AIRA hub.

        Implements robust registration with timeout and retry logic.

        Returns:
            Registration response from the hub
        """
        await self._ensure_session()

        # Prepare registration payload
        payload = {
            "url": self.agent_url,
            "name": self.agent_name,
            "skills": [],  # Populate skills dynamically
            "shared_resources": [r.dict() for r in self.shared_resources],
            "aira_capabilities": ["a2a", "resource_sharing"],
            "auth": {},  # Configure authentication if needed
            "signature": "",  # Add signature if private key is available
            "tags": ["cognitive", "ai", "agent"]
        }

        # Add signature if private key exists
        if self.private_key:
            payload["signature"] = self._generate_signature(payload)

        try:
            # Use explicit timeout
            timeout = aiohttp.ClientTimeout(total=self.registration_timeout)

            async with self.session.post(
                    f"{self.hub_url}/register",
                    json=payload,
                    timeout=timeout
            ) as resp:
                # Detailed logging and error handling
                if resp.status in (200, 201):
                    response_data = await resp.json()
                    self.registration_status.update({
                        "registered": True,
                        "last_registration_time": time.time(),
                        "registration_attempts":
                            self.registration_status.get("registration_attempts", 0) + 1
                    })
                    self.logger.info(f"Successfully registered with AIRA hub: {response_data}")
                    return response_data
                else:
                    error_text = await resp.text()
                    self.logger.error(f"Registration failed: {resp.status} - {error_text}")
                    raise ValueError(f"Registration failed: {error_text}")

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"Registration error: {e}")
            self.registration_status["registered"] = False
            raise

    async def start_heartbeat(self):
        """
        Start periodic heartbeat task.
        Ensures only one heartbeat task is running.
        """
        # Cancel existing heartbeat task if running
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        async def heartbeat_loop():
            while True:
                try:
                    await self._send_heartbeat()
                    await asyncio.sleep(self.heartbeat_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
                    await asyncio.sleep(self.heartbeat_interval)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _send_heartbeat(self):
        """
        Send a heartbeat to the AIRA hub.
        Handles connection and registration status.
        """
        await self._ensure_session()

        if not self.registration_status.get("registered", False):
            await self.register()

        try:
            async with self.session.post(
                    f"{self.hub_url}/heartbeat/{self.agent_name}"
            ) as resp:
                if resp.status != 200:
                    self.logger.warning(f"Heartbeat failed: {resp.status}")
                    # Optional: Attempt re-registration
                    await self.register()
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")
            # Attempt to re-register or reset session
            await self._ensure_session()

    async def discover_agents(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        Discover agents with comprehensive filtering options.

        Args:
            filters: Optional dictionary of filtering criteria

        Returns:
            List of discovered agents
        """
        await self._ensure_session()

        try:
            params = filters or {}
            async with self.session.post(
                    f"{self.hub_url}/discover",
                    json=params
            ) as resp:
                if resp.status == 200:
                    agents = await resp.json()
                    self.logger.info(f"Discovered {len(agents)} agents")
                    return agents
                else:
                    error_text = await resp.text()
                    self.logger.error(f"Agent discovery failed: {error_text}")
                    return []
        except Exception as e:
            self.logger.error(f"Agent discovery error: {e}")
            return []

    async def close(self):
        """
        Gracefully close all resources.
        """
        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close aiohttp session
        if self.session and not self.session.closed:
            await self.session.close()

        self.logger.info("AiraNode resources closed successfully")

    async def __aenter__(self):
        """Context manager entry point."""
        await self.register()
        await self.start_heartbeat()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Context manager exit point."""
        await self.close()