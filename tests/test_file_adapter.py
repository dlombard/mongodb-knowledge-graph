"""Tests for the file storage adapter."""

import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from mcp_server_memory.storage.file_adapter import FileStorageAdapter
from mcp_server_memory.types import Entity, KnowledgeGraph, Relation


class TestFileStorageAdapter:
    """Test cases for FileStorageAdapter."""

    @pytest_asyncio.fixture
    async def adapter(self):
        """Create a file storage adapter for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_memory.json"
            adapter = FileStorageAdapter({"file_path": str(file_path)})
            await adapter.initialize()
            yield adapter
            await adapter.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_directory(self):
        """Test that initialize creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nested" / "directory" / "test.json"
            adapter = FileStorageAdapter({"file_path": str(file_path)})
            
            await adapter.initialize()
            
            assert file_path.parent.exists()

    @pytest.mark.asyncio
    async def test_load_graph_empty_file(self, adapter):
        """Test loading an empty graph when file doesn't exist."""
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
        
        # Check entities
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
    async def test_save_empty_graph(self, adapter):
        """Test saving an empty graph."""
        empty_graph = KnowledgeGraph()
        
        await adapter.save_graph(empty_graph)
        loaded_graph = await adapter.load_graph()
        
        assert loaded_graph.entities == []
        assert loaded_graph.relations == []

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
    async def test_handle_empty_lines(self, adapter):
        """Test that empty lines in files are handled correctly."""
        # Manually create file with empty lines
        test_data = [
            json.dumps({"type": "entity", "name": "Alice", "entity_type": "person", "observations": []}),
            "",
            "   ",  # whitespace only
            json.dumps({"type": "entity", "name": "Bob", "entity_type": "person", "observations": []}),
        ]
        
        file_path = Path(adapter.config["file_path"])
        file_path.write_text("\n".join(test_data), encoding="utf-8")
        
        graph = await adapter.load_graph()
        
        assert len(graph.entities) == 2
        assert len(graph.relations) == 0

    @pytest.mark.asyncio
    async def test_round_trip_consistency(self, adapter):
        """Test that data survives multiple save/load cycles unchanged."""
        original_graph = KnowledgeGraph(
            entities=[
                Entity(
                    name="Complex Entity",
                    entity_type="test",
                    observations=["obs 1", "obs 2", "obs with unicode: 🚀"],
                ),
            ],
            relations=[
                Relation(
                    from_entity="Complex Entity",
                    to_entity="Complex Entity",
                    relation_type="self_reference",
                ),
            ],
        )
        
        # Multiple save/load cycles
        for _ in range(3):
            await adapter.save_graph(original_graph)
            loaded_graph = await adapter.load_graph()
            
            # Verify data integrity
            assert len(loaded_graph.entities) == 1
            assert len(loaded_graph.relations) == 1
            
            entity = loaded_graph.entities[0]
            assert entity.name == "Complex Entity"
            assert entity.entity_type == "test"
            assert entity.observations == ["obs 1", "obs 2", "obs with unicode: 🚀"]
            
            relation = loaded_graph.relations[0]
            assert relation.from_entity == "Complex Entity"
            assert relation.to_entity == "Complex Entity"
            assert relation.relation_type == "self_reference"