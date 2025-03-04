#!/bin/bash
# Tools container entrypoint script for PolicyPulse

# Print a welcome message with available commands
echo "
PolicyPulse Database Tools Container
===================================

Available commands:

  Database Management:
    python /app/db/db_verify.py --verbose    : Verify database setup
    python /app/db/db_setup.py --recreate    : Recreate the database
    python /app/db/db_verify.py --fix        : Attempt to fix database issues

  Application Management:
    python /app/app/cli.py                   : Run the PolicyPulse CLI
    python /app/app/cli.py seed              : Seed the database with test data
    python /app/app/cli.py sync              : Sync data from external sources
    python /app/app/cli.py analyze-pending   : Analyze pending legislation

  Database Connection:
    psql -h db -U admin -d policypulse       : Connect to the database directly

  Container Management:
    exit                                      : Exit the container

To see detailed help for a command, add --help, for example:
    python /app/app/cli.py --help
"

# Function to wait for database to be ready
wait_for_db() {
  echo "Checking database connection..."
  for i in {1..5}; do
    if pg_isready -h db -p 5432 -U admin -d policypulse > /dev/null 2>&1; then
      echo "Database is ready!"
      return 0
    fi
    echo "Database not ready yet, waiting... (attempt $i/5)"
    sleep 2
  done
  echo "Warning: Database does not appear to be ready. Some commands may fail."
  return 1
}

# Wait for database to be ready in background to not block the shell
wait_for_db &

# Start an interactive shell
exec bash