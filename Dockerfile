FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (playwright excluded for cloud deployment)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y playwright 2>/dev/null; true

# Application code
COPY . .

# Data directory
RUN mkdir -p /app/data

# Expose combined server port (Render uses PORT env, default 10000)
EXPOSE 10000

# Health check via FastAPI
HEALTHCHECK CMD curl --fail http://localhost:10000/api/health || exit 1

# Run combined server (FastAPI + Streamlit)
CMD ["python", "server.py"]
