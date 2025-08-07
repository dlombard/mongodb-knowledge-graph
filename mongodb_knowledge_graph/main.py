"""Modern MCP server implementation using FastMCP.

This module implements the Memory Context Protocol (MCP) server using the modern
FastMCP pattern. The server provides tools for managing a knowledge graph-based
memory system with automatic schema generation from type hints.
"""

from __future__ import annotations

import os
import sys
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)

from mcp.server.fastmcp import FastMCP

from mongodb_knowledge_graph.knowledge_graph import KnowledgeGraphManager
from mongodb_knowledge_graph.storage.base import StorageError
from mongodb_knowledge_graph.storage.factory import StorageFactory
from mongodb_knowledge_graph.models import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationRequest,
    ObservationResponse,
    Relation,
)

# Configure logging

# Global variables for server state
storage = None
knowledge_graph_manager = None

# Create the FastMCP server
mcp = FastMCP("mongodb-knowledge-graph")


async def initialize_storage() -> None:
    """Initialize the storage backend and knowledge graph manager."""
    global storage, knowledge_graph_manager
    
    try:
        storage = await StorageFactory.create()
        knowledge_graph_manager = KnowledgeGraphManager(storage)
        storage_type = os.environ.get("STORAGE_TYPE", "file")
        logging.info(f"Knowledge Graph MCP Server initialized with {storage_type} storage")
    except StorageError as e:
        logging.error(f"Failed to initialize storage: {e}")
        # Fallback to file storage if MongoDB fails
        if os.environ.get("STORAGE_TYPE") == "mongodb":
            logging.info("Falling back to file storage...")
            os.environ["STORAGE_TYPE"] = "file"
            storage = await StorageFactory.create()
            knowledge_graph_manager = KnowledgeGraphManager(storage)
        else:
            raise


@mcp.tool()
async def create_entities(entities: List[Entity]) -> List[Entity]:
    """Create multiple new entities in the knowledge graph.
    
    Args:
        entities: List of entities to create with their observations.
        
    Returns:
        List of entities that were actually created (excludes duplicates).
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.create_entities(entities)


@mcp.tool()
async def create_relations(relations: List[Relation]) -> List[Relation]:
    """Create multiple new relations between entities in the knowledge graph.
    
    Relations should be in active voice describing how entities relate.
    
    Args:
        relations: List of relations to create between existing entities.
        
    Returns:
        List of relations that were actually created (excludes duplicates).
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.create_relations(relations)


@mcp.tool()
async def add_observations(observations: List[ObservationRequest]) -> List[ObservationResponse]:
    """Add new observations to existing entities in the knowledge graph.
    
    Args:
        observations: List of observation requests specifying entity names and contents.
        
    Returns:
        List of responses indicating which observations were added to each entity.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.add_observations(observations)


@mcp.tool()
async def delete_entities(entity_names: List[str]) -> str:
    """Delete multiple entities and their associated relations from the knowledge graph.
    
    Args:
        entity_names: List of entity names to delete.
        
    Returns:
        Success message confirming deletion.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    await knowledge_graph_manager.delete_entities(entity_names)
    return "Entities deleted successfully"


@mcp.tool()
async def delete_observations(deletions: List[ObservationDeletion]) -> str:
    """Delete specific observations from entities in the knowledge graph.
    
    Args:
        deletions: List of deletion requests specifying entities and observations to remove.
        
    Returns:
        Success message confirming deletion.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    await knowledge_graph_manager.delete_observations(deletions)
    return "Observations deleted successfully"


@mcp.tool()
async def delete_relations(relations: List[Relation]) -> str:
    """Delete multiple relations from the knowledge graph.
    
    Args:
        relations: List of relations to delete (must match exactly).
        
    Returns:
        Success message confirming deletion.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    await knowledge_graph_manager.delete_relations(relations)
    return "Relations deleted successfully"


@mcp.tool()
async def read_graph() -> KnowledgeGraph:
    """Read the entire knowledge graph.
    
    WARNING: This loads the entire graph into memory and may be slow for large graphs.
    Consider using search_nodes, get_subgraph, or get_graph_summary instead.
    
    Returns:
        The complete knowledge graph with all entities and relations.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.read_graph()


@mcp.tool()
async def get_graph_summary() -> Dict[str, Any]:
    """Get a summary of the knowledge graph without loading all data.
    
    Provides quick statistics about the graph size and sample entities
    without the memory overhead of loading the entire graph.
    
    Returns:
        Dictionary containing:
        - entity_count: Total number of entities in the graph
        - relation_count: Total number of relations in the graph
        - sample_entities: Names of up to 10 sample entities
        - recent_entities: Names of up to 10 recently added entities
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.get_graph_summary()


@mcp.tool()
async def search_nodes(query: str) -> KnowledgeGraph:
    """Search for nodes in the knowledge graph based on a query.
    
    Searches across entity names, types, and observation content.
    Returns matching entities along with connected entities and their relations.
    
    Args:
        query: The search query to match against entity names, types, and observations.
        
    Returns:
        A filtered knowledge graph containing matching entities and their connections.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.search_nodes(query)


@mcp.tool()
async def open_nodes(names: List[str]) -> KnowledgeGraph:
    """Open specific nodes in the knowledge graph by their names.
    
    Args:
        names: List of entity names to retrieve.
        
    Returns:
        A filtered knowledge graph containing the requested entities and their relations.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.open_nodes(names)


@mcp.tool()
async def get_subgraph(start_entity: str, max_depth: int = 2) -> KnowledgeGraph:
    """Get a subgraph starting from an entity up to a certain depth.
    
    Traverses the graph from a starting entity, including all entities
    and relations within the specified depth. Useful for exploring
    local graph neighborhoods and understanding entity connections.
    
    Args:
        start_entity: The name of the entity to start traversal from.
        max_depth: Maximum depth to traverse from the starting entity (default: 2).
        
    Returns:
        A knowledge graph containing all entities and relations within the specified depth.
        
    Raises:
        ValueError: If the start entity doesn't exist.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.get_subgraph(start_entity, max_depth)


@mcp.tool()
async def find_path(start_entity: str, end_entity: str, max_depth: int = 5) -> List[Entity]:
    """Find the shortest path between two entities in the knowledge graph.
    
    Uses breadth-first search to find the shortest path connecting two entities
    through their relations. Useful for understanding how entities are connected
    and discovering indirect relationships.
    
    Args:
        start_entity: The name of the starting entity.
        end_entity: The name of the target entity.
        max_depth: Maximum path length to search (default: 5).
        
    Returns:
        List of entities forming the shortest path from start to end.
        Returns empty list if no path exists within max_depth.
        
    Raises:
        ValueError: If either the start or end entity doesn't exist.
    """
    if not knowledge_graph_manager:
        raise RuntimeError("Knowledge graph manager not initialized")
    
    return await knowledge_graph_manager.find_path(start_entity, end_entity, max_depth)


def main():
    """Main entry point for the MCP server."""
    import asyncio
    
    # Initialize storage before starting the server
    async def setup():
        await initialize_storage()
    
    # Run the initialization
    asyncio.run(setup())
    
    # Let FastMCP handle everything including interrupts
    mcp.run()


if __name__ == "__main__":
    main()
