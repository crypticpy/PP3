# tools.Dockerfile for PolicyPulse database management tools
FROM python:3.9-slim

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
        vim \
        less \
        curl \
        iputils-ping \
        procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for database tools
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy database management scripts
COPY policypulse_schema.sql /app/
COPY db_setup.py /app/
COPY db_verify.py /app/
COPY cli.py /app/

# Create an entry script for database tools
RUN echo '#!/bin/bash\n\
echo "PolicyPulse Database Tools Container"\n\
echo "=================================="\n\
echo "Available commands:"\n\
echo "  python db_verify.py --verbose    : Verify database setup"\n\
echo "  python db_setup.py --recreate    : Recreate the database"\n\
echo "  python cli.py                    : Run the PolicyPulse CLI"\n\
echo "  psql -h db -U admin -d policypulse : Connect to the database directly"\n\
echo\n\
exec bash\n\
' > /app/tools_entrypoint.sh \
    && chmod +x /app/tools_entrypoint.sh

# Set entry point
ENTRYPOINT ["/app/tools_entrypoint.sh"]