import aiohttp
import asyncio
import time
import hashlib
import json
from typing import List, Dict, Optional
from pydantic import BaseModel
from agent_card import get_agent_card


class Resource(BaseModel):
    uri: str
    description: str
    type: str = "mcp_tool"
    version: str = "1.0.0"
    timestamp: float = time.time()


class AiraNode:
    def __init__(self, hub_url: str, private_key: Optional[str] = None):
        self.hub_url = hub_url.rstrip('/')
        self.session = aiohttp.ClientSession()
        self.agent_card = get_agent_card()
        self.shared_resources: List[Resource] = []
        self.private_key = private_key

    def _generate_signature(self, data: dict) -> str:
        if not self.private_key:
            return ""
        return hashlib.sha256(
            json.dumps(data).encode() + self.private_key.encode()
        ).hexdigest()

    async def _register(self):
        payload = {
            "url": f"http://{self.agent_card['name'].lower()}.local",
            "name": self.agent_card["name"],
            "skills": self.agent_card["skills"],
            "shared_resources": [r.dict() for r in self.shared_resources],
            "aira_capabilities": ["resource_sharing"],
            "auth": self.agent_card["auth"],
            "signature": self._generate_signature(self.agent_card)
        }

        async with self.session.post(
                f"{self.hub_url}/register",
                json=payload
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise ValueError(f"Registration failed: {error}")
            return await resp.json()

    async def connect(self):
        """Register with hub and start heartbeat"""
        reg_result = await self._register()
        await asyncio.create_task(self._heartbeat_task())
        return reg_result

    async def _heartbeat_task(self):
        """Background task to send periodic heartbeats"""
        while True:
            await asyncio.sleep(30)
            try:
                await self.session.post(
                    f"{self.hub_url}/heartbeat/{self.agent_card['name'].lower()}.local"
                )
            except Exception as e:
                print(f"Heartbeat failed: {str(e)}")

    async def share_mcp_tool(self, tool_uri: str, description: str, version: str = "1.0.0"):
        """Share a new tool version"""
        self.shared_resources.append(Resource(
            uri=tool_uri,
            description=description,
            version=version
        ))
        return await self._register()

    async def discover_agents(self, skill: Optional[str] = None) -> List[Dict]:
        """Discover agents with optional skill filter"""
        params = {"skill": skill} if skill else None
        async with self.session.get(
                f"{self.hub_url}/discover",
                params=params
        ) as resp:
            return await resp.json()

    async def invoke_tool(self, agent_url: str, tool_uri: str, params: dict):
        """Invoke a remote tool"""
        async with self.session.post(
                f"{agent_url}/invoke",
                json={"tool": tool_uri, "params": params}
        ) as resp:
            return await resp.json()

    async def close(self):
        """Cleanup resources"""
        await self.session.close()