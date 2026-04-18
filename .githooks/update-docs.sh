#!/bin/bash
# Auto-update MASTER_REFERENCE.md after commits
# Add this to .git/hooks/post-commit

DOCS_DIR="docs"
REF_FILE="$DOCS_DIR/MASTER_REFERENCE.md"
LAST_VERSION=$(grep -m1 'v[0-9]*' "$REF_FILE" | grep -o 'v[0-9]*')
CURRENT_DATE=$(date +%Y-%m-%d)

echo "Last version: $LAST_VERSION"
echo "Current date: $CURRENT_DATE"

# Check if version needs update (if commits made after last date in file)
if ! grep -q "$CURRENT_DATE" "$REF_FILE"; then
    echo "⚠️ New day - MASTER_REFERENCE.md may need update"
    echo "Run: Edit docs/MASTER_REFERENCE.md manually or add auto-update logic"
fi