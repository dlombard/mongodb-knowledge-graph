"""File-based storage adapter implementation.

This module provides a storage adapter that uses JSON Lines format to store
the knowledge graph in a local file. Each line contains either an entity
or relation object with a type field to distinguish between them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from mongodb_knowledge_graph.storage.base import StorageAdapter, StorageError
from mongodb_knowledge_graph.types import Entity, KnowledgeGraph, Relation


class FileStorageAdapter(StorageAdapter):
    """File-based storage adapter using JSON Lines format.
    
    This adapter stores the knowledge graph in a local file using JSON Lines
    format where each line contains either an entity or relation object.
    The format is compatible with the original TypeScript implementation.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the file storage adapter.
        
        Args:
            config: Configuration dictionary containing 'file_path' key.
        """
        super().__init__(config)
        self.file_path = Path(config["file_path"])

    async def initialize(self) -> None:
        """Initialize the file storage.
        
        Creates the parent directory if it doesn't exist. No other setup
        is required for file-based storage.
        
        Raises:
            StorageError: If directory creation fails.
        """
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Failed to create directory: {e}") from e

    async def load_graph(self) -> KnowledgeGraph:
        """Load the knowledge graph from the JSON Lines file.
        
        Reads each line from the file and reconstructs the entities and relations.
        Returns an empty graph if the file doesn't exist.
        
        Returns:
            The complete knowledge graph loaded from the file.
            
        Raises:
            StorageError: If file reading or parsing fails.
        """
        if not self.file_path.exists():
            return KnowledgeGraph()

        entities = []
        relations = []

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                        item_type = item.get("type")

                        if item_type == "entity":
                            # Remove type field and create Entity
                            item.pop("type", None)
                            entities.append(Entity(**item))
                        elif item_type == "relation":
                            # Remove type field and create Relation
                            item.pop("type", None)
                            relations.append(Relation(**item))

                    except (json.JSONDecodeError, TypeError, ValueError) as e:
                        raise StorageError(
                            f"Invalid JSON on line {line_num}: {e}"
                        ) from e

        except OSError as e:
            raise StorageError(f"Failed to read file {self.file_path}: {e}") from e

        return KnowledgeGraph(entities=entities, relations=relations)

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Save the knowledge graph to the JSON Lines file.
        
        Writes all entities and relations to the file, one JSON object per line.
        The file is completely overwritten to ensure consistency.
        
        Args:
            graph: The knowledge graph to save.
            
        Raises:
            StorageError: If file writing fails.
        """
        try:
            lines = []

            # Add entities with type field
            for entity in graph.entities:
                entity_dict = entity.dict(by_alias=True)
                entity_dict["type"] = "entity"
                lines.append(json.dumps(entity_dict, ensure_ascii=False))

            # Add relations with type field
            for relation in graph.relations:
                relation_dict = relation.dict(by_alias=True)
                relation_dict["type"] = "relation"
                lines.append(json.dumps(relation_dict, ensure_ascii=False))

            # Write all lines atomically using temporary file
            temp_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")

            with temp_path.open("w", encoding="utf-8") as file:
                file.write("\n".join(lines))
                if lines:  # Add final newline if there's content
                    file.write("\n")

            # Atomic rename to replace original file
            temp_path.replace(self.file_path)

        except OSError as e:
            raise StorageError(f"Failed to write file {self.file_path}: {e}") from e

    async def close(self) -> None:
        """Close the file storage adapter.
        
        No cleanup is required for file-based storage.
        """
        pass