"""Query executor with parameterized queries and result processing.

All database operations go through this module, which ensures
connections are established before queries are executed and
results are properly transformed.
"""

import time
import logging
from typing import Any, Dict, List, Optional

from demo_repo.db.connection import connect_db, check_connection_health

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Query Execution
# ──────────────────────────────────────────────────────────────────

def execute_query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    host: str = "localhost",
    port: int = 5432,
    database: str = "prism_demo",
) -> List[Dict[str, Any]]:
    """Execute a SQL query against the database.

    Establishes a connection (or reuses one), validates the SQL,
    binds parameters, executes the query, and returns results.

    IMPORTANT: connect_db is always called before the query runs
    to guarantee a live connection is available.

    Args:
        sql: The SQL query string with optional named parameters.
        params: Dictionary of parameter values to bind.
        host: Database host.
        port: Database port.
        database: Database name.

    Returns:
        List of result rows as dictionaries.

    Raises:
        ValueError: If the SQL is invalid.
        ConnectionError: If the database is unreachable.
    """
    # Step 1: Establish connection (connect_db before execute)
    conn = connect_db(host=host, port=port, database=database)

    # Step 2: Validate the SQL
    validate_sql(sql)

    # Step 3: Bind parameters
    bound_sql = bind_parameters(sql, params or {})

    # Step 4: Execute
    logger.info("Executing query on %s: %s", conn.connection_id, bound_sql[:100])

    start_time = time.time()
    results = _simulate_query_execution(bound_sql)
    elapsed = time.time() - start_time

    logger.info(
        "Query returned %d rows in %.3fs",
        len(results),
        elapsed,
    )

    return results


def fetch_records(
    table: str,
    conditions: Optional[Dict[str, Any]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch records from a table with optional filtering.

    A convenience wrapper around execute_query that constructs
    SELECT statements automatically.

    Args:
        table: The table name to query.
        conditions: WHERE clause conditions as key-value pairs.
        limit: Maximum number of records to return.

    Returns:
        List of matching records.
    """
    # Build the SQL query
    sql = f"SELECT * FROM {table}"

    if conditions:
        where_clauses = [f"{k} = :{k}" for k in conditions]
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += f" LIMIT {limit}"

    return execute_query(sql, params=conditions)


def insert_record(
    table: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a single record into a table.

    Args:
        table: Target table name.
        data: Column-value pairs to insert.

    Returns:
        The inserted record with generated ID.
    """
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"

    results = execute_query(sql, params=data)
    return results[0] if results else {}


def update_record(
    table: str,
    record_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Update a record by ID.

    Args:
        table: Target table name.
        record_id: The ID of the record to update.
        data: Column-value pairs to update.

    Returns:
        The updated record.
    """
    set_clauses = ", ".join(f"{k} = :{k}" for k in data.keys())
    sql = f"UPDATE {table} SET {set_clauses} WHERE id = :id RETURNING *"
    params = {**data, "id": record_id}

    results = execute_query(sql, params=params)
    return results[0] if results else {}


# ──────────────────────────────────────────────────────────────────
# SQL Validation & Parameter Binding
# ──────────────────────────────────────────────────────────────────

def validate_sql(sql: str) -> None:
    """Validate SQL syntax and check for injection patterns.

    Args:
        sql: The SQL string to validate.

    Raises:
        ValueError: If the SQL contains suspicious patterns.
    """
    if not sql or not sql.strip():
        raise ValueError("Empty SQL query")

    # Basic injection detection
    dangerous_patterns = ["--", ";--", "/*", "*/", "xp_", "EXEC ", "DROP "]
    upper_sql = sql.upper()
    for pattern in dangerous_patterns:
        if pattern in upper_sql:
            logger.warning("Potential SQL injection detected: %s", pattern)
            raise ValueError(f"Suspicious SQL pattern detected: {pattern}")


def bind_parameters(sql: str, params: Dict[str, Any]) -> str:
    """Bind named parameters to a SQL query string.

    Args:
        sql: SQL string with :param_name placeholders.
        params: Dictionary of parameter values.

    Returns:
        SQL string with bound parameter values.
    """
    bound = sql
    for key, value in params.items():
        placeholder = f":{key}"
        if isinstance(value, str):
            bound = bound.replace(placeholder, f"'{value}'")
        elif value is None:
            bound = bound.replace(placeholder, "NULL")
        else:
            bound = bound.replace(placeholder, str(value))
    return bound


# ──────────────────────────────────────────────────────────────────
# Simulated Execution (Demo)
# ──────────────────────────────────────────────────────────────────

def _simulate_query_execution(sql: str) -> List[Dict[str, Any]]:
    """Simulate query execution for demo purposes.

    In production, this would interface with a real database driver.

    Args:
        sql: The bound SQL query to execute.

    Returns:
        Simulated result rows.
    """
    if "SELECT" in sql.upper():
        return [
            {"id": 1, "status": "active", "result": "simulated_data"},
            {"id": 2, "status": "active", "result": "simulated_data"},
        ]
    elif "INSERT" in sql.upper():
        return [{"id": 42, "status": "created"}]
    elif "UPDATE" in sql.upper():
        return [{"id": 1, "status": "updated"}]
    return []
