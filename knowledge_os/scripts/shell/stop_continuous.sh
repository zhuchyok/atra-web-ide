#!/bin/bash
# Stop continuous autonomous trading system helpers

set -euo pipefail

printf "🛑 Stopping Continuous Trading System...\n"

pkill -f "scripts/continuous_runner.py" || true
pkill -f "scripts/external_integrations.py" || true

printf "✅ System stopped successfully\n"
