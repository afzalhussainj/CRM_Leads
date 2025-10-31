# Use Python 3.11 slim image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONPATH=/app

WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better caching)
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the CRM directory contents to /app (so crm/ module is directly accessible)
COPY CRM/ ./

# Create non-root user
RUN useradd -m appuser

# Create staticfiles directory and make startup script executable
RUN mkdir -p /app/staticfiles && \
    chmod +x /app/start.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Use startup script that runs migrations before starting server
CMD ["/app/start.sh"]


