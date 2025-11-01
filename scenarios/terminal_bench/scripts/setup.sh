#!/bin/bash
# This script installs dependencies and downloads the dataset for terminal-bench

set -e
echo "=================================="
echo "Terminal-Bench Green Agent Setup"
echo "=================================="
echo

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Not in a virtual environment!"
    echo "   Recommended: python -m venv venv && source venv/bin/activate"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo
echo "📥 Setting up terminal-bench dataset..."
python scripts/setup_dataset.py

echo
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo
echo "Next steps:"
echo "1. Ensure Docker is installed and running: docker ps"
echo "2. Create .env file: cp .env.example .env"
echo "3. Add your OpenAI API key to .env"
echo ""
echo "4. Start the agents and run evaluation:"
echo "   Terminal 1: python -m white_agent"
echo "   Terminal 2: python -m src.green_agent"
echo "   Terminal 3: python -m src.kickoff"
echo

