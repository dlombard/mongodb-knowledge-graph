# MongoDB Knowledge Graph MCP Server

A high-performance Python implementation of a Model Context Protocol (MCP) server that provides persistent memory your AI agent through a MongoDB-based knowledge graph storage system.

## Overview

This MCP server enables your AI agent to create, manage, and recall information using a structured knowledge graph stored efficiently in MongoDB.

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
```

### Environment Variables

```bash
export MONGODB_URI=mongodb://localhost:27017
export MONGODB_DATABASE=knowledge_graph_db
export MONGODB_COLLECTION_PREFIX=kg_  # optional
```

# Usage with Claude Desktop

### Setup

Add this to your claude_desktop_config.json:

#### uv

```json
  {
    "mcpServers": {
      "mongodb-knowledge-graph": {
        "command": "uv",
        "args": [
          "run",
          "mongodb_knowledge_graph/main.py",
          "run",
          "mongodb_knowledge_graph"
        ],
        "env": {
          "MONGODB_URI": "mongodb://localhost:27017",
          "MONGODB_DATABASE": "knowledge_graph_db",
        }
      }
    }
  }
```

# VS Code Installation Instructions

Add the following JSON block to your User Settings (JSON) file in VS Code. You can do this by pressing `Ctrl + Shift + P` and typing `Preferences: Open Settings (JSON)`.

Optionally, you can add it to a file called `.vscode/mcp.json` in your workspace. This will allow you to share the configuration with others. 

> Note that the `mcp` key is not needed in the `.vscode/mcp.json` file.

#### uv

```json
{
  "mcp": {
    "servers": {
      "mongodb-knowledge-graph": {
        "command": "uv",
        "args": [
          "run",
          "mongodb_knowledge_graph/main.py"
        ],
        "env":{
          "MONGODB_URI": "mongodb://localhost:27017",
          "MONGODB_DATABASE": "knowledge_graph_db",
        }
      }
    }
  }
}
```

### MCP Tools

The server exposes the following tools:

#### 📊 **Graph Overview**
- `get_graph_summary` - Get graph statistics without loading full data
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
- `get_subgraph` - Explore entity neighborhoods with depth control
- `find_path` - Discover shortest paths between entities


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


## Best Practices

### For Large Graphs
1. Use `get_graph_summary()` instead of `read_graph()`
2. Search with `search_nodes()` rather than loading everything
3. Explore locally with `get_subgraph()` instead of broad queries


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

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/dlombard/mongodb-knowledge-graph).

---
