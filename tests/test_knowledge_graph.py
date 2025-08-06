"""Tests for the knowledge graph manager."""

from unittest.mock import AsyncMock

import pytest

from mcp_server_memory.knowledge_graph import KnowledgeGraphManager
from mcp_server_memory.storage.base import StorageAdapter
from mcp_server_memory.types import (
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationRequest,
    Relation,
)


class MockStorageAdapter(StorageAdapter):
    """Mock storage adapter for testing."""

    def __init__(self):
        """Initialize the mock storage adapter."""
        super().__init__({})
        self.graph = KnowledgeGraph()
        self.initialize_called = False
        self.close_called = False

    async def initialize(self):
        """Mock initialize method."""
        self.initialize_called = True

    async def load_graph(self):
        """Mock load_graph method."""
        # Return a deep copy to simulate real storage behavior
        return KnowledgeGraph(
            entities=[Entity.model_validate(e.model_dump()) for e in self.graph.entities],
            relations=[Relation.model_validate(r.model_dump()) for r in self.graph.relations],
        )

    async def save_graph(self, graph):
        """Mock save_graph method."""
        # Store a deep copy to simulate real storage behavior
        self.graph = KnowledgeGraph(
            entities=[Entity.model_validate(e.model_dump()) for e in graph.entities],
            relations=[Relation.model_validate(r.model_dump()) for r in graph.relations],
        )

    async def close(self):
        """Mock close method."""
        self.close_called = True


class TestKnowledgeGraphManager:
    """Test cases for KnowledgeGraphManager."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage adapter."""
        return MockStorageAdapter()

    @pytest.fixture
    def manager(self, mock_storage):
        """Create a knowledge graph manager with mock storage."""
        return KnowledgeGraphManager(mock_storage)

    @pytest.mark.asyncio
    async def test_create_entities(self, manager, mock_storage):
        """Test creating new entities."""
        entities = [
            Entity(name="Alice", entity_type="person", observations=["smart"]),
            Entity(name="Bob", entity_type="person", observations=["tall"]),
        ]

        result = await manager.create_entities(entities)

        assert len(result) == 2
        assert result == entities
        
        # Verify entities were saved
        graph = await mock_storage.load_graph()
        assert len(graph.entities) == 2

    @pytest.mark.asyncio
    async def test_create_entities_filters_duplicates(self, manager, mock_storage):
        """Test that creating entities filters out existing ones."""
        # Pre-populate with one entity
        existing_entity = Entity(name="Alice", entity_type="person", observations=["existing"])
        mock_storage.graph.entities.append(existing_entity)

        new_entities = [
            Entity(name="Alice", entity_type="person", observations=["duplicate"]),
            Entity(name="Bob", entity_type="person", observations=["new"]),
        ]

        result = await manager.create_entities(new_entities)

        # Only Bob should be created
        assert len(result) == 1
        assert result[0].name == "Bob"
        
        # Verify Alice wasn't modified
        graph = await mock_storage.load_graph()
        alice = next(e for e in graph.entities if e.name == "Alice")
        assert alice.observations == ["existing"]

    @pytest.mark.asyncio
    async def test_create_relations(self, manager, mock_storage):
        """Test creating new relations."""
        # Pre-populate with entities
        entities = [
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
        ]
        mock_storage.graph.entities.extend(entities)

        relations = [
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows"),
        ]

        result = await manager.create_relations(relations)

        assert len(result) == 1
        assert result == relations
        
        # Verify relations were saved
        graph = await mock_storage.load_graph()
        assert len(graph.relations) == 1

    @pytest.mark.asyncio
    async def test_create_relations_filters_duplicates(self, manager, mock_storage):
        """Test that creating relations filters out existing ones."""
        # Pre-populate with entities and one relation
        entities = [
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
            Entity(name="Charlie", entity_type="person", observations=[]),
        ]
        existing_relation = Relation(from_entity="Alice", to_entity="Bob", relation_type="knows")
        
        mock_storage.graph.entities.extend(entities)
        mock_storage.graph.relations.append(existing_relation)

        new_relations = [
            Relation(from_entity="Alice", to_entity="Bob", relation_type="knows"),  # duplicate
            Relation(from_entity="Bob", to_entity="Charlie", relation_type="knows"),  # new
        ]

        result = await manager.create_relations(new_relations)

        # Only the new relation should be created
        assert len(result) == 1
        assert result[0].from_entity == "Bob"
        assert result[0].to_entity == "Charlie"

    @pytest.mark.asyncio
    async def test_add_observations(self, manager, mock_storage):
        """Test adding observations to existing entities."""
        # Pre-populate with entities
        alice = Entity(name="Alice", entity_type="person", observations=["smart"])
        bob = Entity(name="Bob", entity_type="person", observations=[])
        mock_storage.graph.entities.extend([alice, bob])

        observation_requests = [
            ObservationRequest(entity_name="Alice", contents=["tall", "funny"]),
            ObservationRequest(entity_name="Bob", contents=["kind"]),
        ]

        responses = await manager.add_observations(observation_requests)

        assert len(responses) == 2
        assert responses[0].entity_name == "Alice"
        assert responses[0].added_observations == ["tall", "funny"]
        assert responses[1].entity_name == "Bob"
        assert responses[1].added_observations == ["kind"]

        # Verify observations were added
        graph = await mock_storage.load_graph()
        alice_updated = next(e for e in graph.entities if e.name == "Alice")
        assert alice_updated.observations == ["smart", "tall", "funny"]

    @pytest.mark.asyncio
    async def test_add_observations_filters_duplicates(self, manager, mock_storage):
        """Test that adding observations filters out existing ones."""
        # Pre-populate with entity
        alice = Entity(name="Alice", entity_type="person", observations=["smart"])
        mock_storage.graph.entities.append(alice)

        observation_requests = [
            ObservationRequest(entity_name="Alice", contents=["smart", "tall"]),  # smart is duplicate
        ]

        responses = await manager.add_observations(observation_requests)

        assert len(responses) == 1
        assert responses[0].added_observations == ["tall"]  # Only new observation

    @pytest.mark.asyncio
    async def test_add_observations_nonexistent_entity(self, manager):
        """Test that adding observations to nonexistent entity raises error."""
        observation_requests = [
            ObservationRequest(entity_name="NonExistent", contents=["test"]),
        ]

        with pytest.raises(ValueError, match="Entity with name NonExistent not found"):
            await manager.add_observations(observation_requests)

    @pytest.mark.asyncio
    async def test_delete_entities(self, manager, mock_storage):
        """Test deleting entities and their relations."""
        # Pre-populate with entities and relations
        entities = [
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="organization", observations=[]),
        ]
        relations = [
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Bob", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Alice", to_entity="Bob", relation_type="manages"),
        ]
        
        mock_storage.graph.entities.extend(entities)
        mock_storage.graph.relations.extend(relations)

        await manager.delete_entities(["Alice"])

        # Verify Alice is deleted
        graph = await mock_storage.load_graph()
        entity_names = {e.name for e in graph.entities}
        assert "Alice" not in entity_names
        assert "Bob" in entity_names
        assert "Company" in entity_names

        # Verify relations involving Alice are deleted
        assert len(graph.relations) == 1
        remaining_relation = graph.relations[0]
        assert remaining_relation.from_entity == "Bob"
        assert remaining_relation.to_entity == "Company"

    @pytest.mark.asyncio
    async def test_delete_observations(self, manager, mock_storage):
        """Test deleting specific observations."""
        # Pre-populate with entities
        alice = Entity(name="Alice", entity_type="person", observations=["smart", "tall", "funny"])
        bob = Entity(name="Bob", entity_type="person", observations=["kind"])
        mock_storage.graph.entities.extend([alice, bob])

        deletions = [
            ObservationDeletion(entity_name="Alice", observations=["tall", "funny"]),
        ]

        await manager.delete_observations(deletions)

        # Verify observations were deleted
        graph = await mock_storage.load_graph()
        alice_updated = next(e for e in graph.entities if e.name == "Alice")
        assert alice_updated.observations == ["smart"]

    @pytest.mark.asyncio
    async def test_delete_observations_nonexistent_entity(self, manager, mock_storage):
        """Test deleting observations from nonexistent entity (should be silent)."""
        deletions = [
            ObservationDeletion(entity_name="NonExistent", observations=["test"]),
        ]

        # Should not raise an error
        await manager.delete_observations(deletions)

    @pytest.mark.asyncio
    async def test_delete_relations(self, manager, mock_storage):
        """Test deleting specific relations."""
        # Pre-populate with relations
        relations = [
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Bob", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Alice", to_entity="Bob", relation_type="manages"),
        ]
        mock_storage.graph.relations.extend(relations)

        to_delete = [
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
        ]

        await manager.delete_relations(to_delete)

        # Verify specific relation was deleted
        graph = await mock_storage.load_graph()
        assert len(graph.relations) == 2
        
        remaining_relations = {
            (r.from_entity, r.to_entity, r.relation_type) for r in graph.relations
        }
        assert ("Alice", "Company", "works_at") not in remaining_relations

    @pytest.mark.asyncio
    async def test_search_nodes_by_name(self, manager, mock_storage):
        """Test searching nodes by name."""
        # Pre-populate with entities and relations
        entities = [
            Entity(name="Alice_Smith", entity_type="person", observations=["software engineer"]),
            Entity(name="Bob_Jones", entity_type="person", observations=["manager"]),
            Entity(name="Acme_Corp", entity_type="company", observations=["tech startup"]),
        ]
        relations = [
            Relation(from_entity="Alice_Smith", to_entity="Acme_Corp", relation_type="works_at"),
            Relation(from_entity="Bob_Jones", to_entity="Acme_Corp", relation_type="works_at"),
        ]
        
        mock_storage.graph.entities.extend(entities)
        mock_storage.graph.relations.extend(relations)

        result = await manager.search_nodes("Alice")

        # Should return Alice and connected Acme_Corp
        assert len(result.entities) == 2
        entity_names = {e.name for e in result.entities}
        assert "Alice_Smith" in entity_names
        assert "Acme_Corp" in entity_names
        
        # Should return the relation between them
        assert len(result.relations) == 1
        assert result.relations[0].from_entity == "Alice_Smith"

    @pytest.mark.asyncio
    async def test_search_nodes_by_observation(self, manager, mock_storage):
        """Test searching nodes by observation content."""
        # Pre-populate with entities and relations
        entities = [
            Entity(name="Alice", entity_type="person", observations=["loves coffee"]),
            Entity(name="Bob", entity_type="person", observations=["plays guitar"]),
            Entity(name="Company", entity_type="company", observations=["remote work"]),
        ]
        relations = [
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
        ]
        
        mock_storage.graph.entities.extend(entities)
        mock_storage.graph.relations.extend(relations)

        result = await manager.search_nodes("coffee")

        # Should return Alice and connected Company
        assert len(result.entities) == 2
        entity_names = {e.name for e in result.entities}
        assert "Alice" in entity_names
        assert "Company" in entity_names

    @pytest.mark.asyncio
    async def test_search_nodes_case_insensitive(self, manager, mock_storage):
        """Test that search is case insensitive."""
        alice = Entity(name="Alice", entity_type="person", observations=[])
        mock_storage.graph.entities.append(alice)

        result = await manager.search_nodes("ALICE")

        assert len(result.entities) == 1
        assert result.entities[0].name == "Alice"

    @pytest.mark.asyncio
    async def test_open_nodes(self, manager, mock_storage):
        """Test opening specific nodes by name."""
        # Pre-populate with entities and relations
        entities = [
            Entity(name="Alice", entity_type="person", observations=[]),
            Entity(name="Bob", entity_type="person", observations=[]),
            Entity(name="Company", entity_type="company", observations=[]),
        ]
        relations = [
            Relation(from_entity="Alice", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Bob", to_entity="Company", relation_type="works_at"),
            Relation(from_entity="Alice", to_entity="Bob", relation_type="manages"),
        ]
        
        mock_storage.graph.entities.extend(entities)
        mock_storage.graph.relations.extend(relations)

        result = await manager.open_nodes(["Alice", "Bob"])

        # Should return Alice and Bob
        assert len(result.entities) == 2
        entity_names = {e.name for e in result.entities}
        assert entity_names == {"Alice", "Bob"}

        # Should return only relations between Alice and Bob
        assert len(result.relations) == 1
        relation = result.relations[0]
        assert relation.from_entity == "Alice"
        assert relation.to_entity == "Bob"

    @pytest.mark.asyncio
    async def test_open_nodes_nonexistent(self, manager, mock_storage):
        """Test opening nonexistent nodes."""
        result = await manager.open_nodes(["NonExistent"])

        assert len(result.entities) == 0
        assert len(result.relations) == 0