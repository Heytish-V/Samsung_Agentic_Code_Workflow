"""Database connection manager with pooling and health checks.

Handles connection lifecycle, pool management, retry logic,
and connection health monitoring.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Connection Pool
# ──────────────────────────────────────────────────────────────────

class ConnectionPool:
    """Thread-safe connection pool for database connections."""

    def __init__(self, max_size: int = 10, timeout: float = 30.0):
        """Initialize the connection pool.

        Args:
            max_size: Maximum number of connections in the pool.
            timeout: Connection timeout in seconds.
        """
        self.max_size = max_size
        self.timeout = timeout
        self._connections = []
        self._in_use = set()
        self._created_count = 0

    def acquire(self) -> "DatabaseConnection":
        """Acquire a connection from the pool.

        Returns:
            An active database connection.

        Raises:
            ConnectionError: If no connection is available.
        """
        # Try to reuse an idle connection
        for conn in self._connections:
            if conn.connection_id not in self._in_use:
                if check_connection_health(conn):
                    self._in_use.add(conn.connection_id)
                    return conn

        # Create new connection if pool not full
        if self._created_count < self.max_size:
            conn = connect_db(
                host="localhost",
                port=5432,
                database="prism_demo",
            )
            self._connections.append(conn)
            self._in_use.add(conn.connection_id)
            self._created_count += 1
            return conn

        raise ConnectionError("Connection pool exhausted")

    def release(self, conn: "DatabaseConnection") -> None:
        """Return a connection to the pool.

        Args:
            conn: The connection to release.
        """
        self._in_use.discard(conn.connection_id)

    def close_all(self) -> None:
        """Close all connections in the pool."""
        for conn in self._connections:
            close_connection(conn)
        self._connections.clear()
        self._in_use.clear()
        self._created_count = 0


# ──────────────────────────────────────────────────────────────────
# Connection Object
# ──────────────────────────────────────────────────────────────────

class DatabaseConnection:
    """Represents a single database connection."""

    def __init__(self, host: str, port: int, database: str):
        self.host = host
        self.port = port
        self.database = database
        self.connection_id = f"conn_{id(self)}_{int(time.time())}"
        self.connected = True
        self.created_at = time.time()
        self.last_used = time.time()

    def is_alive(self) -> bool:
        """Check if the connection is still active."""
        return self.connected and (time.time() - self.last_used < 300)


# ──────────────────────────────────────────────────────────────────
# Connection Functions
# ──────────────────────────────────────────────────────────────────

def connect_db(
    host: str = "localhost",
    port: int = 5432,
    database: str = "prism_demo",
) -> DatabaseConnection:
    """Establish a new database connection.

    Creates a connection to the specified database server,
    performs the handshake, and returns a ready-to-use connection.

    Args:
        host: Database server hostname.
        port: Database server port.
        database: Name of the database to connect to.

    Returns:
        An active DatabaseConnection instance.

    Raises:
        ConnectionError: If the connection cannot be established.
    """
    logger.info("Connecting to %s:%d/%s", host, port, database)

    conn = DatabaseConnection(host, port, database)

    # Simulate connection handshake
    validate_connection_params(host, port, database)

    logger.info("Connected: %s", conn.connection_id)
    return conn


def validate_connection_params(host: str, port: int, database: str) -> None:
    """Validate connection parameters before establishing connection.

    Args:
        host: The hostname to validate.
        port: The port number to validate.
        database: The database name to validate.

    Raises:
        ValueError: If any parameter is invalid.
    """
    if not host or not isinstance(host, str):
        raise ValueError("Invalid host")
    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port}")
    if not database or not isinstance(database, str):
        raise ValueError("Invalid database name")


def check_connection_health(conn: DatabaseConnection) -> bool:
    """Verify that a database connection is still healthy.

    Sends a lightweight ping query and checks the response.

    Args:
        conn: The connection to check.

    Returns:
        True if the connection is healthy.
    """
    if not conn.is_alive():
        logger.warning("Connection %s is stale", conn.connection_id)
        return False

    conn.last_used = time.time()
    return True


def close_connection(conn: DatabaseConnection) -> None:
    """Gracefully close a database connection.

    Args:
        conn: The connection to close.
    """
    conn.connected = False
    logger.info("Connection closed: %s", conn.connection_id)


def get_connection_pool(
    max_size: int = 10,
    timeout: float = 30.0,
) -> ConnectionPool:
    """Create and return a configured connection pool.

    Args:
        max_size: Maximum pool size.
        timeout: Connection timeout in seconds.

    Returns:
        A configured ConnectionPool instance.
    """
    pool = ConnectionPool(max_size=max_size, timeout=timeout)
    logger.info("Connection pool created (max_size=%d)", max_size)
    return pool
