FROM python:3.10-slim-bullseye AS builder

RUN DEBIAN_FRONTEND="noninteractive" apt-get update && \
    apt-get install -y --no-install-recommends \
      tor \
      build-essential \
      curl \
      libssl-dev \
      libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt


COPY . .

EXPOSE 8501

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh", "ui", "--ui-port", "8501", "--ui-host", "0.0.0.0"]