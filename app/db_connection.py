
"""
db_connection.py

This module provides functions for connecting to the PostgreSQL database.
It handles connection pooling, retries, and error handling.
"""

import os
import time
import logging
from typing import Optional, Tuple, Dict, Any, List

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global connection pool
connection_pool = None

def get_connection_string() -> str:
    """
    Get the database connection string from environment variables.
    
    Returns:
        str: Database connection string
    """
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

def init_connection_pool(min_connections: int = 1, max_connections: int = 10) -> None:
    """
    Initialize the database connection pool.
    
    Args:
        min_connections: Minimum number of connections in the pool
        max_connections: Maximum number of connections in the pool
    """
    global connection_pool
    
    if connection_pool is not None:
        logger.info("Connection pool already initialized")
        return
    
    connection_string = get_connection_string()
    
    if not connection_string:
        raise ValueError("No database connection information found in environment variables")
    
    try:
        logger.info(f"Initializing connection pool with {min_connections}-{max_connections} connections")
        connection_pool = pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            connection_string
        )
        logger.info("Connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing connection pool: {e}")
        raise

def get_db_connection(max_retries: int = 3, retry_delay: int = 2) -> Tuple[Optional[psycopg2.extensions.connection], bool]:
    """
    Get a connection from the pool with retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Tuple containing the connection object and a flag indicating if it's a new connection
    """
    global connection_pool
    
    # Initialize pool if it doesn't exist
    if connection_pool is None:
        init_connection_pool()
    
    retry_count = 0
    connection = None
    is_new_connection = False
    
    while retry_count < max_retries:
        try:
            # Get connection from pool
            connection = connection_pool.getconn()
            
            # Test the connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                
            return connection, is_new_connection
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"Database connection attempt {retry_count} failed: {e}")
            
            if connection is not None:
                try:
                    connection_pool.putconn(connection)
                except:
                    pass
                connection = None
            
            # If we've reached max retries, try creating a new connection outside the pool
            if retry_count >= max_retries:
                logger.warning("Max retries reached, attempting direct connection")
                try:
                    connection_string = get_connection_string()
                    connection = psycopg2.connect(connection_string)
                    is_new_connection = True
                    return connection, is_new_connection
                except Exception as direct_error:
                    logger.error(f"Failed to establish direct connection: {direct_error}")
                    return None, False
            
            # Wait before retrying
            time.sleep(retry_delay)
    
    return None, False

def return_db_connection(connection: psycopg2.extensions.connection, is_new_connection: bool) -> None:
    """
    Return a connection to the pool or close it if it was created outside the pool.
    
    Args:
        connection: The connection to return
        is_new_connection: Whether this connection was created outside the pool
    """
    global connection_pool
    
    if connection is None:
        return
    
    try:
        if is_new_connection:
            connection.close()
        else:
            connection_pool.putconn(connection)
    except Exception as e:
        logger.error(f"Error returning connection to pool: {e}")
        # Try to close it directly if putconn fails
        try:
            connection.close()
        except:
            pass

def execute_query(query: str, params=None, fetch_one: bool = False, dict_cursor: bool = False):
    """
    Execute a query and return the results.
    
    Args:
        query: SQL query string
        params: Query parameters
        fetch_one: Whether to fetch only one result
        dict_cursor: Whether to use a dictionary cursor
        
    Returns:
        Query results or None on error
    """
    conn, is_new = get_db_connection()
    
    if conn is None:
        logger.error("Failed to get database connection")
        return None
    
    try:
        cursor_factory = RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=cursor_factory) as cursor:
            cursor.execute(query, params)
            
            if query.strip().upper().startswith(('SELECT', 'WITH')):
                if fetch_one:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        conn.rollback()
        return None
    finally:
        return_db_connection(conn, is_new)

def close_connection_pool():
    """Close all connections in the pool."""
    global connection_pool
    
    if connection_pool is not None:
        try:
            connection_pool.closeall()
            logger.info("Closed all database connections")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            connection_pool = None

def check_database_status() -> Dict[str, Any]:
    """
    Check the status of the database connection and return details.
    
    Returns:
        Dict containing status information
    """
    status = {
        "connection": False,
        "database_url_exists": 'DATABASE_URL' in os.environ,
        "error": None,
        "tables": [],
        "details": {}
    }
    
    if not status["database_url_exists"]:
        status["error"] = "DATABASE_URL environment variable not found"
        return status
    
    try:
        conn = psycopg2.connect(get_connection_string())
        status["connection"] = True
        
        # Get database details
        with conn.cursor() as cursor:
            # PostgreSQL version
            cursor.execute("SELECT version()")
            status["details"]["version"] = cursor.fetchone()[0]
            
            # List tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            status["tables"] = [row[0] for row in cursor.fetchall()]
            
            # Check for required tables
            required_tables = [
                'users', 'legislation', 'legislation_analysis', 
                'legislation_priorities', 'sync_metadata'
            ]
            status["details"]["missing_tables"] = [
                table for table in required_tables 
                if table not in status["tables"]
            ]
            
            # Check if admin user exists
            if 'users' in status["tables"]:
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                status["details"]["admin_user_exists"] = cursor.fetchone()[0] > 0
        
        conn.close()
    except Exception as e:
        status["error"] = str(e)
    
    return status
