#!/usr/bin/env python
"""
db_connection.py

This module provides database connection functionality for the PolicyPulse application.
It handles connecting to PostgreSQL, connection pooling, and database status checking.
"""

import os
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection_string():
    """Get the database connection string from environment variables."""
    # For Replit PostgreSQL integration
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']

    # For local development or explicit configuration
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', 'postgres')
    dbname = os.environ.get('DB_NAME', 'policypulse')

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

# Global connection pool
_pool = None

def get_connection_pool(min_conn=1, max_conn=10):
    """
    Get or create a database connection pool.

    Args:
        min_conn: Minimum number of connections
        max_conn: Maximum number of connections

    Returns:
        SimpleConnectionPool: A PostgreSQL connection pool
    """
    global _pool

    if _pool is None:
        try:
            connection_string = get_connection_string()
            _pool = SimpleConnectionPool(
                min_conn,
                max_conn,
                connection_string
            )
            logger.info(f"Created connection pool with {min_conn}-{max_conn} connections")
        except Exception as e:
            logger.error(f"Error creating connection pool: {e}")
            raise

    return _pool

def get_connection():
    """
    Get a connection from the pool.

    Returns:
        A PostgreSQL connection from the pool
    """
    pool = get_connection_pool()
    return pool.getconn()

def release_connection(conn):
    """
    Release a connection back to the pool.

    Args:
        conn: The connection to release
    """
    pool = get_connection_pool()
    pool.putconn(conn)

def execute_query(query, params=None, fetchone=False, fetchall=True, cursor_factory=DictCursor):
    """
    Execute a query and return the results.

    Args:
        query: SQL query string
        params: Parameters for the query
        fetchone: Whether to fetch one result
        fetchall: Whether to fetch all results
        cursor_factory: Factory for cursor type

    Returns:
        Query results as dictionaries
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=cursor_factory) as cur:
            cur.execute(query, params)

            if cur.description is None:  # No results expected (e.g., INSERT)
                conn.commit()
                return cur.rowcount

            if fetchone:
                return cur.fetchone()
            elif fetchall:
                return cur.fetchall()
            return None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def check_database_status():
    """
    Check the status of the database connection and schema.

    Returns:
        dict: Status information
    """
    status = {
        "connection": False,
        "tables": [],
        "details": {},
        "error": None
    }

    conn = None
    try:
        # Try to connect
        conn = psycopg2.connect(get_connection_string())
        status["connection"] = True

        with conn.cursor() as cursor:
            # Get list of tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            status["tables"] = [row[0] for row in cursor.fetchall()]

            # Check for required tables
            required_tables = [
                'users', 'legislation', 'legislation_analysis', 
                'legislation_text', 'alert_preferences'
            ]

            status["details"]["missing_tables"] = [
                table for table in required_tables 
                if table not in status["tables"]
            ]

            # Check if admin user exists
            if 'users' in status["tables"]:
                # Execute the query
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                # Fetch the result
                result = cursor.fetchone()
                # Check if result is not None and then subscript
                status["details"]["admin_user_exists"] = (result[0] if result else 0) > 0

        conn.close()
    except Exception as e:
        status["error"] = str(e)

    return status

def close_all_connections():
    """Close all connections in the pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Closed all database connections")

# Example usage
if __name__ == "__main__":
    status = check_database_status()
    if status["connection"]:
        print(f"Connected to database. Found {len(status['tables'])} tables.")
    else:
        print(f"Could not connect to database: {status['error']}")