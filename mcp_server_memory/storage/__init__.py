"""Storage backend abstraction and implementations."""

from mcp_server_memory.storage.base import StorageAdapter
from mcp_server_memory.storage.factory import StorageFactory
from mcp_server_memory.storage.file_adapter import FileStorageAdapter

__all__ = ["StorageAdapter", "StorageFactory", "FileStorageAdapter"]

# MongoDB adapter is imported conditionally to avoid import errors
# when pymongo is not available
try:
    from mcp_server_memory.storage.mongodb_adapter import MongoDBStorageAdapter

    __all__.append("MongoDBStorageAdapter")
except ImportError:
    pass