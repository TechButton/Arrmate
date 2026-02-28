# Arrmate Dockerfile
FROM python:3.15-rc-alpine3.22

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apk add --no-cache curl

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the package
RUN pip install -e .

# Create data directory
RUN mkdir -p /data

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "arrmate.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
