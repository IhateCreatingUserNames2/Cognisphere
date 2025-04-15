# cognisphere_adk/a2a/client.py (continuação)
"""Cliente A2A para o Cognisphere que permite interagir com outros agentes A2A."""

import aiohttp
import uuid
import json
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator


class A2AClient:
    """Cliente para interagir com agentes que implementam o protocolo A2A."""

    def __init__(self, default_timeout: int = 60):
        """
        Inicializa o cliente A2A.

        Args:
            default_timeout: Tempo limite padrão para requisições em segundos
        """
        self.default_timeout = default_timeout
        self.session = None

    async def __aenter__(self):
        """Inicializa a sessão HTTP ao entrar no contexto."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Fecha a sessão HTTP ao sair do contexto."""
        if self.session:
            await self.session.close()
            self.session = None

    async def ensure_session(self):
        """Garante que haja uma sessão HTTP ativa."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def get_agent_card(self, agent_url: str) -> Dict[str, Any]:
        """
        Obtém o Agent Card de um agente A2A.

        Args:
            agent_url: URL base do agente

        Returns:
            O Agent Card como um dicionário
        """
        await self.ensure_session()

        # Normalizar URL
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
        """
        Envia uma tarefa a um agente A2A.

        Args:
            agent_url: URL base do agente
            task_id: ID opcional da tarefa (gerado automaticamente se não fornecido)
            messages: Lista de mensagens (precisa conter pelo menos uma mensagem de usuário)
            user_message: Mensagem do usuário (alternativa simplificada a messages)
            timeout: Tempo limite para a requisição (usa o padrão se não especificado)

        Returns:
            A resposta do agente
        """
        await self.ensure_session()

        # Normalizar URL
        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        # Verificar qual endpoint A2A usar
        tasks_url = f"{agent_url}/a2a/tasks/send"

        # Gerar task_id se não fornecido
        if task_id is None:
            task_id = str(uuid.uuid4())

        # Preparar mensagens
        if messages is None:
            if user_message is None:
                raise ValueError("Either messages or user_message must be provided")

            messages = [{
                "role": "user",
                "parts": [{"type": "text", "text": user_message}]
            }]

        # Preparar payload
        payload = {
            "taskId": task_id,
            "messages": messages
        }

        # Definir timeout
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

    async def tasks_get(self, agent_url: str, task_id: str) -> Dict[str, Any]:
        """
        Obtém o estado atual de uma tarefa.

        Args:
            agent_url: URL base do agente
            task_id: ID da tarefa a ser consultada

        Returns:
            O estado atual da tarefa
        """
        await self.ensure_session()

        # Normalizar URL
        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        tasks_url = f"{agent_url}/a2a/tasks/get?taskId={task_id}"

        try:
            async with self.session.get(
                    tasks_url,
                    timeout=self.default_timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise ValueError(f"Failed to get task: {response.status} - {error_text}")
        except Exception as e:
            raise ConnectionError(f"Error connecting to agent at {tasks_url}: {str(e)}")

    async def tasks_cancel(self, agent_url: str, task_id: str) -> Dict[str, Any]:
        """
        Cancela uma tarefa em andamento.

        Args:
            agent_url: URL base do agente
            task_id: ID da tarefa a ser cancelada

        Returns:
            O estado final da tarefa cancelada
        """
        await self.ensure_session()

        # Normalizar URL
        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        tasks_url = f"{agent_url}/a2a/tasks/cancel"
        payload = {"taskId": task_id}

        try:
            async with self.session.post(
                    tasks_url,
                    json=payload,
                    timeout=self.default_timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise ValueError(f"Failed to cancel task: {response.status} - {error_text}")
        except Exception as e:
            raise ConnectionError(f"Error connecting to agent at {tasks_url}: {str(e)}")

    async def tasks_send_subscribe(
            self,
            agent_url: str,
            task_id: Optional[str] = None,
            messages: Optional[List[Dict[str, Any]]] = None,
            user_message: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Inicia uma tarefa com streaming de atualizações.

        Args:
            agent_url: URL base do agente
            task_id: ID opcional da tarefa (gerado automaticamente se não fornecido)
            messages: Lista de mensagens (precisa conter pelo menos uma mensagem de usuário)
            user_message: Mensagem do usuário (alternativa simplificada a messages)

        Yields:
            Atualizações da tarefa conforme são recebidas
        """
        await self.ensure_session()

        # Normalizar URL
        if agent_url.endswith('/'):
            agent_url = agent_url[:-1]

        tasks_url = f"{agent_url}/a2a/tasks/sendSubscribe"

        # Gerar task_id se não fornecido
        if task_id is None:
            task_id = str(uuid.uuid4())

        # Preparar mensagens
        if messages is None:
            if user_message is None:
                raise ValueError("Either messages or user_message must be provided")

            messages = [{
                "role": "user",
                "parts": [{"type": "text", "text": user_message}]
            }]

        # Preparar payload
        payload = {
            "taskId": task_id,
            "messages": messages
        }

        try:
            async with self.session.post(
                    tasks_url,
                    json=payload,
                    timeout=0  # Sem timeout para streaming
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to start streaming task: {response.status} - {error_text}")

                # Processar o stream de eventos SSE
                buffer = ""
                async for line in response.content:
                    line = line.decode('utf-8')
                    buffer += line

                    # Se temos pelo menos uma linha completa
                    if '\n\n' in buffer:
                        parts = buffer.split('\n\n')
                        events = parts[:-1]  # Todos os eventos completos
                        buffer = parts[-1]  # Resto incompleto

                        for event_data in events:
                            if not event_data.strip():
                                continue

                            # Extrair tipo de evento e dados
                            event_type = None
                            data = None

                            for line in event_data.split('\n'):
                                if line.startswith('event:'):
                                    event_type = line[6:].strip()
                                elif line.startswith('data:'):
                                    data = line[5:].strip()

                            if data:
                                try:
                                    parsed_data = json.loads(data)
                                    yield {
                                        "event_type": event_type,
                                        "data": parsed_data
                                    }
                                except json.JSONDecodeError:
                                    # Dados inválidos, ignorar
                                    pass
        except Exception as e:
            raise ConnectionError(f"Error in streaming connection to {tasks_url}: {str(e)}")