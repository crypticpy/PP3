
#!/bin/bash
# Initialize and verify the PolicyPulse database

echo "Initializing PolicyPulse database..."

# Check if DATABASE_URL environment variable is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable not set"
    echo "Please set up a PostgreSQL database in Replit first"
    exit 1
fi

# Run the database setup script
echo "Setting up database schema..."
python db/db_setup.py

if [ $? -ne 0 ]; then
    echo "ERROR: Database setup failed. See logs above for details."
    exit 1
fi

# Verify database setup
echo "Verifying database setup..."
python db/db_verify.py --verbose

if [ $? -ne 0 ]; then
    echo "WARNING: Database verification reported issues. The application may not function correctly."
else
    echo "Database initialization complete!"
    echo "The PolicyPulse database is ready to use."
fi
