# MongoDB Knowledge Graph MCP Server

A high-performance Python implementation of a Model Context Protocol (MCP) server that provides persistent memory for Claude through an optimized MongoDB-based knowledge graph storage system.

## Overview

This MCP server enables Claude to create, manage, and recall information using a structured knowledge graph stored efficiently in MongoDB. It features advanced graph traversal capabilities, incremental operations, and is optimized for large-scale knowledge graphs without loading entire datasets into memory.

## Features

### 🚀 **Performance Optimized**
- **Incremental Operations**: Add, update, delete entities and relations without loading the entire graph
- **Efficient Search**: MongoDB-powered regex and text search with indexing
- **Graph Traversal**: Advanced subgraph exploration and pathfinding algorithms
- **Memory Efficient**: Statistics and summaries without full graph loading
- **Scalable**: Handles thousands of entities and relations efficiently

### 🧠 **Knowledge Graph Management**
- **Entity Operations**: Create, read, update, and delete entities with rich metadata
- **Relationship Mapping**: Define and query directional relationships between entities
- **Observation Tracking**: Associate multiple observations with entities
- **Graph Analytics**: Find paths between entities, explore neighborhoods
- **Search Capabilities**: Multi-field search across names, types, and observations

### 🔧 **Modern Architecture**
- **FastMCP Implementation**: Uses the latest MCP Python SDK 1.2.0+ patterns
- **Automatic Schema Generation**: Tools defined with type hints automatically generate JSON schemas
- **MongoDB Native**: Built specifically for MongoDB with advanced aggregation pipelines
- **Type Safety**: Full Pydantic model validation with automatic serialization
- **Production Ready**: Optimized for concurrent access and large datasets

## Installation

### Requirements

- Python 3.10 or higher
- MongoDB 4.4 or higher
- MCP Python SDK 1.2.0+
- Dependencies managed via `uv` (recommended)

### Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### Development Dependencies

```bash
# Install development dependencies
uv sync --group dev

# Or using pip
pip install -e .[dev]
```

## Configuration

### MongoDB Setup

Ensure MongoDB is running on your system:

```bash
# macOS with Homebrew
brew services start mongodb-community

# Ubuntu/Debian
sudo systemctl start mongod

# Windows
net start MongoDB
```

### Environment Variables

```bash
export MONGODB_URI=mongodb://localhost:27017
export MONGODB_DATABASE=knowledge_graph_db
export MONGODB_COLLECTION_PREFIX=kg_  # optional
```

## Usage

### Running the Server

```bash
# Using uv (recommended)
uv run python mongodb_knowledge_graph/main.py

# Or directly with Python
python -m mongodb_knowledge_graph.main
```

### MCP Tools

The server exposes the following optimized tools:

#### 📊 **Graph Overview**
- `get_graph_summary` - **NEW!** Get graph statistics without loading full data
- `read_graph` - Retrieve entire graph (use sparingly for large datasets)

#### 🔍 **Entity Management** 
- `create_entities` - Batch create entities efficiently
- `delete_entities` - Remove entities and cascade delete relations
- `add_observations` - Add observations with deduplication
- `delete_observations` - Remove specific observations

#### 🔗 **Relationship Management**
- `create_relations` - Batch create relationships efficiently  
- `delete_relations` - Remove specific relationships

#### 🎯 **Query & Search Operations**
- `search_nodes` - Search entities by name, type, or observation content
- `open_nodes` - Retrieve specific entities by name
- `get_subgraph` - **NEW!** Explore entity neighborhoods with depth control
- `find_path` - **NEW!** Discover shortest paths between entities

### Example Usage

#### Basic Entity and Relation Creation

```python
from mongodb_knowledge_graph.types import Entity, Relation

# Create entities
entities = [
    Entity(
        name="Alice Johnson",
        entity_type="person", 
        observations=["Senior Software Engineer", "Expert in Python", "Lives in Seattle"]
    ),
    Entity(
        name="TechCorp Inc",
        entity_type="company",
        observations=["AI Startup", "Series B funded", "100+ employees"]
    )
]

# Create relations
relations = [
    Relation(
        from_entity="Alice Johnson",
        to_entity="TechCorp Inc",
        relation_type="works_at"
    )
]
```

#### Advanced Graph Operations

```python
# Get overview without loading full graph
summary = await get_graph_summary()
# Returns: {"entity_count": 1000, "relation_count": 2500, "sample_entities": [...]}

# Explore Alice's network (2 hops deep)
subgraph = await get_subgraph("Alice Johnson", max_depth=2)
# Returns: All entities within 2 relationships of Alice

# Find how Alice connects to a specific project
path = await find_path("Alice Johnson", "AI Research Project") 
# Returns: [Alice Johnson, TechCorp Inc, Research Division, AI Research Project]

# Search for AI-related entities
results = await search_nodes("artificial intelligence")
# Returns: Matching entities with their connections
```

## Development

### Project Structure

```
mongodb-knowledge-graph/
├── mongodb_knowledge_graph/
│   ├── __init__.py
│   ├── main.py                 # FastMCP server entry point
│   ├── knowledge_graph.py      # High-level graph operations
│   ├── types.py               # Pydantic data models
│   └── storage/
│       ├── base.py            # Storage adapter interface
│       ├── factory.py         # Storage factory
│       └── mongodb_adapter.py # Optimized MongoDB operations
├── tests/                     # Comprehensive test suite
├── pyproject.toml            # Project configuration
└── README.md
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Test MongoDB functionality (requires running MongoDB)
TEST_MONGODB=1 uv run pytest tests/test_mongodb_*

# Run with coverage
uv run pytest --cov=mongodb_knowledge_graph --cov-report=html

# Test specific functionality
uv run pytest tests/test_knowledge_graph.py -v
```


## MongoDB Optimization Features

### Indexes
- **Unique index** on entity names for fast lookups
- **Compound index** on relations (from, to, type) for relationship queries
- **Text index** on observations for full-text search

### Aggregation Pipelines
- **Graph traversal** using `$graphLookup` for subgraph exploration
- **Efficient joins** between entities and relations
- **Pagination** support for large result sets

### Query Patterns
- **Batch operations** for multiple entities/relations
- **Incremental updates** using `$addToSet` and `$pull`
- **Existence checks** without data retrieval
- **Count queries** for statistics

## Best Practices

### For Large Graphs
1. Use `get_graph_summary()` instead of `read_graph()`
2. Search with `search_nodes()` rather than loading everything
3. Explore locally with `get_subgraph()` instead of broad queries
4. Batch operations when creating multiple entities/relations

### For Performance
1. Create indexes on frequently queried fields
2. Use appropriate `max_depth` values for subgraph exploration
3. Limit search result sizes when appropriate
4. Monitor MongoDB performance metrics

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run the full test suite (`uv run pytest`)
5. Ensure MongoDB tests pass (`TEST_MONGODB=1 uv run pytest`)
6. Submit a pull request

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/modelcontextprotocol/servers).

---

**🚀 Built for Scale** • **🧠 Optimized for AI** • **⚡ MongoDB Native**