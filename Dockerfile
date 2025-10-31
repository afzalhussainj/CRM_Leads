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
RUN useradd -m appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command (Render startCommand can override)
# Run from /app where crm/ is a direct subdirectory
CMD ["gunicorn", "crm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]


