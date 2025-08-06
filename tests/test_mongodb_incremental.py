"""Tests for incremental MongoDB operations."""

import os
from typing import List

import pytest
import pytest_asyncio

from mcp_server_memory.types import Entity, KnowledgeGraph, Relation

# Skip all tests if pymongo is not available
pymongo = pytest.importorskip("pymongo")

from mcp_server_memory.storage.mongodb_adapter import MongoDBStorageAdapter


@pytest.mark.skipif(
    not os.environ.get("TEST_MONGODB", "").lower() in ("1", "true"),
    reason="MongoDB tests require TEST_MONGODB=1 environment variable and running MongoDB instance",
)
class TestMongoDBIncrementalOperations:
    """Test cases for incremental MongoDB operations."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a MongoDB storage adapter for testing."""
        config = {
            "uri": "mongodb://localhost:27017",
            "database": "mcp_memory_test",
            "collection_prefix": "incremental_test_",
        }
        
        adapter = MongoDBStorageAdapter(config)
        await adapter.initialize()
        
        # Clean up any existing data
        await adapter.save_graph(KnowledgeGraph())
        
        yield adapter
        
        # Clean up after test
        await adapter.save_graph(KnowledgeGraph())
        await adapter.close()

    @pytest.mark.asyncio
    async def test_add_single_entity(self, adapter):
        """Test adding a single entity without loading entire graph."""
        entity = Entity(name="Alice", entity_type="person", observations=["smart"])
        
        added = await adapter.add_entity(entity)
        assert added == entity
        
        # Verify entity exists without loading full graph
        exists = await adapter.entity_exists("Alice")
        assert exists is True
        
        # Get single entity
        retrieved = await adapter.get_entity("Alice")
        assert retrieved.name == "Alice"
        assert retrieved.entity_type == "person"
        assert retrieved.observations == ["smart"]

    @pytest.mark.asyncio
    async def test_add_multiple_entities_batch(self, adapter):
        """Test batch adding entities efficiently."""
        entities = [
            Entity(name="Alice", entity_type="person", observations=["smart"]),
            Entity(name="Bob", entity_type="person", observations=["funny"]),
            Entity(name="Company", entity_type="organization", observations=["tech"]),
        ]
        
        added = await adapter.add_entities(entities)
        assert len(added) == 3
        
        # Verify count without loading all
        count = await adapter.count_entities()
        assert count == 3

    @pytest.mark.asyncio
    async def test_update_entity_observations(self, adapter):
        """Test updating entity observations without loading graph."""
        # Add initial entity
        entity = Entity(name="Alice", entity_type="person", observations=["smart"])
        await adapter.add_entity(entity)
        
        # Add new observations
        updated = await adapter.add_observations("Alice", ["kind", "tall"])
        assert set(updated.observations) == {"smart", "kind", "tall"}
        
        # Remove observations
        updated = await adapter.remove_observations("Alice", ["smart"])
        assert updated.observations == ["kind", "tall"]

    @pytest.mark.asyncio
    async def test_delete_single_entity(self, adapter):
        """Test deleting a single entity and its relations."""
        # Setup entities and relations
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
        ])
        await adapter.add_relation(
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows")
        )
        
        # Delete Alice
        deleted = await adapter.delete_entity("Alice")
        assert deleted is True
        
        # Verify Alice is gone
        exists = await adapter.entity_exists("Alice")
        assert exists is False
        
        # Verify relation is also gone
        relations = await adapter.get_entity_relations("Alice")
        assert len(relations) == 0

    @pytest.mark.asyncio
    async def test_add_single_relation(self, adapter):
        """Test adding a single relation."""
        # Setup entities
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
        ])
        
        # Add relation
        relation = Relation(from_entity="Alice", to_entity="Bob", relation_type="knows")
        added = await adapter.add_relation(relation)
        assert added == relation
        
        # Verify relation exists
        exists = await adapter.relation_exists("Alice", "Bob", "knows")
        assert exists is True

    @pytest.mark.asyncio
    async def test_delete_single_relation(self, adapter):
        """Test deleting a specific relation."""
        # Setup
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
        ])
        await adapter.add_relation(
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows")
        )
        
        # Delete relation
        deleted = await adapter.delete_relation("Alice", "Bob", "knows")
        assert deleted is True
        
        # Verify relation is gone
        exists = await adapter.relation_exists("Alice", "Bob", "knows")
        assert exists is False

    @pytest.mark.asyncio
    async def test_search_entities_by_name(self, adapter):
        """Test searching entities by name pattern."""
        # Setup test data
        await adapter.add_entities([
            Entity(name="Alice Smith", entity_type="person", observations=[]),
            Entity(name="Alice Jones", entity_type="person", observations=[]),
            Entity(name="Bob Smith", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="organization", observations=[]),
        ])
        
        # Search for "Alice"
        results = await adapter.search_entities_by_name("Alice")
        assert len(results) == 2
        assert all("Alice" in e.name for e in results)
        
        # Search for "Smith"
        results = await adapter.search_entities_by_name("Smith")
        assert len(results) == 2
        assert all("Smith" in e.name for e in results)

    @pytest.mark.asyncio
    async def test_search_entities_by_observation(self, adapter):
        """Test searching entities by observation content."""
        # Setup test data
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=["works at Google", "PhD"]),
            Entity(name="Bob", entity_type="person", observations=["works at Microsoft"]),
            Entity(name="Charlie", entity_type="person", observations=["works at Google"]),
        ])
        
        # Search for "Google"
        results = await adapter.search_entities_by_observation("Google")
        assert len(results) == 2
        names = {e.name for e in results}
        assert names == {"Alice", "Charlie"}

    @pytest.mark.asyncio
    async def test_get_entity_relations(self, adapter):
        """Test getting all relations for a specific entity."""
        # Setup complex graph
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
            Entity(name="Charlie", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="organization", observations=[]),
        ])
        
        await adapter.add_relations([
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows"),
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Bob", to_entity="Alice", relation_type="knows"),
            Relation(from_entity="Charlie", to_entity="Company", relation_type="works_at"),
        ])
        
        # Get Alice's relations
        relations = await adapter.get_entity_relations("Alice")
        assert len(relations) == 3  # 2 outgoing, 1 incoming
        
        # Get only outgoing relations
        outgoing = await adapter.get_entity_relations("Alice", direction="outgoing")
        assert len(outgoing) == 2
        assert all(r.from_entity == "Alice" for r in outgoing)
        
        # Get only incoming relations
        incoming = await adapter.get_entity_relations("Alice", direction="incoming")
        assert len(incoming) == 1
        assert incoming[0].to_entity == "Alice"

    @pytest.mark.asyncio
    async def test_get_connected_entities(self, adapter):
        """Test getting entities connected to a specific entity."""
        # Setup
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
            Entity(name="Charlie", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="organization", observations=[]),
        ])
        
        await adapter.add_relations([
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows"),
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Charlie", to_entity="Alice", relation_type="manages"),
        ])
        
        # Get entities connected to Alice
        connected = await adapter.get_connected_entities("Alice")
        names = {e.name for e in connected}
        assert names == {"Bob", "Company", "Charlie"}

    @pytest.mark.asyncio
    async def test_pagination(self, adapter):
        """Test pagination for large result sets."""
        # Add many entities
        entities = [
            Entity(name=f"Entity_{i}", entity_type="test", observations=[f"obs_{i}"])
            for i in range(100)
        ]
        await adapter.add_entities(entities)
        
        # Get first page
        page1 = await adapter.get_entities(skip=0, limit=10)
        assert len(page1) == 10
        
        # Get second page
        page2 = await adapter.get_entities(skip=10, limit=10)
        assert len(page2) == 10
        
        # Verify different entities
        page1_names = {e.name for e in page1}
        page2_names = {e.name for e in page2}
        assert page1_names.isdisjoint(page2_names)

    @pytest.mark.asyncio
    async def test_aggregation_pipeline_subgraph(self, adapter):
        """Test using aggregation pipeline to get subgraph."""
        # Setup hierarchical data
        await adapter.add_entities([
            Entity(name="CEO", entity_type="person", observations=[]),
            Entity(name="CTO", entity_type="person", observations=[]),
            Entity(name="Engineer1", entity_type="person", observations=[]),
            Entity(name="Engineer2", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="organization", observations=[]),
        ])
        
        await adapter.add_relations([
            Relation(from_entity="CEO", to_entity="Company", relation_type="leads"),
            Relation(from_entity="CTO", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="CTO", to_entity="Engineer1", relation_type="manages"),
            Relation(from_entity="CTO", to_entity="Engineer2", relation_type="manages"),
            Relation(from_entity="Engineer1", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Engineer2", to_entity="Company", relation_type="works_at"),
        ])
        
        # Get subgraph starting from CTO (depth 1)
        subgraph = await adapter.get_subgraph("CTO", max_depth=1)
        
        # Should include CTO and directly connected entities
        entity_names = {e.name for e in subgraph.entities}
        assert "CTO" in entity_names
        assert "Company" in entity_names
        assert "Engineer1" in entity_names
        assert "Engineer2" in entity_names
        
        # Should not include CEO (not directly connected)
        assert "CEO" not in entity_names

    @pytest.mark.asyncio
    async def test_find_path_between_entities(self, adapter):
        """Test finding path between two entities."""
        # Setup graph with path
        await adapter.add_entities([
            Entity(name="A", entity_type="node", observations=[]),
            Entity(name="B", entity_type="node", observations=[]),
            Entity(name="C", entity_type="node", observations=[]),
            Entity(name="D", entity_type="node", observations=[]),
        ])
        
        await adapter.add_relations([
            Relation(from_entity="A", to_entity="B", relation_type="connects"),
            Relation(from_entity="B", to_entity="C", relation_type="connects"),
            Relation(from_entity="C", to_entity="D", relation_type="connects"),
        ])
        
        # Find path from A to D
        path = await adapter.find_path("A", "D", max_depth=3)
        assert path is not None
        assert len(path) == 4  # A -> B -> C -> D
        assert path[0].name == "A"
        assert path[-1].name == "D"

    @pytest.mark.asyncio
    async def test_upsert_entity(self, adapter):
        """Test upsert operation for entities."""
        # Initial insert
        entity = Entity(name="Alice", entity_type="person", observations=["smart"])
        created = await adapter.upsert_entity(entity)
        assert created is True
        
        # Update existing
        entity.observations.append("tall")
        created = await adapter.upsert_entity(entity)
        assert created is False
        
        # Verify updated
        retrieved = await adapter.get_entity("Alice")
        assert "tall" in retrieved.observations

    @pytest.mark.asyncio
    async def test_bulk_operations(self, adapter):
        """Test bulk operations for efficiency."""
        # Bulk insert entities
        entities = [
            Entity(name=f"Entity_{i}", entity_type="test", observations=[])
            for i in range(1000)
        ]
        
        result = await adapter.bulk_add_entities(entities)
        assert result.inserted_count == 1000
        
        # Bulk delete
        names_to_delete = [f"Entity_{i}" for i in range(500)]
        result = await adapter.bulk_delete_entities(names_to_delete)
        assert result.deleted_count == 500
        
        # Verify count
        count = await adapter.count_entities()
        assert count == 500

    @pytest.mark.asyncio
    async def test_text_search_with_index(self, adapter):
        """Test text search using MongoDB text index."""
        # Create text index on observations
        await adapter.create_text_index()
        
        # Add test data
        await adapter.add_entities([
            Entity(name="Alice", entity_type="person", 
                  observations=["expert in machine learning", "PhD in AI"]),
            Entity(name="Bob", entity_type="person", 
                  observations=["software engineer", "backend developer"]),
            Entity(name="Charlie", entity_type="person", 
                  observations=["machine learning engineer", "Python expert"]),
        ])
        
        # Search for "machine learning"
        results = await adapter.text_search("machine learning")
        assert len(results) == 2
        names = {e.name for e in results}
        assert names == {"Alice", "Charlie"}
        
        # Results should be ranked by relevance
        assert results[0].name in ["Alice", "Charlie"]