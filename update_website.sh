#!/bin/bash
set -e

WEBSITE_DIR="${WEBSITE_DIR:-$HOME/spl1ceAI-website}"

if [ ! -d "$WEBSITE_DIR" ]; then
    echo "❌ Error: Directory $WEBSITE_DIR not found."
    exit 1
fi

echo "Pulling latest code in $WEBSITE_DIR..."
cd "$WEBSITE_DIR"

git pull origin main

echo "Installing dependencies..."
npm install --no-audit --no-fund

echo "Building production bundle..."
npm run build

echo "✅ Website successfully updated and rebuilt."
