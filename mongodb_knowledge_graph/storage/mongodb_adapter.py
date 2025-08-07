"""MongoDB storage adapter implementation.

This module provides a storage adapter that uses MongoDB to store the knowledge
graph. Entities and relations are stored in separate collections with appropriate
indexes for performance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
import logging

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
    from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError
    from pymongo.results import InsertManyResult, DeleteResult
except ImportError as e:
    raise ImportError(
        "PyMongo is required for MongoDB storage. Install with: pip install pymongo"
    ) from e

from mongodb_knowledge_graph.storage.base import StorageAdapter, StorageError
from mongodb_knowledge_graph.models import Entity, KnowledgeGraph, Relation


class MongoDBStorageAdapter(StorageAdapter):
    """MongoDB storage adapter for the knowledge graph.
    
    This adapter stores entities and relations in separate MongoDB collections
    with appropriate indexes for performance. Each entity uses its name as the
    document ID, and relations use a composite ID.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the MongoDB storage adapter.
        
        Args:
            config: Configuration dictionary containing MongoDB settings.
        """
        super().__init__(config)
        self.uri = config["uri"]
        self.database_name = config["database"]
        self.collection_prefix = config.get("collection_prefix", "")
        
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.entities_collection: Optional[Collection] = None
        self.relations_collection: Optional[Collection] = None

    async def initialize(self) -> None:
        """Initialize the MongoDB connection and collections.
        
        Creates the database connection, sets up collections, and creates
        appropriate indexes for performance.
        
        Raises:
            StorageError: If connection or initialization fails.
        """
        try:
            self.client = MongoClient(self.uri)
            
            # Test the connection
            self.client.admin.command("ping")
            
            self.database = self.client[self.database_name]
            
            entities_name = f"{self.collection_prefix}entities"
            relations_name = f"{self.collection_prefix}relations"
            
            self.entities_collection = self.database[entities_name]
            self.relations_collection = self.database[relations_name]
            
            # Create indexes for better performance
            # Entity name is already the _id, so no additional index needed
            self.entities_collection.create_index([("name", 1)], unique=True)
            # Create compound index for relations to ensure uniqueness
            # and improve query performance
            self.relations_collection.create_index(
                [("from", 1), ("to", 1), ("relationType", 1)], unique=True
            )
            
        except ConnectionFailure as e:
            raise StorageError(f"Failed to connect to MongoDB: {e}") from e
        except PyMongoError as e:
            raise StorageError(f"MongoDB initialization error: {e}") from e

    # Incremental Entity Operations
    
    async def add_entity(self, entity: Entity) -> Entity:
        """Add a single entity to the database.
        
        Args:
            entity: The entity to add.
            
        Returns:
            The added entity.
            
        Raises:
            StorageError: If the entity already exists or operation fails.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            doc = entity.model_dump(by_alias=True)
            #doc["_id"] = entity.name  # Use name as unique ID
            self.entities_collection.insert_one(doc)
            return entity
        except DuplicateKeyError:
            raise StorageError(f"Entity with name '{entity.name}' already exists")
        except PyMongoError as e:
            raise StorageError(f"Failed to add entity: {e}") from e
    
    async def add_entities(self, entities: List[Entity]) -> List[Entity]:
        """Add multiple entities in batch.
        
        Args:
            entities: List of entities to add.
            
        Returns:
            List of successfully added entities.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        if not entities:
            return []
        
        try:
            docs = []
            for entity in entities:
                doc = entity.model_dump(by_alias=True)
                #doc["_id"] = entity.name
                docs.append(doc)
            
            # Use ordered=False to continue on duplicate errors
            result = self.entities_collection.insert_many(docs, ordered=False)
            
            # Return only successfully inserted entities
            inserted_names = set(result.inserted_ids)
            return [e for e in entities if e.name in inserted_names]
        except PyMongoError as e:
            # Even with errors, some might have been inserted
            if hasattr(e, 'details') and e.details:
                # Extract successfully inserted
                inserted_names = set()
                for doc in docs:
                    if self.entities_collection.find_one({"_id": doc["_id"]}):
                        inserted_names.add(doc["_id"])
                return [e for e in entities if e.name in inserted_names]
            return []
    
    # TODO: Implement bulk operations for efficiency
    async def bulk_add_entities(self, entities: List[Entity]) -> InsertManyResult:
        """Bulk add entities for maximum efficiency.
        
        Args:
            entities: List of entities to add.
            
        Returns:
            MongoDB InsertManyResult.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            docs = []
            for entity in entities:
                doc = entity.model_dump(by_alias=True)
                doc["_id"] = entity.name
                docs.append(doc)
            
            return self.entities_collection.insert_many(docs, ordered=False)
        except PyMongoError as e:
            raise StorageError(f"Bulk add failed: {e}") from e
    
    async def get_entity(self, name: str) -> Optional[Entity]:
        """Get a single entity by name.
        
        Args:
            name: The entity name.
            
        Returns:
            The entity if found, None otherwise.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            doc = self.entities_collection.find_one({"name": name}, {"_id": 0})
            if doc:
                return Entity(**doc)
            return None
        except PyMongoError as e:
            raise StorageError(f"Failed to get entity: {e}") from e
    
    async def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Get a single entity by MongoDB ObjectId.
        
        Args:
            entity_id: The MongoDB ObjectId as string.
            
        Returns:
            The entity if found, None otherwise.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            from bson import ObjectId
            doc = self.entities_collection.find_one({"_id": ObjectId(entity_id)})
            if doc:
                doc.pop("_id", None)  # Remove _id from result
                return Entity(**doc)
            return None
        except Exception as e:
            raise StorageError(f"Failed to get entity by ID: {e}") from e
    
    async def get_entity_id(self, name: str) -> Optional[str]:
        """Get the MongoDB ObjectId for an entity by name.
        
        Args:
            name: The entity name.
            
        Returns:
            The ObjectId as string if found, None otherwise.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            doc = self.entities_collection.find_one({"name": name}, {"_id": 1})
            if doc:
                return str(doc["_id"])
            return None
        except PyMongoError as e:
            raise StorageError(f"Failed to get entity ID: {e}") from e
    
    async def get_entities(self, skip: int = 0, limit: int = 100) -> List[Entity]:
        """Get entities with pagination.
        
        Args:
            skip: Number of entities to skip.
            limit: Maximum number of entities to return.
            
        Returns:
            List of entities.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            cursor = self.entities_collection.find({}, {"_id": 0}).skip(skip).limit(limit)
            entities = []
            for doc in cursor:
                entities.append(Entity(**doc))
            return entities
        except PyMongoError as e:
            raise StorageError(f"Failed to get entities: {e}") from e
    
    async def entity_exists(self, name: str) -> bool:
        """Check if an entity exists.
        
        Args:
            name: The entity name.
            
        Returns:
            True if entity exists, False otherwise.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            return self.entities_collection.count_documents({"name": name}, limit=1) > 0
        except PyMongoError as e:
            raise StorageError(f"Failed to check entity existence: {e}") from e
    
    async def count_entities(self) -> int:
        """Count total number of entities.
        
        Returns:
            The total count of entities.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            return self.entities_collection.count_documents({})
        except PyMongoError as e:
            raise StorageError(f"Failed to count entities: {e}") from e
    
    async def upsert_entity(self, entity: Entity) -> bool:
        """Insert or update an entity.
        
        Args:
            entity: The entity to upsert.
            
        Returns:
            True if created, False if updated.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            doc = entity.model_dump(by_alias=True)
            result = self.entities_collection.replace_one(
                {"name": entity.name},
                doc,
                upsert=True
            )
            return result.upserted_id is not None
        except PyMongoError as e:
            raise StorageError(f"Failed to upsert entity: {e}") from e
    
    async def add_observations(self, entity_name: str, observations: List[str]) -> Entity:
        """Add observations to an entity.
        
        Args:
            entity_name: The entity name.
            observations: List of new observations to add.
            
        Returns:
            The updated entity.
            
        Raises:
            StorageError: If entity doesn't exist or operation fails.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            # Add unique observations only
            result = self.entities_collection.find_one_and_update(
                {"name": entity_name},
                {"$addToSet": {"observations": {"$each": observations}}},
                {"_id": 0},  # Exclude _id from result
                return_document=True
            )
            
            if not result:
                raise StorageError(f"Entity '{entity_name}' not found")
            
            return Entity(**result)
        except PyMongoError as e:
            raise StorageError(f"Failed to add observations: {e}") from e
    
    async def remove_observations(self, entity_name: str, observations: List[str]) -> Entity:
        """Remove observations from an entity.
        
        Args:
            entity_name: The entity name.
            observations: List of observations to remove.
            
        Returns:
            The updated entity.
            
        Raises:
            StorageError: If entity doesn't exist or operation fails.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            result = self.entities_collection.find_one_and_update(
                {"name": entity_name},
                {"$pull": {"observations": {"$in": observations}}},
                {"_id": 0},  # Exclude _id from result
                return_document=True
            )
            
            if not result:
                raise StorageError(f"Entity '{entity_name}' not found")
            
            result.pop("_id", None)
            return Entity(**result)
        except PyMongoError as e:
            raise StorageError(f"Failed to remove observations: {e}") from e
    
    async def delete_entity(self, name: str) -> bool:
        """Delete a single entity and its relations.
        
        Args:
            name: The entity name.
            
        Returns:
            True if deleted, False if not found.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            # Delete entity
            result = self.entities_collection.delete_one({"name": name})
            
            # Delete all relations involving this entity
            self.relations_collection.delete_many({
                "$or": [{"from": name}, {"to": name}]
            })
            
            return result.deleted_count > 0
        except PyMongoError as e:
            raise StorageError(f"Failed to delete entity: {e}") from e
    
    async def bulk_delete_entities(self, names: List[str]) -> DeleteResult:
        """Bulk delete entities.
        
        Args:
            names: List of entity names to delete.
            
        Returns:
            MongoDB DeleteResult.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            # Delete entities
            result = self.entities_collection.delete_many({"name": {"$in": names}})
            
            # Delete related relations
            self.relations_collection.delete_many({
                "$or": [{"from": {"$in": names}}, {"to": {"$in": names}}]
            })
            
            return result
        except PyMongoError as e:
            raise StorageError(f"Bulk delete failed: {e}") from e
    
    # Incremental Relation Operations
    
    async def add_relation(self, relation: Relation) -> Relation:
        """Add a single relation.
        
        Args:
            relation: The relation to add.
            
        Returns:
            The added relation.
            
        Raises:
            StorageError: If relation already exists or operation fails.
        """
        if self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            doc = relation.model_dump(by_alias=True)
            # Create composite ID
            doc["_id"] = f"{relation.from_entity}_{relation.to_entity}_{relation.relation_type}"
            self.relations_collection.insert_one(doc)
            return relation
        except DuplicateKeyError:
            raise StorageError(f"Relation already exists")
        except PyMongoError as e:
            raise StorageError(f"Failed to add relation: {e}") from e
    
    async def add_relations(self, relations: List[Relation]) -> List[Relation]:
        """Add multiple relations in batch.
        
        Args:
            relations: List of relations to add.
            
        Returns:
            List of successfully added relations.
        """
        if self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        if not relations:
            return []
        
        try:
            docs = []
            for relation in relations:
                doc = relation.model_dump(by_alias=True)
                doc["_id"] = f"{relation.from_entity}_{relation.to_entity}_{relation.relation_type}"
                docs.append(doc)
            
            result = self.relations_collection.insert_many(docs, ordered=False)
            
            # Return successfully inserted
            inserted_ids = set(result.inserted_ids)
            return [
                r for r in relations 
                if f"{r.from_entity}_{r.to_entity}_{r.relation_type}" in inserted_ids
            ]
        except PyMongoError:
            # Return what was successfully inserted
            inserted = []
            for relation in relations:
                _id = f"{relation.from_entity}_{relation.to_entity}_{relation.relation_type}"
                if self.relations_collection.find_one({"_id": _id}):
                    inserted.append(relation)
            return inserted
    
    async def relation_exists(self, from_entity: str, to_entity: str, relation_type: str) -> bool:
        """Check if a relation exists.
        
        Args:
            from_entity: Source entity name.
            to_entity: Target entity name.
            relation_type: Type of relation.
            
        Returns:
            True if relation exists, False otherwise.
        """
        if self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            _id = f"{from_entity}_{to_entity}_{relation_type}"
            return self.relations_collection.count_documents({"_id": _id}, limit=1) > 0
        except PyMongoError as e:
            raise StorageError(f"Failed to check relation existence: {e}") from e
    
    async def delete_relation(self, from_entity: str, to_entity: str, relation_type: str) -> bool:
        """Delete a specific relation.
        
        Args:
            from_entity: Source entity name.
            to_entity: Target entity name.
            relation_type: Type of relation.
            
        Returns:
            True if deleted, False if not found.
        """
        if self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            _id = f"{from_entity}_{to_entity}_{relation_type}"
            result = self.relations_collection.delete_one({"_id": _id})
            return result.deleted_count > 0
        except PyMongoError as e:
            raise StorageError(f"Failed to delete relation: {e}") from e
    
    async def get_entity_relations(
        self, 
        entity_name: str, 
        direction: Literal["both", "incoming", "outgoing"] = "both"
    ) -> List[Relation]:
        """Get all relations for an entity.
        
        Args:
            entity_name: The entity name.
            direction: Filter by relation direction.
            
        Returns:
            List of relations.
        """
        if self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            if direction == "outgoing":
                query = {"from": entity_name}
            elif direction == "incoming":
                query = {"to": entity_name}
            else:  # both
                query = {"$or": [{"from": entity_name}, {"to": entity_name}]}
            
            cursor = self.relations_collection.find(query)
            relations = []
            for doc in cursor:
                doc.pop("_id", None)
                relations.append(Relation(**doc))
            return relations
        except PyMongoError as e:
            raise StorageError(f"Failed to get entity relations: {e}") from e
    
    # Search Operations
    
    async def search_entities_by_name(self, pattern: str) -> List[Entity]:
        """Search entities by name pattern.
        
        Args:
            pattern: Search pattern (case-insensitive).
            
        Returns:
            List of matching entities.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            query = {"name": {"$regex": pattern, "$options": "i"}}
            cursor = self.entities_collection.find(query)
            entities = []
            for doc in cursor:
                doc.pop("_id", None)
                entities.append(Entity(**doc))
            return entities
        except PyMongoError as e:
            raise StorageError(f"Search failed: {e}") from e
    
    async def search_entities_by_observation(self, pattern: str) -> List[Entity]:
        """Search entities by observation content.
        
        Args:
            pattern: Search pattern (case-insensitive).
            
        Returns:
            List of matching entities.
        """
        if self.entities_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            query = {"observations": {"$regex": pattern, "$options": "i"}}
            cursor = self.entities_collection.find(query)
            entities = []
            for doc in cursor:
                doc.pop("_id", None)
                entities.append(Entity(**doc))
            return entities
        except PyMongoError as e:
            raise StorageError(f"Search failed: {e}") from e
    
    async def get_connected_entities(self, entity_name: str) -> List[Entity]:
        """Get all entities connected to a specific entity.
        
        Args:
            entity_name: The entity name.
            
        Returns:
            List of connected entities.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            logging.info("GET_CONNECTED_ENTITIES:")
            # Find all relations involving this entity
            relations = await self.get_entity_relations(entity_name)
            
            # Extract connected entity names
            connected_names = set()
            for relation in relations:
                if relation.from_entity == entity_name:
                    connected_names.add(relation.to_entity)
                else:
                    connected_names.add(relation.from_entity)
            
            # Fetch connected entities
            if not connected_names:
                return []

            cursor = self.entities_collection.find({"name": {"$in": list(connected_names)}}, {"_id": 0})
            entities = []
            for doc in cursor:
                entities.append(Entity(**doc))
            return entities
        except PyMongoError as e:
            raise StorageError(f"Failed to get connected entities: {e}") from e
    
    # Graph Traversal Operations
    
    async def get_subgraph(self, start_entity: str, max_depth: int = 2) -> KnowledgeGraph:
        """Get a subgraph starting from an entity using aggregation.
        
        Args:
            start_entity: Starting entity name.
            max_depth: Maximum traversal depth.
            
        Returns:
            KnowledgeGraph containing the subgraph.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            logging.info("GET_SUBGRAPH:")
            # Use $graphLookup for graph traversal
            relations_collection_name = f"{self.collection_prefix}relations"
            pipeline = [
                {"$match": {"name": start_entity}},
                {
                    "$graphLookup": {
                        "from": relations_collection_name,
                        "startWith": "$name",
                        "connectFromField": "name",
                        "connectToField": "from",
                        "as": "connected_relations",
                        "maxDepth": max_depth,
                        "depthField": "depth"
                    }
                },
                {"$project": {"_id": 0}}
            ]
            
            result = list(self.entities_collection.aggregate(pipeline))
            
            if not result:
                return KnowledgeGraph(entities=[], relations=[])
            
            # For now, use simpler BFS approach for correctness
            # MongoDB $graphLookup is powerful but needs more complex pipeline for bidirectional
            entity_names = {start_entity}
            visited = {start_entity}
            current_level = {start_entity}
            
            for depth in range(max_depth):
                next_level = set()
                # Find all relations at current level
                relations_out = list(self.relations_collection.find(
                    {"from": {"$in": list(current_level)}}, {"_id": 0}
                ))
                relations_in = list(self.relations_collection.find(
                    {"to": {"$in": list(current_level)}}, {"_id": 0}
                ))
                
                for rel in relations_out:
                    if rel["to"] not in visited:
                        next_level.add(rel["to"])
                        entity_names.add(rel["to"])
                
                for rel in relations_in:
                    if rel["from"] not in visited:
                        next_level.add(rel["from"])
                        entity_names.add(rel["from"])
                
                visited.update(next_level)
                current_level = next_level
                
                if not current_level:
                    break
            
            # Fetch all entities and relations in subgraph
            cursor = self.entities_collection.find({"name": {"$in": list(entity_names)}}, {"_id": 0})
            entities = []
            for doc in cursor:
                entities.append(Entity(**doc))
            
            # Get all relations between these entities
            relations_cursor = self.relations_collection.find({
                "$and": [
                    {"from": {"$in": list(entity_names)}},
                    {"to": {"$in": list(entity_names)}}
                ]
            }, {"_id": 0})
            
            relations = []
            for doc in relations_cursor:
                relations.append(Relation(**doc))
            
            return KnowledgeGraph(entities=entities, relations=relations)
        except PyMongoError as e:
            raise StorageError(f"Failed to get subgraph: {e}") from e
    
    async def find_path(self, start: str, end: str, max_depth: int = 5) -> Optional[List[Entity]]:
        """Find a path between two entities.
        
        Args:
            start: Starting entity name.
            end: Target entity name.
            max_depth: Maximum path length.
            
        Returns:
            List of entities forming the path, or None if no path exists.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")
        
        try:
            logging.info("FIND_PATH:")
            # Simple BFS implementation
            visited = {start}
            queue = [(start, [start])]
            
            while queue:
                current, path = queue.pop(0)
                
                if len(path) > max_depth:
                    continue
                
                if current == end:
                    # Fetch entities in path order
                    cursor = self.entities_collection.find({"name": {"$in": path}}, {"_id": 0})
                    entity_map = {}
                    for doc in cursor:
                        entity_map[doc["name"]] = Entity(**doc)
                    
                    return [entity_map[name] for name in path]
                
                # Get neighbors
                relations = await self.get_entity_relations(current, direction="outgoing")
                
                for relation in relations:
                    next_entity = relation.to_entity
                    if next_entity not in visited:
                        visited.add(next_entity)
                        queue.append((next_entity, path + [next_entity]))
            
            return None
        except PyMongoError as e:
            raise StorageError(f"Failed to find path: {e}") from e
    
    # Legacy methods for compatibility
    
    async def load_graph(self):
        """Load the complete knowledge graph from MongoDB.
        
        Retrieves all entities and relations from their respective collections
        and constructs a KnowledgeGraph object.
        
        Returns:
            The complete knowledge graph loaded from MongoDB.
            
        Raises:
            StorageError: If the connection is not initialized or loading fails.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")

        try:
            logging.info("LOAD_GRAPH:")
            # Load all entities
            entity_docs = list(self.entities_collection.find({}, {"_id": 0}))
            entities = []
            
            for doc in entity_docs:
                # Remove MongoDB _id and convert to Entity
                entities.append(Entity(**doc))

            # Load all relations
            relation_docs = list(self.relations_collection.find({}, {"_id": 0}))
            relations = []
            
            for doc in relation_docs:
                # Remove MongoDB _id and convert to Relation
                relations.append(Relation(**doc))

            return KnowledgeGraph(entities=entities, relations=relations)

        except PyMongoError as e:
            raise StorageError(f"Failed to load graph from MongoDB: {e}") from e

    async def save_graph(self, graph: KnowledgeGraph) -> None:
        """Save the complete knowledge graph to MongoDB.
        
        Replaces all existing entities and relations with the provided graph.
        This operation is performed atomically within the constraints of MongoDB.
        
        Args:
            graph: The knowledge graph to save.
            
        Raises:
            StorageError: If the connection is not initialized or saving fails.
        """
        if self.entities_collection is None or self.relations_collection is None:
            raise StorageError("MongoDB connection not initialized")

        try:
            logging.info("SAVE_GRAPH:")
            # Clear existing data
            self.entities_collection.delete_many({})
            self.relations_collection.delete_many({})

            # Insert entities
            if graph.entities:
                entity_docs = []
                for entity in graph.entities:
                    doc = entity.model_dump(by_alias=True)
                    #doc["_id"] = entity.name
                    entity_docs.append(doc)
                
                self.entities_collection.insert_many(entity_docs)

            # Insert relations
            if graph.relations:
                relation_docs = []
                for relation in graph.relations:
                    doc = relation.model_dump(by_alias=True)
                    # Create composite ID for uniqueness
                    #doc["_id"] = f"{relation.from_entity}_{relation.to_entity}_{relation.relation_type}"
                    relation_docs.append(doc)
                
                self.relations_collection.insert_many(relation_docs)

        except PyMongoError as e:
            raise StorageError(f"Failed to save graph to MongoDB: {e}") from e

    async def close(self) -> None:
        """Close the MongoDB connection and clean up resources."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self.entities_collection = None
            self.relations_collection = None