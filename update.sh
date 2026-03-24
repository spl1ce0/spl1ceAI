#!/bin/bash

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
cd "$SCRIPTPATH"

echo "Updating code..."

if git pull origin main; then
    echo "Updating dependencies..."
    ./venv/bin/pip install -r requirements.txt

    echo "✅ Update successful."
    echo "Note: This script requires the systemd service to be configured with 'Restart=always'."
    echo "Killing the process, service should restart automatically..."
    sleep 3
    pkill -f bot.py
else
    echo "❌ Git pull failed! Staying on current version to avoid crash."
    exit 1
fi
