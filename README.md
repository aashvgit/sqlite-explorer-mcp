# sqlite-explorer-mcp

A read-only MCP server for exploring a SQLite database.

mcp-name: io.github.YOUR-GITHUB-USERNAME/sqlite-explorer-mcp

## Usage

    uvx sqlite-explorer-mcp /path/to/database.db

## Tools

- `list_tables`: list all tables
- `describe_table`: show a table's columns
- `preview_table`: show the first rows of a table
- `run_select_query`: run a read-only SELECT (50 rows max, 5 second limit)