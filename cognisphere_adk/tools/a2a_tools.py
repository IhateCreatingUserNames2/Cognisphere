# cognisphere_adk/tools/a2a_tools.py
"""Ferramentas para interagir com agentes externos usando o protocolo A2A."""

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any, List, Optional
import asyncio
import json
import aiohttp
import uuid


# Implementar classe A2AClient diretamente aqui em vez de importá-la
class A2AClient:
    """Cliente para interagir com agentes que implementam o protocolo A2A."""

    def __init__(self, default_timeout: int = 60):
        self.default_timeout = default_timeout
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def get_agent_card(self, agent_url: str) -> Dict[str, Any]:
        await self.ensure_session()

        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        card_url = f"{agent_url}/.well-known/agent.json"

        try:
            async with self.session.get(card_url, timeout=self.default_timeout) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise ValueError(f"Failed to get agent card: {response.status} - {error_text}")
        except Exception as e:
            raise ConnectionError(f"Error connecting to agent at {card_url}: {str(e)}")

    async def tasks_send(
            self,
            agent_url: str,
            task_id: Optional[str] = None,
            messages: Optional[List[Dict[str, Any]]] = None,
            user_message: Optional[str] = None,
            timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        await self.ensure_session()

        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        tasks_url = f"{agent_url}/a2a/tasks/send"

        if task_id is None:
            task_id = str(uuid.uuid4())

        if messages is None:
            if user_message is None:
                raise ValueError("Either messages or user_message must be provided")

            messages = [{
                "role": "user",
                "parts": [{"type": "text", "text": user_message}]
            }]

        payload = {
            "taskId": task_id,
            "messages": messages
        }

        req_timeout = timeout if timeout is not None else self.default_timeout

        try:
            async with self.session.post(
                    tasks_url,
                    json=payload,
                    timeout=req_timeout
            ) as response:
                if response.status in (200, 201, 202):
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise ValueError(f"Failed to send task: {response.status} - {error_text}")
        except Exception as e:
            raise ConnectionError(f"Error connecting to agent at {tasks_url}: {str(e)}")


async def connect_to_external_agent(
        url: str,
        query: str,
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Conecta a um agente externo para processar uma consulta.

    Args:
        url: URL do agente externo (ex: http://example.com/agent)
        query: A consulta a ser enviada para o agente
        tool_context: Contexto da ferramenta

    Returns:
        Resposta do agente externo
    """
    try:
        async with A2AClient() as client:
            # Tenta obter o agent card para verificar se é um agente A2A válido
            try:
                agent_card = await client.get_agent_card(url)
                print(f"Conectado ao agente: {agent_card.get('name', 'Unknown')}")
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Falha ao obter o Agent Card: {str(e)}",
                    "is_valid_agent": False
                }

            # Envia a tarefa
            response = await client.tasks_send(
                agent_url=url,
                user_message=query
            )

            # Extrai a resposta final do agente
            agent_messages = [msg for msg in response.get("messages", [])
                              if msg.get("role") == "agent"]

            if agent_messages:
                # Pegar a última mensagem do agente
                last_message = agent_messages[-1]
                text_parts = [part.get("text") for part in last_message.get("parts", [])
                              if part.get("type") == "text" and part.get("text")]

                agent_response = " ".join(text_parts)

                # Se tiver artefatos, incluir
                artifacts = response.get("artifacts", [])
                artifact_info = []

                for artifact in artifacts:
                    artifact_parts = artifact.get("parts", [])
                    for part in artifact_parts:
                        if part.get("type") == "text":
                            artifact_info.append(part.get("text", ""))

                return {
                    "status": "success",
                    "agent_name": agent_card.get("name", "Unknown Agent"),
                    "agent_response": agent_response,
                    "artifacts": artifact_info,
                    "task_id": response.get("taskId"),
                    "skills": agent_card.get("skills", [])
                }
            else:
                return {
                    "status": "error",
                    "message": "Resposta do agente não contém mensagens"
                }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erro ao conectar com o agente externo: {str(e)}"
        }


async def discover_a2a_agents(
        urls: List[str],
        tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Descobre informações sobre vários agentes A2A.

    Args:
        urls: Lista de URLs de possíveis agentes A2A
        tool_context: Contexto da ferramenta

    Returns:
        Informações sobre os agentes descobertos
    """
    discovered_agents = []
    errors = []

    async with A2AClient() as client:
        for url in urls:
            try:
                agent_card = await client.get_agent_card(url)
                discovered_agents.append({
                    "url": url,
                    "name": agent_card.get("name", "Unknown"),
                    "description": agent_card.get("description", ""),
                    "skills": agent_card.get("skills", []),
                    "capabilities": agent_card.get("capabilities", [])
                })
            except Exception as e:
                errors.append({
                    "url": url,
                    "error": str(e)
                })

    return {
        "status": "success",
        "agents": discovered_agents,
        "errors": errors,
        "count": len(discovered_agents)
    }


# Criar as ferramentas para usar no Orchestrator Agent
connect_external_agent_tool = FunctionTool(connect_to_external_agent)
discover_a2a_agents_tool = FunctionTool(discover_a2a_agents)