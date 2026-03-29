FROM registry.starbluesolutions.net/library/python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install uv

# Copy project files
COPY pyproject.toml README.md alembic.ini ./
COPY src/ src/
COPY alembic/ alembic/
COPY deploy/healthcheck.py /app/healthcheck.py

# Install dependencies
RUN uv pip install --system .

# Create non-root user
RUN useradd -m -u 1000 engram
USER engram

# Run the server
EXPOSE 8800
CMD ["python", "-m", "engram.cli"]
