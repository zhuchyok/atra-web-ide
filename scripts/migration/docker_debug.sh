#!/bin/bash
# Краткая диагностика docker и агентов. Таймаут 25 с.
D="${HOME}/migration/up_agents_debug.txt"
echo "=== docker ps -a ===" > "$D"
( perl -e 'alarm 8; exec @ARGV' - docker ps -a 2>&1 ) >> "$D" || echo "(timeout/error)" >> "$D"
echo "" >> "$D"
echo "=== victoria-agent (tail 20) ===" >> "$D"
( perl -e 'alarm 6; exec @ARGV' - docker logs victoria-agent 2>&1 | tail -20 ) >> "$D" || echo "(timeout/error)" >> "$D"
echo "" >> "$D"
echo "=== veronica-agent (tail 20) ===" >> "$D"
( perl -e 'alarm 6; exec @ARGV' - docker logs veronica-agent 2>&1 | tail -20 ) >> "$D" || echo "(timeout/error)" >> "$D"
cat "$D"
