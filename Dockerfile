FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN DEBIAN_FRONTEND="noninteractive" apt-get update && \
    apt-get install -y --no-install-recommends \
      tor \
      build-essential \
      curl \
      libssl-dev \
      libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy uv configuration files and metadata files (required by pyproject.toml)
COPY pyproject.toml uv.lock LICENSE README.md ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

COPY . .

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["uv", "run", "/app/entrypoint.sh"]

CMD []