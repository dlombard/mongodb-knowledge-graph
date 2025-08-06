"""Storage factory for creating storage adapters based on configuration.

This module provides a factory function that creates the appropriate storage
adapter based on environment variables and configuration settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from mongodb_knowledge_graph.storage.base import StorageAdapter, StorageError


class StorageFactory:
    """Factory class for creating storage adapters."""

    @staticmethod
    async def create() -> StorageAdapter:
        """Create a storage adapter based on environment configuration.
        
        Reads environment variables to determine which storage backend to use
        and creates the appropriate adapter with the correct configuration.
        
        Returns:
            An initialized storage adapter.
            
        Raises:
            StorageError: If configuration is invalid or adapter creation fails.
        """

        return await StorageFactory._create_mongodb_storage()

    @staticmethod
    async def _create_mongodb_storage() -> StorageAdapter:
        """Create a MongoDB storage adapter.
        
        Returns:
            An initialized MongoDB storage adapter.
            
        Raises:
            StorageError: If MongoDB storage creation fails.
        """
        try:
            from mongodb_knowledge_graph.storage.mongodb_adapter import MongoDBStorageAdapter
        except ImportError as e:
            raise StorageError(
                "MongoDB storage requires pymongo. Install with: pip install pymongo"
            ) from e

        config = {
            "uri": os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
            "database": os.environ.get("MONGODB_DATABASE", "mcp_memory"),
            "collection_prefix": os.environ.get("MONGODB_COLLECTION_PREFIX", ""),
        }
        
        adapter = MongoDBStorageAdapter(config)
        await adapter.initialize()
        return adapter