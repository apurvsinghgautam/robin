FROM python:3.11-slim AS builder

# The MCP registry reads this label off the published image to confirm it
# belongs to the io.github.apurvsinghgautam/robin server entry.
LABEL io.modelcontextprotocol.server.name="io.github.apurvsinghgautam/robin"

RUN DEBIAN_FRONTEND="noninteractive" apt-get update && \
    apt-get install -y --no-install-recommends \
      tor \
      build-essential \
      curl \
      libssl-dev \
      libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Everything past the install runs as this user. UID/GID 1000 is the first
# non-system id on Linux, so a bind mount created by a typical desktop user is
# already writable without anyone passing --user.
RUN groupadd --gid 1000 robin && \
    useradd --uid 1000 --gid 1000 --create-home --home-dir /home/robin robin

ENV HOME=/home/robin

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY --chown=robin:robin . .

# Pre-create these directories robin-owned. Tor requires 0700 on $HOME/.tor,
# and a named volume takes its owner from the image directory it mounts over,
# or root when the image has none, which leaves it unwritable to UID 1000.
RUN chmod +x /app/entrypoint.sh && \
    install -d -m 0700 -o robin -g robin /home/robin/.tor && \
    install -d -m 0700 -o robin -g robin /home/robin/.robin && \
    install -d -m 0755 -o robin -g robin /app/investigations && \
    chown robin:robin /app

# 8501 is the Streamlit UI. The MCP server speaks over stdio and needs no port.
# Tor's SOCKS port stays unpublished on purpose: it is an internal proxy, and
# exposing it would turn the container into an open proxy on the host network.
EXPOSE 8501

USER robin

ENTRYPOINT ["/app/entrypoint.sh"]
