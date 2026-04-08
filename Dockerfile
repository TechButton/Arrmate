FROM python:3.15-rc-alpine3.22

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg for H.265 transcoding, su-exec for privilege drop)
RUN apk add --no-cache gcc ffmpeg su-exec musl-dev

# Copy project files
COPY requirements.txt ./
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies (requirements.txt first to pin security-patched versions)
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

# Create data directory and non-root user
# The entrypoint re-chowns /data at runtime (named volumes are created as root),
# then drops privileges via gosu before starting the app.
RUN mkdir -p /data \
    && addgroup -S arrmate \
    && adduser -S -G arrmate -h /app -s /sbin/nologin arrmate \
    && chown -R arrmate:arrmate /app /data

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
    CMD su-exec arrmate python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "arrmate.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
