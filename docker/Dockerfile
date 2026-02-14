# Arrmate Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the package
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 arrmate && \
    chown -R arrmate:arrmate /app

USER arrmate

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run API server
CMD ["uvicorn", "arrmate.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
