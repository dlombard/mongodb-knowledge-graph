"""Knowledge graph manager for handling all graph operations.

This module provides the KnowledgeGraphManager class which implements all
the business logic for managing entities, relations, and observations in
the knowledge graph.
"""

from __future__ import annotations

from typing import List, Dict, Any

from mcp_server_memory.storage.base import StorageAdapter
from mcp_server_memory.storage.mongodb_adapter import MongoDBStorageAdapter
from mcp_server_memory.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationRequest,
    ObservationResponse,
    Relation,
)


class KnowledgeGraphManager:
    """Manages all operations on the knowledge graph.
    
    This class provides high-level operations for creating, reading, updating,
    and deleting entities and relations in the knowledge graph. It uses a
    storage adapter for persistence.
    """

    def __init__(self, storage: StorageAdapter) -> None:
        """Initialize the knowledge graph manager.
        
        Args:
            storage: The storage adapter to use for persistence.
        """
        self.storage = storage

    async def _load_graph(self) -> KnowledgeGraph:
        """Load the current knowledge graph from storage.
        
        Returns:
            The current knowledge graph.
        """
        return await self.storage.load_graph()

    async def _save_graph(self, graph: KnowledgeGraph) -> None:
        """Save the knowledge graph to storage.
        
        Args:
            graph: The knowledge graph to save.
        """
        await self.storage.save_graph(graph)

    async def create_entities(self, entities: List[Entity]) -> List[Entity]:
        """Create new entities in the knowledge graph.
        
        Only creates entities that don't already exist (based on name).
        
        Args:
            entities: List of entities to create.
            
        Returns:
            List of entities that were actually created (excludes duplicates).
        """
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            return await self.storage.add_entities(entities)
        
        # Fallback to full graph load/save for other storage types
        graph = await self._load_graph()
        existing_names = {entity.name for entity in graph.entities}
        
        new_entities = [
            entity for entity in entities if entity.name not in existing_names
        ]
        
        graph.entities.extend(new_entities)
        await self._save_graph(graph)
        
        return new_entities

    async def create_relations(self, relations: List[Relation]) -> List[Relation]:
        """Create new relations in the knowledge graph.
        
        Only creates relations that don't already exist (based on from, to, and type).
        
        Args:
            relations: List of relations to create.
            
        Returns:
            List of relations that were actually created (excludes duplicates).
        """
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            return await self.storage.add_relations(relations)
        
        # Fallback to full graph load/save for other storage types
        graph = await self._load_graph()
        existing_relations = {
            (r.from_entity, r.to_entity, r.relation_type) for r in graph.relations
        }
        
        new_relations = [
            relation
            for relation in relations
            if (relation.from_entity, relation.to_entity, relation.relation_type)
            not in existing_relations
        ]
        
        graph.relations.extend(new_relations)
        await self._save_graph(graph)
        
        return new_relations

    async def add_observations(
        self, observation_requests: List[ObservationRequest]
    ) -> List[ObservationResponse]:
        """Add observations to existing entities.
        
        Args:
            observation_requests: List of observation addition requests.
            
        Returns:
            List of responses indicating which observations were added.
            
        Raises:
            ValueError: If any specified entity doesn't exist.
        """
        responses = []
        
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            for request in observation_requests:
                try:
                    # Get original entity before update
                    original_entity = await self.storage.get_entity(request.entity_name)
                    original_obs = set(original_entity.observations) if original_entity else set()
                    
                    # Update entity with new observations
                    await self.storage.add_observations(request.entity_name, request.contents)
                    
                    # Calculate which observations were actually added
                    new_observations = [obs for obs in request.contents if obs not in original_obs]
                    
                    responses.append(
                        ObservationResponse(
                            entity_name=request.entity_name,
                            added_observations=new_observations,
                        )
                    )
                except Exception as e:
                    raise ValueError(f"Entity with name {request.entity_name} not found") from e
            return responses
        
        # Fallback to full graph load/save for other storage types
        graph = await self._load_graph()
        entity_map = {entity.name: entity for entity in graph.entities}
        
        for request in observation_requests:
            entity = entity_map.get(request.entity_name)
            if not entity:
                raise ValueError(f"Entity with name {request.entity_name} not found")
            
            # Filter out observations that already exist
            new_observations = [
                obs for obs in request.contents if obs not in entity.observations
            ]
            
            entity.observations.extend(new_observations)
            responses.append(
                ObservationResponse(
                    entity_name=request.entity_name,
                    added_observations=new_observations,
                )
            )
        
        await self._save_graph(graph)
        return responses

    async def delete_entities(self, entity_names: List[str]) -> None:
        """Delete entities and their associated relations.
        
        Removes the specified entities and all relations that reference them.
        
        Args:
            entity_names: List of entity names to delete.
        """
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            await self.storage.bulk_delete_entities(entity_names)
            return
        
        # Fallback to full graph load/save for other storage types
        graph = await self._load_graph()
        entity_names_set = set(entity_names)
        
        # Remove entities
        graph.entities = [
            entity for entity in graph.entities if entity.name not in entity_names_set
        ]
        
        # Remove relations that reference deleted entities
        graph.relations = [
            relation
            for relation in graph.relations
            if (
                relation.from_entity not in entity_names_set
                and relation.to_entity not in entity_names_set
            )
        ]
        
        await self._save_graph(graph)

    async def delete_observations(
        self, deletions: List[ObservationDeletion]
    ) -> None:
        """Delete specific observations from entities.
        
        Args:
            deletions: List of observation deletion requests.
        """
        graph = await self._load_graph()
        entity_map = {entity.name: entity for entity in graph.entities}
        
        for deletion in deletions:
            entity = entity_map.get(deletion.entity_name)
            if entity:
                # Remove specified observations
                entity.observations = [
                    obs
                    for obs in entity.observations
                    if obs not in deletion.observations
                ]
        
        await self._save_graph(graph)

    async def delete_relations(self, relations: List[Relation]) -> None:
        """Delete specific relations from the knowledge graph.
        
        Args:
            relations: List of relations to delete.
        """
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            for relation in relations:
                await self.storage.delete_relation(
                    relation.from_entity, relation.to_entity, relation.relation_type
                )
            return
        
        # Fallback to full graph load/save for other storage types
        graph = await self._load_graph()
        relations_to_delete = {
            (r.from_entity, r.to_entity, r.relation_type) for r in relations
        }
        
        graph.relations = [
            relation
            for relation in graph.relations
            if (relation.from_entity, relation.to_entity, relation.relation_type)
            not in relations_to_delete
        ]
        
        await self._save_graph(graph)

    async def read_graph(self) -> KnowledgeGraph:
        """Read the entire knowledge graph.
        
        WARNING: This loads the entire graph into memory. For large graphs,
        consider using search_nodes, get_subgraph, or get_graph_summary instead.
        
        Returns:
            The complete knowledge graph.
        """
        return await self._load_graph()
    
    async def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the knowledge graph without loading all data.
        
        Returns:
            Dictionary containing:
            - entity_count: Total number of entities
            - relation_count: Total number of relations  
            - sample_entities: A few example entities (max 10)
            - recent_entities: Most recently added entities (max 10)
        """
        # Use MongoDB efficient operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            summary = {
                "entity_count": await self.storage.count_entities(),
                "relation_count": 0,  # Would need to add count_relations to adapter
                "sample_entities": [],
                "recent_entities": []
            }
            
            # Get sample entities
            sample = await self.storage.get_entities(skip=0, limit=10)
            summary["sample_entities"] = [e.name for e in sample]
            
            # For MongoDB, we could get recently added based on _id
            # For now, just return the sample
            summary["recent_entities"] = summary["sample_entities"]
            
            # Count relations
            if hasattr(self.storage, 'relations_collection') and self.storage.relations_collection is not None:
                summary["relation_count"] = self.storage.relations_collection.count_documents({})
            
            return summary
        
        # Fallback: load graph but return summary only
        graph = await self._load_graph()
        return {
            "entity_count": len(graph.entities),
            "relation_count": len(graph.relations),
            "sample_entities": [e.name for e in graph.entities[:10]],
            "recent_entities": [e.name for e in graph.entities[-10:]] if len(graph.entities) > 10 else [e.name for e in graph.entities]
        }

    async def search_nodes(self, query: str) -> KnowledgeGraph:
        """Search for nodes in the knowledge graph based on a query.
        
        Searches across entity names, types, and observations. Returns matching
        entities along with any connected entities and their relations.
        
        Args:
            query: The search query string.
            
        Returns:
            A filtered knowledge graph containing matching entities and their connections.
        """
        # Use efficient MongoDB search when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            # Search by name and observations
            name_matches = await self.storage.search_entities_by_name(query)
            obs_matches = await self.storage.search_entities_by_observation(query)
            
            # Combine and deduplicate
            all_matches = {}
            for entity in name_matches + obs_matches:
                all_matches[entity.name] = entity
            
            filtered_entities = list(all_matches.values())
            filtered_entity_names = set(all_matches.keys())
            
            # Get relations for matched entities
            all_relations = []
            connected_entity_names = set()
            
            for entity_name in filtered_entity_names:
                relations = await self.storage.get_entity_relations(entity_name)
                all_relations.extend(relations)
                
                # Track connected entities
                for relation in relations:
                    if relation.from_entity not in filtered_entity_names:
                        connected_entity_names.add(relation.from_entity)
                    if relation.to_entity not in filtered_entity_names:
                        connected_entity_names.add(relation.to_entity)
            
            # Get connected entities
            connected_entities = []
            for name in connected_entity_names:
                entity = await self.storage.get_entity(name)
                if entity:
                    connected_entities.append(entity)
            
            return KnowledgeGraph(
                entities=filtered_entities + connected_entities,
                relations=all_relations,
            )
        
        # Fallback to full graph load for other storage types
        graph = await self._load_graph()
        query_lower = query.lower()
        
        # Find entities that match the query
        filtered_entities = []
        for entity in graph.entities:
            if (
                query_lower in entity.name.lower()
                or query_lower in entity.entity_type.lower()
                or any(query_lower in obs.lower() for obs in entity.observations)
            ):
                filtered_entities.append(entity)
        
        filtered_entity_names = {entity.name for entity in filtered_entities}
        
        # Find relations involving the filtered entities
        filtered_relations = []
        connected_entity_names = set()
        
        for relation in graph.relations:
            if (
                relation.from_entity in filtered_entity_names
                or relation.to_entity in filtered_entity_names
            ):
                filtered_relations.append(relation)
                # Track connected entities
                if relation.from_entity not in filtered_entity_names:
                    connected_entity_names.add(relation.from_entity)
                if relation.to_entity not in filtered_entity_names:
                    connected_entity_names.add(relation.to_entity)
        
        # Add connected entities
        connected_entities = [
            entity
            for entity in graph.entities
            if entity.name in connected_entity_names
        ]
        
        return KnowledgeGraph(
            entities=filtered_entities + connected_entities,
            relations=filtered_relations,
        )

    async def open_nodes(self, names: List[str]) -> KnowledgeGraph:
        """Retrieve specific nodes by name along with their relations.
        
        Args:
            names: List of entity names to retrieve.
            
        Returns:
            A filtered knowledge graph containing the requested entities and their relations.
        """
        # Use efficient MongoDB operations when available
        if isinstance(self.storage, MongoDBStorageAdapter):
            # Get entities efficiently
            entities = []
            for name in names:
                entity = await self.storage.get_entity(name)
                if entity:
                    entities.append(entity)
            
            # Get relations between these entities
            relations = []
            names_set = set(names)
            for name in names:
                entity_relations = await self.storage.get_entity_relations(name)
                # Only include relations between requested entities
                for relation in entity_relations:
                    if (relation.from_entity in names_set and 
                        relation.to_entity in names_set):
                        relations.append(relation)
            
            # Remove duplicates
            unique_relations = []
            seen = set()
            for relation in relations:
                key = (relation.from_entity, relation.to_entity, relation.relation_type)
                if key not in seen:
                    seen.add(key)
                    unique_relations.append(relation)
            
            return KnowledgeGraph(entities=entities, relations=unique_relations)
        
        # Fallback to full graph load for other storage types
        graph = await self._load_graph()
        names_set = set(names)
        
        # Filter entities by requested names
        filtered_entities = [
            entity for entity in graph.entities if entity.name in names_set
        ]
        
        # Filter relations to only include those between requested entities
        filtered_relations = [
            relation
            for relation in graph.relations
            if (
                relation.from_entity in names_set and relation.to_entity in names_set
            )
        ]
        
        return KnowledgeGraph(
            entities=filtered_entities, relations=filtered_relations
        )

    async def get_subgraph(self, start_entity: str, max_depth: int = 2) -> KnowledgeGraph:
        """Get a subgraph starting from an entity up to a certain depth.
        
        Traverses the graph from a starting entity, including all entities
        and relations within the specified depth.
        
        Args:
            start_entity: The name of the entity to start from.
            max_depth: Maximum depth to traverse (default: 2).
            
        Returns:
            A knowledge graph containing the subgraph.
            
        Raises:
            ValueError: If the start entity doesn't exist.
        """
        # Use MongoDB's graph traversal if available
        if isinstance(self.storage, MongoDBStorageAdapter):
            return await self.storage.get_subgraph(start_entity, max_depth)
        
        # Fallback implementation for other storage types
        graph = await self._load_graph()
        entity_map = {e.name: e for e in graph.entities}
        
        if start_entity not in entity_map:
            raise ValueError(f"Entity '{start_entity}' not found")
        
        # BFS to find all entities within max_depth
        visited = {start_entity}
        current_level = {start_entity}
        all_entities = {start_entity}
        
        for depth in range(max_depth):
            next_level = set()
            for entity_name in current_level:
                # Find relations involving this entity
                for relation in graph.relations:
                    if relation.from_entity == entity_name:
                        if relation.to_entity not in visited:
                            next_level.add(relation.to_entity)
                            all_entities.add(relation.to_entity)
                    elif relation.to_entity == entity_name:
                        if relation.from_entity not in visited:
                            next_level.add(relation.from_entity)
                            all_entities.add(relation.from_entity)
            
            visited.update(next_level)
            current_level = next_level
            
            if not current_level:
                break
        
        # Collect entities and relations
        subgraph_entities = [e for e in graph.entities if e.name in all_entities]
        subgraph_relations = [
            r for r in graph.relations 
            if r.from_entity in all_entities and r.to_entity in all_entities
        ]
        
        return KnowledgeGraph(entities=subgraph_entities, relations=subgraph_relations)

    async def find_path(self, start_entity: str, end_entity: str, max_depth: int = 5) -> List[Entity]:
        """Find a path between two entities in the knowledge graph.
        
        Uses breadth-first search to find the shortest path between two entities.
        
        Args:
            start_entity: The name of the starting entity.
            end_entity: The name of the target entity.
            max_depth: Maximum path length to search (default: 5).
            
        Returns:
            List of entities forming the path from start to end.
            Returns empty list if no path is found.
            
        Raises:
            ValueError: If either entity doesn't exist.
        """
        # Use MongoDB's pathfinding if available
        if isinstance(self.storage, MongoDBStorageAdapter):
            result = await self.storage.find_path(start_entity, end_entity, max_depth)
            return result if result else []
        
        # Fallback implementation for other storage types
        graph = await self._load_graph()
        entity_map = {e.name: e for e in graph.entities}
        
        if start_entity not in entity_map:
            raise ValueError(f"Start entity '{start_entity}' not found")
        if end_entity not in entity_map:
            raise ValueError(f"End entity '{end_entity}' not found")
        
        if start_entity == end_entity:
            return [entity_map[start_entity]]
        
        # BFS to find shortest path
        visited = {start_entity}
        queue = [(start_entity, [start_entity])]
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            # Find neighbors
            neighbors = set()
            for relation in graph.relations:
                if relation.from_entity == current:
                    neighbors.add(relation.to_entity)
                elif relation.to_entity == current:
                    neighbors.add(relation.from_entity)
            
            for neighbor in neighbors:
                if neighbor == end_entity:
                    # Found the path
                    path_entities = path + [neighbor]
                    return [entity_map[name] for name in path_entities]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return []  # No path found