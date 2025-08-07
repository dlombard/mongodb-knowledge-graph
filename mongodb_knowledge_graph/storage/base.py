"""Base storage adapter interface.

This module defines the abstract base class that all storage adapters must
implement. It provides a common interface for different storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from mongodb_knowledge_graph.models import KnowledgeGraph


class StorageAdapter(ABC):
    """Abstract base class for storage adapters.
    
    All storage implementations must inherit from this class and implement
    all abstract methods. This ensures a consistent interface across different
    storage backends.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the storage adapter with configuration.
        
        Args:
            config: Configuration dictionary specific to the storage backend.
        """
        self.config = config

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend.
        
        This method should perform any necessary setup, such as creating
        connections, initializing databases, or setting up file structures.
        
        Raises:
            StorageError: If initialization fails.
        """

    @abstractmethod
    async def load_graph(self) -> KnowledgeGraph:
        """Load the complete knowledge graph from storage.
        
        Returns:
            The complete knowledge graph with all entities and relations.
            
        Raises:
            StorageError: If loading fails.
        """

    @abstractmethod
    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Save the complete knowledge graph to storage.
        
        This method should completely replace the existing graph with the
        provided one, ensuring atomic updates where possible.
        
        Args:
            graph: The knowledge graph to save.
            
        Raises:
            StorageError: If saving fails.
        """

    @abstractmethod
    async def close(self) -> None:
        """Close the storage backend and clean up resources.
        
        This method should properly close any connections and clean up
        resources used by the storage backend.
        """


class StorageError(Exception):
    """Base exception for storage-related errors."""

    pass