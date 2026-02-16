#!/bin/bash
# [SINGULARITY 10.0+] Setup script for Browser Operator (Veronica)
# Installs Playwright browsers and system dependencies

set -e

echo "🚀 [BROWSER OPERATOR] Starting setup..."

# 1. Install system dependencies for Playwright (if running on host or in a custom Dockerfile)
# Note: In our current Dockerfile (infrastructure/docker/agents/Dockerfile), we might need to add these.
# For now, we assume the base image has common libs or we'll add them to the Dockerfile later.

# 2. Install Playwright browsers
echo "🌐 [BROWSER OPERATOR] Installing Playwright browsers..."
pip install playwright
python3 -m playwright install chromium --with-deps

# 3. Verify installation
echo "✅ [BROWSER OPERATOR] Setup complete. Verifying..."
python3 -c "from playwright.sync_api import sync_playwright; print('Playwright is ready!')"

echo "🎉 [BROWSER OPERATOR] Ready to operate."
