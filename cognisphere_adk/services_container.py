"""
 # cognisphere_adk/services_container.py
services_container.py - Contém as instâncias globais dos serviços
"""

# Inicialize como None primeiramente
db_service = None
embedding_service = None

def initialize_services(db, embedding):
    """
    Inicializa os serviços globais.
    """
    global db_service, embedding_service
    db_service = db
    embedding_service = embedding

def get_db_service():
    """Retorna o serviço de banco de dados."""
    return db_service

def get_embedding_service():
    """Retorna o serviço de embedding."""
    return embedding_service