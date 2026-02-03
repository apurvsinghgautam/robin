FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install backend requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy and install main requirements (for agent SDK)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Robin agent code
COPY agent /app/agent
COPY core /app/core
COPY config.py /app/config.py

# Copy backend code
COPY backend/app /app/backend/app

# Set Python path
ENV PYTHONPATH=/app:/app/backend

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
