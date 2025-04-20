# cognisphere_adk/services_container.py
"""
services_container.py - Contém as instâncias globais dos serviços
"""

# Inicialize como None primeiramente
db_service = None
embedding_service = None
identity_store = None

def initialize_services(db, embedding):
    """
    Inicializa os serviços globais.
    """
    global db_service, embedding_service
    db_service = db
    embedding_service = embedding

def initialize_identity_store(store):
    """
    Inicializa o serviço de armazenamento de identidades.
    """
    global identity_store
    identity_store = store

def get_db_service():
    """Retorna o serviço de banco de dados."""
    return db_service

def get_embedding_service():
    """Retorna o serviço de embedding."""
    return embedding_service


def get_identity_store():
    """Retrieve the identity storage service."""
    global identity_store

    # Print debugging information
    print("[VERBOSE] get_identity_store() called")
    print(f"[VERBOSE] Current identity_store: {identity_store}")

    if identity_store is None:
        try:
            # Import here to avoid circular imports
            from data_models.identity_store import IdentityStore
            import config
            import os

            # Ensure identities directory exists
            identities_dir = os.path.join(config.DATABASE_CONFIG["path"], "identities")
            os.makedirs(identities_dir, exist_ok=True)

            # Create IdentityStore
            identity_store = IdentityStore(identities_dir)

            print("[VERBOSE] IdentityStore created successfully")
        except Exception as e:
            print(f"[CRITICAL] Failed to recreate identity store: {e}")
            return None

    return identity_store