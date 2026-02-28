FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg for H.265 transcoding)
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt ./
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies (requirements.txt first to pin security-patched versions)
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /data

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Entrypoint fixes /data ownership then drops to arrmate user
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "arrmate.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
