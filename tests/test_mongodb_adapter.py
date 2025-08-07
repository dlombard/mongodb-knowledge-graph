"""Tests for the MongoDB storage adapter."""

import os

import pytest
import pytest_asyncio

from mongodb_knowledge_graph.models import Entity, KnowledgeGraph, Relation

# Skip all tests if pymongo is not available
pymongo = pytest.importorskip("pymongo")

from mongodb_knowledge_graph.storage.mongodb_adapter import MongoDBStorageAdapter


@pytest.mark.skipif(
    not os.environ.get("TEST_MONGODB", "").lower() in ("1", "true"),
    reason="MongoDB tests require TEST_MONGODB=1 environment variable and running MongoDB instance",
)
class TestMongoDBStorageAdapter:
    """Test cases for MongoDBStorageAdapter."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a MongoDB storage adapter for testing."""
        config = {
            "uri": "mongodb://localhost:27017",
            "database": "mcp_memory_test",
            "collection_prefix": "test_",
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
    async def test_initialize_connection(self):
        """Test that initialization connects to MongoDB successfully."""
        config = {
            "uri": "mongodb://localhost:27017",
            "database": "mcp_memory_test",
            "collection_prefix": "init_test_",
        }
        
        adapter = MongoDBStorageAdapter(config)
        await adapter.initialize()
        
        assert adapter.client is not None
        assert adapter.database is not None
        assert adapter.entities_collection is not None
        assert adapter.relations_collection is not None
        
        await adapter.close()

    @pytest.mark.asyncio
    async def test_load_empty_graph(self, adapter):
        """Test loading an empty graph from MongoDB."""
        graph = await adapter.load_graph()
        
        assert isinstance(graph, KnowledgeGraph)
        assert graph.entities == []
        assert graph.relations == []

    @pytest.mark.asyncio
    async def test_save_and_load_graph(self, adapter):
        """Test saving and loading a complete graph."""
        original_graph = KnowledgeGraph(
            entities=[
                Entity(name="Alice", entity_type="person", observations=["smart", "tall"]),
                Entity(name="Bob", entity_type="person", observations=["funny"]),
            ],
            relations=[
                Relation(from_entity="Alice", to_entity="Bob", relation_type="knows"),
            ],
        )
        
        await adapter.save_graph(original_graph)
        loaded_graph = await adapter.load_graph()
        
        assert len(loaded_graph.entities) == 2
        assert len(loaded_graph.relations) == 1
        
        # Check entities (order might be different)
        entity_names = {e.name for e in loaded_graph.entities}
        assert entity_names == {"Alice", "Bob"}
        
        alice = next(e for e in loaded_graph.entities if e.name == "Alice")
        assert alice.entity_type == "person"
        assert alice.observations == ["smart", "tall"]
        
        bob = next(e for e in loaded_graph.entities if e.name == "Bob")
        assert bob.entity_type == "person"
        assert bob.observations == ["funny"]
        
        # Check relation
        relation = loaded_graph.relations[0]
        assert relation.from_entity == "Alice"
        assert relation.to_entity == "Bob"
        assert relation.relation_type == "knows"

    @pytest.mark.asyncio
    async def test_overwrite_existing_graph(self, adapter):
        """Test that saving overwrites existing data."""
        # Save initial graph
        initial_graph = KnowledgeGraph(
            entities=[Entity(name="Old", entity_type="test", observations=[])],
            relations=[],
        )
        await adapter.save_graph(initial_graph)
        
        # Save new graph
        new_graph = KnowledgeGraph(
            entities=[Entity(name="New", entity_type="test", observations=[])],
            relations=[],
        )
        await adapter.save_graph(new_graph)
        
        # Verify only new data exists
        loaded_graph = await adapter.load_graph()
        assert len(loaded_graph.entities) == 1
        assert loaded_graph.entities[0].name == "New"

    @pytest.mark.asyncio
    async def test_duplicate_entity_names(self, adapter):
        """Test behavior with duplicate entity names."""
        # MongoDB should handle this by using name as _id
        graph = KnowledgeGraph(
            entities=[Entity(name="Duplicate", entity_type="type1", observations=["first"])],
            relations=[],
        )
        
        await adapter.save_graph(graph)
        
        # Save again - should succeed as collections are cleared first
        await adapter.save_graph(graph)
        
        loaded_graph = await adapter.load_graph()
        assert len(loaded_graph.entities) == 1
        assert loaded_graph.entities[0].entity_type == "type1"

    @pytest.mark.asyncio
    async def test_complex_graph_with_multiple_relations(self, adapter):
        """Test handling complex graphs with multiple relations."""
        complex_graph = KnowledgeGraph(
            entities=[
                Entity(name="Company", entity_type="organization", observations=["Fortune 500"]),
                Entity(name="CEO", entity_type="person", observations=["experienced"]),
                Entity(name="CTO", entity_type="person", observations=["technical"]),
                Entity(name="Product", entity_type="product", observations=["innovative"]),
            ],
            relations=[
                Relation(from_entity="CEO", to_entity="Company", relation_type="leads"),
                Relation(from_entity="CTO", to_entity="Company", relation_type="works_at"),
                Relation(from_entity="Company", to_entity="Product", relation_type="produces"),
                Relation(from_entity="CEO", to_entity="CTO", relation_type="manages"),
            ],
        )
        
        await adapter.save_graph(complex_graph)
        loaded_graph = await adapter.load_graph()
        
        assert len(loaded_graph.entities) == 4
        assert len(loaded_graph.relations) == 4
        
        # Verify all entities exist
        entity_names = {e.name for e in loaded_graph.entities}
        assert entity_names == {"Company", "CEO", "CTO", "Product"}
        
        # Verify all relations exist
        relation_tuples = {
            (r.from_entity, r.to_entity, r.relation_type) for r in loaded_graph.relations
        }
        expected_relations = {
            ("CEO", "Company", "leads"),
            ("CTO", "Company", "works_at"),
            ("Company", "Product", "produces"),
            ("CEO", "CTO", "manages"),
        }
        assert relation_tuples == expected_relations

    @pytest.mark.asyncio
    async def test_collection_prefix(self):
        """Test that collection prefix is used correctly."""
        config = {
            "uri": "mongodb://localhost:27017",
            "database": "mcp_memory_test",
            "collection_prefix": "custom_prefix_",
        }
        
        adapter = MongoDBStorageAdapter(config)
        await adapter.initialize()
        
        graph = KnowledgeGraph(
            entities=[Entity(name="Test", entity_type="test", observations=[])],
            relations=[],
        )
        
        await adapter.save_graph(graph)
        
        # Verify collections were created with prefix
        collection_names = adapter.database.list_collection_names()
        assert "custom_prefix_entities" in collection_names
        assert "custom_prefix_relations" in collection_names
        
        await adapter.close()

    @pytest.mark.asyncio
    async def test_round_trip_consistency(self, adapter):
        """Test that data survives multiple save/load cycles unchanged."""
        original_graph = KnowledgeGraph(
            entities=[
                Entity(
                    name="Alice",
                    entity_type="person",
                    observations=["smart", "kind", "works at Acme Corp"],
                ),
                Entity(name="Bob", entity_type="person", observations=[]),
                Entity(name="Acme Corp", entity_type="company", observations=["tech", "startup"]),
            ],
            relations=[
                Relation(from_entity="Alice", to_entity="Acme Corp", relation_type="works_at"),
                Relation(from_entity="Bob", to_entity="Acme Corp", relation_type="works_at"),
                Relation(from_entity="Alice", to_entity="Bob", relation_type="manages"),
            ],
        )
        
        # Multiple save/load cycles
        for i in range(3):
            await adapter.save_graph(original_graph)
            loaded_graph = await adapter.load_graph()
            
            # Verify data integrity
            assert len(loaded_graph.entities) == 3
            assert len(loaded_graph.relations) == 3
            
            # Check that all original entities are present
            loaded_entity_names = {e.name for e in loaded_graph.entities}
            original_entity_names = {e.name for e in original_graph.entities}
            assert loaded_entity_names == original_entity_names
            
            # Check that all original relations are present
            loaded_relations = {
                (r.from_entity, r.to_entity, r.relation_type) for r in loaded_graph.relations
            }
            original_relations = {
                (r.from_entity, r.to_entity, r.relation_type) for r in original_graph.relations
            }
            assert loaded_relations == original_relations