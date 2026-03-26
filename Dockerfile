FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl nginx \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (playwright excluded for cloud deployment)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y playwright 2>/dev/null; true

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/sites-available/default

# Application code
COPY . .

# Data directory and execution permissions
RUN mkdir -p /app/data
RUN chmod +x start.sh

# Expose combined server port (Render uses PORT env, default 10000)
EXPOSE 10000

# Health check via FastAPI
HEALTHCHECK CMD curl --fail http://localhost:10000/api/health || exit 1

# Run combined server (Nginx + FastAPI + Streamlit)
CMD ["./start.sh"]
