#!/bin/bash

# Start FastAPI server for REST endpoints
echo "Starting FastAPI on port 8000..."
uvicorn api_server:app --host 127.0.0.1 --port 8000 &

# Start Streamlit
echo "Starting Streamlit on port 8501..."
streamlit run app.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true --browser.gatherUsageStats=false &

# Start Nginx in the foreground
echo "Starting Nginx on port 10000..."
nginx -g 'daemon off;'
