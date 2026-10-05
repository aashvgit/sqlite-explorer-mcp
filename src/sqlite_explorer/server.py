import sqlite3
import sys
from contextlib import closing
from pathlib import Path
import time 

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DB_PATH: Path | None = None

mcp = MCPServer("sqlite-explorer")
QUERY_TIMEOUT_S = 5

def connect() -> sqlite3.Connection:
    """Open a fresh read-only connection. One per tool call."""
    if DB_PATH is None:
        raise ToolError(
            "No database configured. Start the server with a path: "
            "sqlite-explorer-mcp /path/to/file.db"
        )
    if not DB_PATH.exists():
        raise ToolError(f"Database file not found at {DB_PATH}.")
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


@mcp.tool()
def list_tables() -> list[str]:
    with closing(connect()) as conn:
        return table_names(conn)


@mcp.tool()
def describe_table(table_name: str) -> str:
    with closing(connect()) as conn:
        tables = table_names(conn)
        if table_name not in tables:
            raise ToolError(
                f"No table named '{table_name}'. Available tables: {', '.join(tables)}."
            )
        cols = conn.execute(
            'SELECT name, type, "notnull", pk FROM pragma_table_info(?)', (table_name,)
        ).fetchall()
    lines = []
    for name, col_type, notnull, pk in cols:
        flags = []
        if pk:
            flags.append("primary key")
        if notnull:
            flags.append("required")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"{name} {col_type}{suffix}")
    return "\n".join(lines)

MAX_ROWS = 50

def format_rows(columns: list[str], rows: list[tuple], truncated: bool) -> str:
    if not rows:
        return "Query ran successfully but returned 0 rows."
    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join("NULL" if v is None else str(v) for v in row))
    if truncated:
        lines.append(f"... (truncated to {MAX_ROWS} rows)"
                     "Add a WHERE or LIMIT clause to reduce the number of rows returned.")
    return "\n".join(lines)

@mcp.tool()
def preview_table(table_name: str, limit: int = 5) -> str:
    limit = max(1, min(limit, MAX_ROWS))
    with closing(connect()) as conn:
        tables = table_names(conn)
        if table_name not in tables:
            raise ToolError(
                f"No table named '{table_name}'. Available tables: {', '.join(tables)}."
            )
        cur = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return format_rows(columns, rows, truncated=False)

@mcp.tool()
def run_select_query(sql: str) -> str:
    statement = sql.strip().rstrip(";")
    if not statement.lower().startswith(("select", "with")):
        raise ToolError("Only SELECT queries are allowed. Rewrite query to start with SELECT.")
    if ";" in statement:
        raise ToolError("Send one statement at a time (no ';' inside the query).")
    with closing(connect()) as conn:
        deadline = time.monotonic() + QUERY_TIMEOUT_S
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        try:
            cur = conn.execute(statement)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(MAX_ROWS + 1)
        except sqlite3.OperationalError as e:
            msg = str(e)
            if "interrupted" in msg:
                raise ToolError(
                    f"Query stopped after {QUERY_TIMEOUT_S} seconds. "
                    "Make it cheaper: add a WHERE or LIMIT clause and avoid recursive queries."
                )
            if "locked" in msg:
                raise ToolError(
                    "The database is busy (locked by another process). "
                    "Wait a few seconds and try the same query again."
                )
            raise ToolError(
                f"SQL error: {e}. Use describe_table to check table and column names."
            )
        except sqlite3.Error as e:
            raise ToolError(
                f"SQL error: {e}. Use describe_table to check table and column names."
            )
        truncated = len(rows) > MAX_ROWS
    return format_rows(columns, rows[:MAX_ROWS], truncated)

@mcp.tool()
def get_distinct_values(table_name: str, column_name: str, limit: int = 25) -> str:
    """List the distinct values stored in one column, with how many rows have each value.

    Use this before filtering on a text column (like genre) so you match the exact
    spelling stored in the data instead of guessing. Not useful for columns where
    almost every value is different (like ids or titles).
    table_name must come from list_tables; column_name must come from describe_table.
    limit is the maximum number of distinct values to return (1 to 50, default 25).
    """
    limit = max(1, min(limit, MAX_ROWS))
    with closing(connect()) as conn:
        tables = table_names(conn)
        if table_name not in tables:
            raise ToolError(
                f"No table named '{table_name}'. Available tables: {', '.join(tables)}."
            )
        columns = [
            r[0]
            for r in conn.execute("SELECT name FROM pragma_table_info(?)", (table_name,))
        ]
        if column_name not in columns:
            raise ToolError(
                f"No column named '{column_name}' in table '{table_name}'. "
                f"Available columns: {', '.join(columns)}."
            )
        rows = conn.execute(
            f'SELECT "{column_name}", COUNT(*) FROM "{table_name}" '
            f'GROUP BY "{column_name}" ORDER BY COUNT(*) DESC LIMIT ?',
            (limit + 1,),
        ).fetchall()
    lines = ["value | row_count"]
    for value, count in rows[:limit]:
        lines.append(f"{'NULL' if value is None else value} | {count}")
    if len(rows) > limit:
        lines.append(f"... more distinct values exist; showing the {limit} most common.")
    return "\n".join(lines)


def main() -> None:
    global DB_PATH
    if len(sys.argv) != 2:
        sys.exit("Usage: sqlite-explorer-mcp /path/to/database.db")
    DB_PATH = Path(sys.argv[1]).expanduser().resolve()
    mcp.run()


if __name__ == "__main__":
    main()