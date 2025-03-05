
#!/usr/bin/env python
"""
fix_enum_values.py

Script to check and fix enum values in the database.
This script:
1. Connects to the database
2. Checks if the data_source_enum exists and has the correct values
3. If not, updates the enum values to match the code
"""

import os
import sys
import logging
from sqlalchemy import text

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import from app
from app.db_connection import get_connection, release_connection
from app.models import init_db

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def check_and_fix_enums():
    """
    Check and fix enum values in the database to match the code.
    """
    logger.info("Checking enum values in the database...")
    
    conn = None
    try:
        # Initialize database session
        db_session_factory = init_db()
        db_session = db_session_factory()
        
        # Get direct connection for raw SQL
        conn = db_session.connection().connection
        
        # Check if data_source_enum exists and has the correct values
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    t.typname AS enum_name,
                    e.enumlabel AS enum_value
                FROM 
                    pg_type t 
                    JOIN pg_enum e ON t.oid = e.enumtypid 
                WHERE 
                    t.typname = 'data_source_enum'
                ORDER BY 
                    e.enumsortorder
            """)
            
            enum_values = [row[1] for row in cursor.fetchall()]
            logger.info(f"Current data_source_enum values: {enum_values}")
            
            # Check if 'legiscan' is in the values
            if enum_values and 'legiscan' not in enum_values:
                logger.info("Enum value 'legiscan' not found, updating enum...")
                
                # Create backup of legislation table
                db_session.execute(text("CREATE TABLE legislation_backup AS SELECT * FROM legislation"))
                logger.info("Created backup table: legislation_backup")
                
                # Update the enum type
                db_session.execute(text("""
                    -- Create a new enum type with the correct values
                    CREATE TYPE data_source_enum_new AS ENUM ('legiscan', 'congress_gov', 'other');
                    
                    -- Alter the column to use the new enum type (this may require modifications to data)
                    ALTER TABLE legislation 
                    ALTER COLUMN data_source TYPE data_source_enum_new 
                    USING (
                        CASE 
                            WHEN data_source::text = 'LEGISCAN' THEN 'legiscan'::data_source_enum_new
                            WHEN data_source::text = 'CONGRESS_GOV' THEN 'congress_gov'::data_source_enum_new
                            ELSE 'other'::data_source_enum_new
                        END
                    );
                    
                    -- Drop the old enum type
                    DROP TYPE data_source_enum;
                    
                    -- Rename the new enum type to the original name
                    ALTER TYPE data_source_enum_new RENAME TO data_source_enum;
                """))
                
                logger.info("Updated data_source_enum values to match code")
            elif not enum_values:
                logger.warning("data_source_enum not found in the database")
            else:
                logger.info("data_source_enum values already match the code")
            
        db_session.commit()
        logger.info("Enum check and fix complete")
        
    except Exception as e:
        logger.error(f"Error checking or fixing enum values: {e}", exc_info=True)
        if db_session:
            db_session.rollback()
    finally:
        if db_session:
            db_session.close()

if __name__ == "__main__":
    check_and_fix_enums()
    logger.info("Script complete")
