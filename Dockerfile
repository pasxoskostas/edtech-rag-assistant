FROM python:3.12-slim

# Εγκατάσταση του επίσημου uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Εγκατάσταση μόνο των εξαρτήσεων (χωρίς build του root package)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Αντιγραφή του κώδικα της εφαρμογής
COPY main.py app.py ingest.py notes.txt ./

EXPOSE 8000 8501