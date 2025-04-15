# cognisphere_adk/a2a/server.py
"""Implementação do servidor A2A para o Cognisphere."""

import json
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context


# Definir o Agent Card diretamente aqui (sem importar)
def get_agent_card():
    """Retorna o Agent Card do Cognisphere."""
    return {
        "name": "Cognisphere",
        "description": "Advanced cognitive architecture with sophisticated memory and narrative capabilities",
        "version": "1.0.0",
        "endpoint": "/a2a",  # Endpoint relativo à base URL
        "capabilities": ["streaming"],
        "skills": [
            {
                "id": "memory-management",
                "name": "Memory Management",
                "description": "Store, retrieve, and analyze memories of different types and emotional significance"
            },
            {
                "id": "narrative-weaving",
                "name": "Narrative Weaving",
                "description": "Create and manage narrative threads that organize experiences into meaningful stories"
            },
            {
                "id": "emotion-analysis",
                "name": "Emotion Analysis",
                "description": "Analyze emotional content and context of interactions"
            }
        ],
        "auth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }


# Criar Blueprint para as rotas A2A
a2a_bp = Blueprint('a2a', __name__, url_prefix='/a2a')

# Estado da tarefa
tasks = {}


@a2a_bp.route('/.well-known/agent.json')
def agent_json():
    """Endpoint para obter o Agent Card."""
    return jsonify(get_agent_card())


@a2a_bp.route('/tasks/send', methods=['POST'])
def tasks_send():
    """Endpoint para iniciar ou continuar uma tarefa."""
    # Obter runner e orchestrator da aplicação Flask
    from app import runner

    data = request.json
    task_id = data.get('taskId', str(uuid.uuid4()))
    user_id = f"a2a_user_{task_id[:8]}"

    # Obter a mensagem do usuário
    message = data.get('messages', [])[-1] if data.get('messages') else None
    if not message or message.get('role') != 'user':
        return jsonify({"error": "Invalid or missing user message"}), 400

    # Extrair o texto da mensagem
    text_parts = [part.get('text') for part in message.get('parts', [])
                  if part.get('type') == 'text' and part.get('text')]
    user_message = ' '.join(text_parts)

    if not user_message:
        return jsonify({"error": "No text content in message"}), 400

    # Criar tarefa se não existir
    if task_id not in tasks:
        tasks[task_id] = {
            "taskId": task_id,
            "state": "submitted",
            "messages": [],
            "artifacts": []
        }

    # Processar a mensagem com o runner
    try:
        # Preparar o conteúdo para o ADK
        from google.genai import types
        content = types.Content(role='user', parts=[types.Part(text=user_message)])

        # Executar o runner
        final_response = None
        event_list = []

        # Executar de forma síncrona
        for event in runner.run(
                user_id=user_id,
                session_id=task_id,
                new_message=content
        ):
            event_list.append(event)
            # Capturar a resposta final do agente
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text

        # Verificar se temos uma resposta final
        if not final_response:
            return jsonify({"error": "No response generated"}), 500

        # Atualizar a tarefa
        tasks[task_id]["state"] = "completed"

        # Adicionar a mensagem do usuário
        tasks[task_id]["messages"].append({
            "role": "user",
            "parts": [{"type": "text", "text": user_message}]
        })

        # Adicionar a resposta do agente
        tasks[task_id]["messages"].append({
            "role": "agent",
            "parts": [{"type": "text", "text": final_response}]
        })

        # Retornar o resultado da tarefa
        return jsonify(tasks[task_id])

    except Exception as e:
        tasks[task_id]["state"] = "failed"
        tasks[task_id]["error"] = str(e)
        return jsonify({"error": f"Error processing task: {str(e)}"}), 500


@a2a_bp.route('/tasks/get', methods=['GET'])
def tasks_get():
    """Endpoint para obter o estado de uma tarefa."""
    task_id = request.args.get('taskId')
    if not task_id or task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(tasks[task_id])


@a2a_bp.route('/tasks/cancel', methods=['POST'])
def tasks_cancel():
    """Endpoint para cancelar uma tarefa."""
    data = request.json
    task_id = data.get('taskId')
    if not task_id or task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404

    tasks[task_id]["state"] = "canceled"
    return jsonify(tasks[task_id])


def register_a2a_blueprint(app):
    """Registra o blueprint do A2A na aplicação Flask."""
    app.register_blueprint(a2a_bp)