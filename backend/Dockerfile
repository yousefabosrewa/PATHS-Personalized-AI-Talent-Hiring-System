# PATHS backend — FastAPI service image.
FROM python:3.11-slim

WORKDIR /app

# Cleaner logs + no .pyc clutter inside the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# System build deps (psycopg, etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (see .dockerignore for what is excluded).
COPY . .

# Normalise line endings (in case of a Windows checkout) and make the
# entrypoint executable.
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000

# Applies migrations, then starts Uvicorn. See docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
