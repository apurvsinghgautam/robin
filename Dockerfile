# Stage 1: Builder
FROM python:3.10-slim AS builder

# Install system dependencies for building wheels, and curl
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    tor \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy project metadata and source
COPY pyproject.toml LICENSE README.md uv.lock ./
COPY src/ ./src/
COPY entrypoint.sh ./
COPY .github/ ./.github/

# Install dependencies
RUN uv sync --no-dev

# Stage 2: Final Image
FROM python:3.10-slim

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    tor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create the directory for uv installation and install it
RUN mkdir -p /root/.local/bin && \
    curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH:/app/.venv/bin"

# Copy installed dependencies from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code and metadata
COPY --from=builder /app/src/ ./src/
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/LICENSE /app/LICENSE
COPY --from=builder /app/README.md /app/README.md
COPY --from=builder /app/uv.lock /app/uv.lock
COPY --from=builder /app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy GitHub assets for UI
COPY --from=builder /app/.github/ /.github/

ENTRYPOINT ["/entrypoint.sh"]

CMD ["robin"]
