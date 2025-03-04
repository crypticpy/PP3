# Dockerfile for PolicyPulse application
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        libpq-dev \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Copy database scripts
COPY db/policypulse_schema.sql /app/db/
COPY db/db_setup.py /app/db/
COPY db/db_verify.py /app/db/
COPY docker/entrypoint.sh /app/

# Make scripts executable
RUN chmod +x /app/docker/entrypoint.sh

# Specify the entrypoint script
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Default command
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]