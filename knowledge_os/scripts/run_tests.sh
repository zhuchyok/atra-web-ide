#!/bin/bash
# Скрипт для запуска unit tests с coverage

set -e

echo "🧪 Running ATRA Unit Tests..."
echo "================================"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run tests with coverage
echo ""
echo "📊 Running tests with coverage..."
pytest tests/unit/ \
    -v \
    --tb=short \
    --cov=. \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml

# Show summary
echo ""
echo "================================"
echo "✅ Tests complete!"
echo ""
echo "📊 Coverage report saved to htmlcov/index.html"
echo "📊 Open with: open htmlcov/index.html"
echo ""

# Show quick stats
echo "📈 Quick Stats:"
pytest tests/unit/ -q --tb=no 2>&1 | tail -3
