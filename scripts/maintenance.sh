#!/bin/bash
# [v149.34] Техокно: ./maintenance.sh on|off|status
case "${1:-status}" in
  on) touch /tmp/atra_maintenance_mode; echo "$(date '+%F %T') MAINTENANCE ON ($2)" >> ~/Library/Logs/atra/maintenance.log; echo "акторы на паузе" ;;
  off) rm -f /tmp/atra_maintenance_mode; echo "$(date '+%F %T') MAINTENANCE OFF" >> ~/Library/Logs/atra/maintenance.log; echo "акторы возвращены" ;;
  *) [ -f /tmp/atra_maintenance_mode ] && echo "ВКЛЮЧЁН" || echo "выключен" ;;
esac
