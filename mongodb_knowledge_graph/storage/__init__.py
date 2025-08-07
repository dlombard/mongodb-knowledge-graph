"""Storage backend abstraction and implementations."""

from mongodb_knowledge_graph.storage.base import StorageAdapter
from mongodb_knowledge_graph.storage.factory import StorageFactory

__all__ = ["StorageAdapter", "StorageFactory"]

# MongoDB adapter is imported conditionally to avoid import errors
# when pymongo is not available
try:
    from mongodb_knowledge_graph.storage.mongodb_adapter import MongoDBStorageAdapter

    __all__.append("MongoDBStorageAdapter")
except ImportError:
    pass