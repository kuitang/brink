# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Install curl for Claude Code native installer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI using native installer (no Node.js required)
# The installer puts claude in ~/.local/bin
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/root/.local/bin:${PATH}"

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY README.md .

# Install dependencies with webapp extras
# Try frozen first (for reproducible builds), fall back to non-frozen
RUN uv sync --extra webapp --no-dev --frozen || uv sync --extra webapp --no-dev

# Install gunicorn for production WSGI server
RUN uv pip install gunicorn

# Copy application code
COPY src/ src/

# Copy scenarios and game manual (now tracked in git)
COPY scenarios/ scenarios/
COPY GAME_MANUAL.md .

# Create data directory for SQLite (will be mounted as volume in production)
RUN mkdir -p /data

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Verify Claude Code CLI is installed (build-time check)
RUN claude --version

# Health check using Python (curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# Start command - gunicorn with Flask app factory
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "brinksmanship.webapp.app:create_app()"]
