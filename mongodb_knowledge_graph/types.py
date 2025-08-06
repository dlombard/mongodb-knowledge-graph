"""Type definitions and data models for the memory server.

This module defines the core data structures used throughout the memory server,
including entities, relations, and knowledge graphs. All models use Pydantic
for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, ConfigDict


class StorageType(str, Enum):
    """Supported storage backend types."""

    FILE = "file"
    MONGODB = "mongodb"


class Entity(BaseModel):
    """Represents a node in the knowledge graph.
    
    Entities are the primary nodes that can represent people, organizations,
    events, or any other conceptual object. Each entity has a unique name,
    a type classification, and associated observations.
    
    Attributes:
        name: Unique identifier for the entity.
        entity_type: Classification of the entity (e.g., 'person', 'organization').
        observations: List of discrete facts about the entity.
    """

    name: str = Field(..., description="Unique identifier for the entity")
    entity_type: str = Field(
        ..., description="Type classification of the entity", alias="entityType"
    )
    observations: List[str] = Field(
        default_factory=list, description="List of facts about the entity"
    )

    model_config = ConfigDict(populate_by_name=True)


class Relation(BaseModel):
    """Represents a directed edge in the knowledge graph.
    
    Relations define connections between entities and are always stored in
    active voice to describe how entities interact or relate to each other.
    
    Attributes:
        from_entity: Name of the source entity.
        to_entity: Name of the target entity.  
        relation_type: Type of relationship in active voice.
    """

    from_entity: str = Field(..., description="Source entity name", alias="from")
    to_entity: str = Field(..., description="Target entity name", alias="to")
    relation_type: str = Field(
        ..., description="Relationship type in active voice", alias="relationType"
    )

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeGraph(BaseModel):
    """Complete representation of the knowledge graph.
    
    Contains all entities and relations that make up the knowledge graph,
    providing a complete snapshot of the stored knowledge.
    
    Attributes:
        entities: All entities in the graph.
        relations: All relations between entities.
    """

    entities: List[Entity] = Field(
        default_factory=list, description="All entities in the graph"
    )
    relations: List[Relation] = Field(
        default_factory=list, description="All relations between entities"
    )


class FileStorageConfig(BaseModel):
    """Configuration for file-based storage."""

    file_path: str = Field(..., description="Path to the storage file")


class MongoDBStorageConfig(BaseModel):
    """Configuration for MongoDB storage."""

    uri: str = Field(..., description="MongoDB connection URI")
    database: str = Field(..., description="Database name")
    collection_prefix: str = Field(
        default="", description="Optional prefix for collection names"
    )


class ObservationRequest(BaseModel):
    """Request model for adding observations to an entity."""

    entity_name: str = Field(..., description="Name of the target entity")
    contents: List[str] = Field(..., description="Observations to add")


class ObservationResponse(BaseModel):
    """Response model for observation additions."""

    entity_name: str = Field(..., description="Name of the entity")
    added_observations: List[str] = Field(
        ..., description="Observations that were added"
    )


class ObservationDeletion(BaseModel):
    """Request model for deleting observations from an entity."""

    entity_name: str = Field(..., description="Name of the target entity")
    observations: List[str] = Field(..., description="Observations to delete")