FROM python:3.11-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy pyproject.toml and uv.lock if you have them, otherwise just install directly
# Since we used uv init, we can just copy everything
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy source code and data
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
