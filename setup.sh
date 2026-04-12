#!/bin/bash

# Smart Parking System - Complete Setup and Run Script

set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Smart Parking System - Setup & Run"
echo "=========================================="
echo ""

# Check Python
echo "✓ Checking Python..."
python3 --version || { echo "✗ Python 3 not found"; exit 1; }

# Check Node.js
echo "✓ Checking Node.js..."
node --version || { echo "✗ Node.js not found"; exit 1; }

# Install Backend Dependencies
echo ""
echo "📦 Installing Backend Dependencies..."
cd "$PROJECT_ROOT/backend"
pip install -q -r requirements.txt
echo "✓ Backend dependencies installed"

# Install Frontend Dependencies
echo ""
echo "📦 Installing Frontend Dependencies..."
cd "$PROJECT_ROOT/frontend"
npm install --prefer-offline --no-audit > /dev/null 2>&1 || npm install
echo "✓ Frontend dependencies installed"

# Summary
echo ""
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "To start the system:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend"
echo "  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd frontend"
echo "  npm start"
echo ""
echo "Then open: http://localhost:3000"
echo ""
echo "API Docs: http://localhost:8000/docs"
echo ""
