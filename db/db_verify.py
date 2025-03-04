#!/usr/bin/env python
"""
db_verify.py

A comprehensive verification script to check if the PolicyPulse database is properly set up.
This script will:
1. Test the connection to the database
2. Verify that all expected tables, columns, and relationships exist
3. Check that all extensions are installed
4. Validate that triggers and functions are properly configured
5. Test basic CRUD operations
6. Generate a comprehensive report

Usage:
  python db_verify.py [--verbose] [--fix]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect, MetaData, Table, select, func
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import pandas as pd
from tabulate import tabulate
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:H6v@3xP!2qL#9zR8@localhost:5432/policypulse")

# Expected database objects
EXPECTED_TABLES = [
    'users', 'user_preferences', 'search_history', 'alert_preferences',
    'legislation', 'legislation_analysis', 'legislation_text',
    'legislation_sponsors', 'amendments', 'legislation_priorities',
    'impact_ratings', 'implementation_requirements', 'alert_history',
    'sync_metadata', 'sync_errors'
]

EXPECTED_ENUMS = [
    'data_source_enum', 'govt_type_enum', 'bill_status_enum', 
    'impact_level_enum', 'impact_category_enum', 'amendment_status_enum',
    'notification_type_enum', 'sync_status_enum'
]

EXPECTED_EXTENSIONS = [
    'pg_trgm', 'unaccent'
]

EXPECTED_FUNCTIONS = [
    'legislation_search_update_trigger', 'update_modified_column'
]

EXPECTED_INDEXES = [
    'idx_legislation_status', 'idx_legislation_dates', 'idx_legislation_change',
    'idx_legislation_search', 'idx_amendments_legislation', 'idx_amendments_date',
    'idx_priority_health', 'idx_priority_local_govt', 'idx_priority_overall'
]

# Expected relationships
RELATIONSHIPS = [
    ('user_preferences', 'users', 'user_id', 'id'),
    ('search_history', 'users', 'user_id', 'id'),
    ('alert_preferences', 'users', 'user_id', 'id'),
    ('alert_history', 'users', 'user_id', 'id'),
    ('alert_history', 'legislation', 'legislation_id', 'id'),
    ('legislation_analysis', 'legislation', 'legislation_id', 'id'),
    ('legislation_text', 'legislation', 'legislation_id', 'id'),
    ('legislation_sponsors', 'legislation', 'legislation_id', 'id'),
    ('amendments', 'legislation', 'legislation_id', 'id'),
    ('legislation_priorities', 'legislation', 'legislation_id', 'id'),
    ('impact_ratings', 'legislation', 'legislation_id', 'id'),
    ('implementation_requirements', 'legislation', 'legislation_id', 'id'),
    ('sync_errors', 'sync_metadata', 'sync_id', 'id')
]


def print_header(text):
    """Print a formatted header."""
    print(f"\n{Fore.CYAN}{'=' * 80}")
    print(f" {text}")
    print(f"{'=' * 80}{Style.RESET_ALL}")


def print_success(text):
    """Print a success message."""
    print(f"{Fore.GREEN}✓ {text}{Style.RESET_ALL}")


def print_warning(text):
    """Print a warning message."""
    print(f"{Fore.YELLOW}⚠ {text}{Style.RESET_ALL}")


def print_error(text):
    """Print an error message."""
    print(f"{Fore.RED}✗ {text}{Style.RESET_ALL}")


def print_info(text):
    """Print an info message."""
    print(f"{Fore.BLUE}ℹ {text}{Style.RESET_ALL}")


def connect_to_database():
    """Create and return a database engine."""
    try:
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        print_error(f"Failed to create database engine: {e}")
        return None


def test_connection(engine):
    """Test the connection to the database."""
    print_header("TESTING DATABASE CONNECTION")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            version = result.scalar()
            print_success(f"Connected to PostgreSQL: {version}")
            return True
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return False


def check_extensions(engine):
    """Check if all required PostgreSQL extensions are installed."""
    print_header("CHECKING POSTGRESQL EXTENSIONS")
    try:
        with engine.connect() as connection:
            result = connection.execute(text(
                "SELECT extname FROM pg_extension"
            ))
            installed_extensions = [row[0] for row in result]
            
            all_installed = True
            for ext in EXPECTED_EXTENSIONS:
                if ext in installed_extensions:
                    print_success(f"Extension {ext} is installed")
                else:
                    print_error(f"Extension {ext} is NOT installed")
                    all_installed = False
            
            return all_installed
    except Exception as e:
        print_error(f"Failed to check extensions: {e}")
        return False


def check_enums(engine):
    """Check if all required enum types are created."""
    print_header("CHECKING ENUM TYPES")
    try:
        with engine.connect() as connection:
            result = connection.execute(text(
                "SELECT typname FROM pg_type JOIN pg_catalog.pg_namespace n ON typnamespace = n.oid "
                "WHERE typtype = 'e' AND n.nspname = 'public'"
            ))
            installed_enums = [row[0] for row in result]
            
            all_installed = True
            for enum in EXPECTED_ENUMS:
                if enum in installed_enums:
                    print_success(f"Enum type {enum} is created")
                else:
                    print_error(f"Enum type {enum} is NOT created")
                    all_installed = False
            
            return all_installed
    except Exception as e:
        print_error(f"Failed to check enum types: {e}")
        return False


def check_tables(engine):
    """Check if all expected tables exist with their columns."""
    print_header("CHECKING DATABASE TABLES")
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    tables_ok = True
    
    # Check each expected table
    for table in EXPECTED_TABLES:
        if table in existing_tables:
            columns = inspector.get_columns(table)
            print_success(f"Table {table} exists with {len(columns)} columns")
            
            # Check for primary key
            primary_keys = inspector.get_pk_constraint(table)
            if primary_keys and primary_keys['constrained_columns']:
                pk_cols = ', '.join(primary_keys['constrained_columns'])
                print_info(f"  Primary Key: {pk_cols}")
            else:
                print_warning(f"  Table {table} has no primary key!")
                tables_ok = False
        else:
            print_error(f"Table {table} does NOT exist")
            tables_ok = False
    
    return tables_ok


def check_relationships(engine):
    """Check if all expected relationships exist."""
    print_header("CHECKING TABLE RELATIONSHIPS")
    
    inspector = inspect(engine)
    all_ok = True
    
    for child_table, parent_table, fk_col, pk_col in RELATIONSHIPS:
        try:
            foreign_keys = inspector.get_foreign_keys(child_table)
            relationship_found = False
            
            for fk in foreign_keys:
                if (fk['referred_table'] == parent_table and 
                    fk_col in fk['constrained_columns'] and 
                    pk_col in fk['referred_columns']):
                    relationship_found = True
                    print_success(f"Relationship: {child_table}.{fk_col} -> {parent_table}.{pk_col}")
                    break
            
            if not relationship_found:
                print_error(f"Missing relationship: {child_table}.{fk_col} -> {parent_table}.{pk_col}")
                all_ok = False
                
        except Exception as e:
            print_error(f"Error checking relationship for {child_table}: {e}")
            all_ok = False
    
    return all_ok


def check_indexes(engine):
    """Check if all expected indexes exist."""
    print_header("CHECKING INDEXES")
    
    inspector = inspect(engine)
    all_ok = True
    
    all_indexes = {}
    for table in EXPECTED_TABLES:
        try:
            indexes = inspector.get_indexes(table)
            for idx in indexes:
                all_indexes[idx['name']] = {
                    'table': table,
                    'columns': idx['column_names'],
                    'unique': idx['unique']
                }
        except Exception as e:
            print_error(f"Error getting indexes for table {table}: {e}")
            all_ok = False
    
    # Check all expected indexes
    for idx_name in EXPECTED_INDEXES:
        if idx_name in all_indexes:
            idx = all_indexes[idx_name]
            print_success(f"Index {idx_name} exists on {idx['table']}({', '.join(idx['columns'])})")
        else:
            print_error(f"Index {idx_name} does NOT exist")
            all_ok = False
    
    return all_ok


def check_functions_and_triggers(engine):
    """Check if all expected functions and triggers exist."""
    print_header("CHECKING FUNCTIONS AND TRIGGERS")
    
    all_ok = True
    
    try:
        with engine.connect() as connection:
            # Check functions
            result = connection.execute(text(
                "SELECT proname FROM pg_proc JOIN pg_namespace n ON pronamespace = n.oid "
                "WHERE n.nspname = 'public'"
            ))
            functions = [row[0] for row in result]
            
            for func_name in EXPECTED_FUNCTIONS:
                if func_name in functions:
                    print_success(f"Function {func_name} exists")
                else:
                    print_error(f"Function {func_name} does NOT exist")
                    all_ok = False
            
            # Check triggers
            result = connection.execute(text(
                "SELECT tgname, relname FROM pg_trigger t JOIN pg_class c ON t.tgrelid = c.oid "
                "WHERE NOT tgisinternal"
            ))
            triggers = {f"{row[0]} on {row[1]}" for row in result}
            
            # Check update_modified_column trigger on all tables
            for table in EXPECTED_TABLES:
                trigger_name = f"update_{table}_modtime"
                full_trigger = f"{trigger_name} on {table}"
                
                if full_trigger in triggers:
                    print_success(f"Trigger {trigger_name} exists on table {table}")
                else:
                    print_error(f"Trigger {trigger_name} does NOT exist on table {table}")
                    all_ok = False
            
            # Check search vector trigger
            if "tsvector_update on legislation" in triggers:
                print_success("Trigger tsvector_update exists on legislation table")
            else:
                print_error("Trigger tsvector_update does NOT exist on legislation table")
                all_ok = False
                
    except Exception as e:
        print_error(f"Error checking functions and triggers: {e}")
        all_ok = False
    
    return all_ok


def test_basic_operations(engine):
    """Test basic CRUD operations on the database."""
    print_header("TESTING BASIC DATABASE OPERATIONS")
    
    all_ok = True
    test_user_email = f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
    
    try:
        with engine.begin() as connection:
            # INSERT test
            print_info("Testing INSERT operation...")
            result = connection.execute(text(
                "INSERT INTO users (email, name, is_active, role) "
                f"VALUES ('{test_user_email}', 'Test User', TRUE, 'user') RETURNING id"
            ))
            user_id = result.scalar()
            
            if user_id:
                print_success(f"INSERT successful. Created test user with ID: {user_id}")
            else:
                print_error("INSERT failed. No user ID returned.")
                all_ok = False
                return all_ok
            
            # SELECT test
            print_info("Testing SELECT operation...")
            result = connection.execute(text(
                f"SELECT id, email, name, role FROM users WHERE id = {user_id}"
            ))
            user = result.fetchone()
            
            if user and user[1] == test_user_email:
                print_success(f"SELECT successful. Retrieved user: {user[2]} ({user[1]})")
            else:
                print_error("SELECT failed. User not found or data mismatch.")
                all_ok = False
            
            # UPDATE test
            print_info("Testing UPDATE operation...")
            new_name = "Updated Test User"
            connection.execute(text(
                f"UPDATE users SET name = '{new_name}' WHERE id = {user_id}"
            ))
            
            # Verify update
            result = connection.execute(text(
                f"SELECT name FROM users WHERE id = {user_id}"
            ))
            updated_name = result.scalar()
            
            if updated_name == new_name:
                print_success(f"UPDATE successful. User name changed to: {updated_name}")
            else:
                print_error(f"UPDATE failed. Expected '{new_name}', got '{updated_name}'")
                all_ok = False
            
            # DELETE test
            print_info("Testing DELETE operation...")
            connection.execute(text(
                f"DELETE FROM users WHERE id = {user_id}"
            ))
            
            # Verify deletion
            result = connection.execute(text(
                f"SELECT COUNT(*) FROM users WHERE id = {user_id}"
            ))
            count = result.scalar()
            
            if count == 0:
                print_success("DELETE successful. Test user removed.")
            else:
                print_error("DELETE failed. User still exists in the database.")
                all_ok = False
    
    except Exception as e:
        print_error(f"Error during CRUD tests: {e}")
        all_ok = False
    
    return all_ok


def generate_report(all_checks):
    """Generate a summary report of all checks."""
    print_header("VERIFICATION SUMMARY REPORT")
    
    # Count checks
    total = len(all_checks)
    passed = sum(1 for check, result in all_checks.items() if result)
    failed = total - passed
    
    # Create a summary table
    rows = []
    for check, result in all_checks.items():
        status = f"{Fore.GREEN}PASSED" if result else f"{Fore.RED}FAILED"
        rows.append([check, f"{status}{Style.RESET_ALL}"])
    
    print(tabulate(rows, headers=["Check", "Status"], tablefmt="grid"))
    
    print("\n")
    if failed == 0:
        print_success(f"All {total} checks passed! The database is correctly configured.")
    else:
        print_warning(f"{passed}/{total} checks passed. {failed} checks failed.")
        print_info("Please fix the reported issues to ensure proper database functionality.")


def fix_issues(engine, all_checks):
    """Attempt to fix common issues."""
    print_header("ATTEMPTING TO FIX ISSUES")
    
    if all_checks['Extensions']:
        print_info("Extensions check passed. No fixes needed.")
    else:
        print_info("Attempting to create missing extensions...")
        try:
            with engine.begin() as connection:
                for ext in EXPECTED_EXTENSIONS:
                    connection.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
                print_success("Extensions fix attempted. Please run verification again.")
        except Exception as e:
            print_error(f"Failed to fix extensions: {e}")
    
    # Check for missing triggers
    if not all_checks['Functions and Triggers']:
        print_info("Attempting to recreate missing triggers...")
        try:
            with engine.begin() as connection:
                # Recreate update_modified_column function if needed
                connection.execute(text("""
                    CREATE OR REPLACE FUNCTION update_modified_column() RETURNS trigger AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                """))
                
                # Recreate legislation_search_update_trigger function if needed
                connection.execute(text("""
                    CREATE OR REPLACE FUNCTION legislation_search_update_trigger() RETURNS trigger AS $$
                    BEGIN
                        NEW.search_vector = 
                        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
                        RETURN NEW;
                    END
                    $$ LANGUAGE plpgsql;
                """))
                
                # Create missing triggers
                for table in EXPECTED_TABLES:
                    connection.execute(text(f"""
                        DROP TRIGGER IF EXISTS update_{table}_modtime ON {table};
                        CREATE TRIGGER update_{table}_modtime
                        BEFORE UPDATE ON {table}
                        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
                    """))
                
                # Create legislation search trigger
                connection.execute(text("""
                    DROP TRIGGER IF EXISTS tsvector_update ON legislation;
                    CREATE TRIGGER tsvector_update
                    BEFORE INSERT OR UPDATE ON legislation
                    FOR EACH ROW EXECUTE FUNCTION legislation_search_update_trigger();
                """))
                
                print_success("Triggers fix attempted. Please run verification again.")
        except Exception as e:
            print_error(f"Failed to fix triggers: {e}")
    
    print_info("Some issues may require manual intervention. Check the verification report.")


def main():
    """Main function to verify the database."""
    parser = argparse.ArgumentParser(description='Verify PolicyPulse database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix common issues')
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    print_header("POLICYPULSE DATABASE VERIFICATION")
    print(f"Database URL: {DATABASE_URL}")
    print(f"Starting verification: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize engine
    engine = connect_to_database()
    if not engine:
        return False
    
    # Run all checks
    all_checks = {
        'Connection': test_connection(engine),
        'Extensions': check_extensions(engine),
        'Enum Types': check_enums(engine),
        'Tables': check_tables(engine),
        'Relationships': check_relationships(engine),
        'Indexes': check_indexes(engine),
        'Functions and Triggers': check_functions_and_triggers(engine),
        'Basic Operations': test_basic_operations(engine)
    }
    
    # Generate summary report
    generate_report(all_checks)
    
    # Try to fix issues if requested
    if args.fix and not all(all_checks.values()):
        fix_issues(engine, all_checks)
    
    return all(all_checks.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)