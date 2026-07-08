#!/bin/bash
set -e

pip install -r requirements_app.txt --user
streamlit run app.py \
    --server.port 8888 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
