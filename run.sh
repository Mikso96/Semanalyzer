#!/bin/bash

echo "Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Starting Semanalyzer..."
echo "Opening browser..."

# Open browser after delay (different for Mac vs Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2 && open http://localhost:8501 &
else
    sleep 2 && xdg-open http://localhost:8501 &
fi

streamlit run app.py
