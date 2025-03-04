#!/bin/bash
set -e

# Function to wait for database to be ready
wait_for_db() {
  echo "Waiting for database to be ready..."
  while ! pg_isready -h db -p 5432 -U admin -d policypulse > /dev/null 2>&1; do
    echo "Database not ready yet, retrying..."
    sleep 1
  done
  echo "Database is ready!"
}

# Function to set up the database
setup_db() {
  echo "Setting up the database..."
  python /app/db_setup.py
  if [ $? -eq 0 ]; then
    echo "Database setup completed successfully."
    return 0
  else
    echo "Database setup failed. Checking database status..."
    python /app/db_verify.py
    return 1
  fi
}

# Wait for the database service to be available
wait_for_db

# Run database setup
setup_db

# Run database verification in verbose mode
echo "Verifying database setup..."
python /app/db_verify.py --verbose

# Execute the provided command or default to starting the API server
exec "$@"