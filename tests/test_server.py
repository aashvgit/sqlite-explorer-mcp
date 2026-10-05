import sqlite3

import pytest
from mcp import Client

import sqlite_explorer.server as main

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A tiny throwaway database, so tests never touch library.db."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL, genre TEXT);
        INSERT INTO books (title, genre) VALUES ('Dune', 'sci-fi'), ('Emma', 'classic');
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(main, "DB_PATH", path)
    return path


@pytest.fixture
async def client(db):
    async with Client(main.mcp) as c:
        yield c


def text_of(result) -> str:
    return result.content[0].text


@pytest.mark.anyio
async def test_list_tables(client):
    result = await client.call_tool("list_tables", {})
    assert result.structured_content == {"result": ["books"]}


@pytest.mark.anyio
async def test_describe_missing_table_gives_helpful_error(client):
    result = await client.call_tool("describe_table", {"table_name": "bookz"})
    assert result.is_error
    assert "Available tables: books" in text_of(result)


@pytest.mark.anyio
async def test_select_returns_rows(client):
    result = await client.call_tool(
        "run_select_query", {"sql": "SELECT title FROM books WHERE genre = 'sci-fi'"}
    )
    assert not result.is_error
    assert "Dune" in text_of(result)
    assert "Emma" not in text_of(result)


@pytest.mark.anyio
async def test_rejects_non_select(client):
    result = await client.call_tool("run_select_query", {"sql": "DELETE FROM books"})
    assert result.is_error
    assert "Only SELECT" in text_of(result)


@pytest.mark.anyio
async def test_rejects_multiple_statements(client):
    result = await client.call_tool(
        "run_select_query", {"sql": "SELECT 1; DROP TABLE books"}
    )
    assert result.is_error
    assert "one statement" in text_of(result)


@pytest.mark.anyio
async def test_read_only_blocks_sneaky_write(client):
    # Starts with WITH, so it passes our text check. The read-only connection must stop it.
    sneaky = "WITH x AS (SELECT 1) DELETE FROM books"
    result = await client.call_tool("run_select_query", {"sql": sneaky})
    assert result.is_error
    still_there = await client.call_tool(
        "run_select_query", {"sql": "SELECT count(*) FROM books"}
    )
    assert "2" in text_of(still_there)


@pytest.mark.anyio
async def test_truncation_is_success_with_warning(client):
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c LIMIT 60) SELECT x FROM c"
    result = await client.call_tool("run_select_query", {"sql": sql})
    assert not result.is_error
    assert "truncated" in text_of(result)


@pytest.mark.anyio
async def test_timeout_is_an_error(client, monkeypatch):
    monkeypatch.setattr(main, "QUERY_TIMEOUT_S", 0.2)  # don't wait 5 real seconds
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
    result = await client.call_tool("run_select_query", {"sql": sql})
    assert result.is_error
    assert "stopped after" in text_of(result)

@pytest.mark.anyio
async def test_distinct_values(client):
    result = await client.call_tool(
        "get_distinct_values", {"table_name": "books", "column_name": "genre"}
    )
    assert not result.is_error
    assert "sci-fi | 1" in text_of(result)


@pytest.mark.anyio
async def test_distinct_values_bad_column(client):
    result = await client.call_tool(
        "get_distinct_values", {"table_name": "books", "column_name": "genr"}
    )
    assert result.is_error
    assert "Available columns" in text_of(result)