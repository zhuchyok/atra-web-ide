#!/usr/bin/env bash
# Верификация всех сайтов Setki21: для каждого хоста проверяем, что API возвращает JSON tenant config.
# Запуск из корня atra-web-ide. Требуется SSH на VDS (по умолчанию root@45.10.43.248).
# См. docs/SETKI21_NPM_SOURCE_OF_TRUTH.md

set -e
VDS="${VDS:-root@45.10.43.248}"
API_URL="http://setki21-api-new:8080/api/v1/tenant/config"

hosts=(
  "www.setki21.ru"
  "setki21.ru"
  "xn--e1agaahbbnszfhh.xn--p1ai"
  "www.xn--e1agaahbbnszfhh.xn--p1ai"
  "setkimoskitki.ru"
  "www.setkimoskitki.ru"
)

failed=0
for host in "${hosts[@]}"; do
  out=$(ssh "$VDS" "docker exec atra-nginx-proxy curl -s -o /dev/null -w '%{http_code}' -H 'Host: $host' $API_URL" 2>/dev/null || echo "000")
  if [[ "$out" == "200" ]]; then
    echo "OK   Host: $host"
  else
    echo "FAIL Host: $host (HTTP $out)"
    ((failed++)) || true
  fi
done

if [[ $failed -gt 0 ]]; then
  echo ""
  echo "Провалено проверок: $failed. См. docs/runbooks/SETKI21_WHITE_SCREEN.md и docs/SETKI21_NPM_SOURCE_OF_TRUTH.md"
  exit 1
fi
echo ""
echo "Все сайты отдают tenant config (HTTP 200)."
