#!/usr/bin/env python3
"""
Отправка алертов о качестве в Telegram/Slack.
Использование: python3 scripts/send_quality_alert.py backend/validation_report.json
"""
import argparse
import json
import os
import sys
from pathlib import Path
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

def send_telegram_alert(message: str):
    """Отправка алерта в Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не заданы")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def send_slack_alert(message: str):
    """Отправка алерта в Slack."""
    if not SLACK_WEBHOOK_URL:
        print("⚠️ SLACK_WEBHOOK_URL не задан")
        return False
    payload = {"text": message, "username": "Quality Monitor", "icon_emoji": ":warning:"}
    try:
        r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return False

def build_alert_message(report_path: Path) -> str:
    """Формирует сообщение алерта из отчёта."""
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    m = data.get("avg_metrics", {})
    passed = data.get("passed", False)
    icon = "✅" if passed else "⚠️"
    msg = f"""{icon} *Отчёт качества RAG*

📊 *Метрики:*
• Faithfulness: {m.get('faithfulness', 0):.1%}
• Relevance: {m.get('relevance', 0):.1%}
• Coherence: {m.get('coherence', 0):.1%}
• Запросов: {data.get('total_queries', 0)}

🎯 *Статус:* {'Порог пройден' if passed else 'Требуется улучшение'}

🔗 Отчёт: `{report_path.name}`
"""
    # Добавляем топ-3 проблемных запроса если не прошли
    if not passed:
        results = data.get("results", [])[:3]
        if results:
            msg += "\n📌 *Проблемные запросы:*\n"
            for r in results:
                rel = r["metrics"].get("relevance", 0)
                msg += f"• {r['query'][:40]}... (rel={rel:.2f})\n"
    return msg

def main():
    parser = argparse.ArgumentParser(description="Send quality alerts")
    parser.add_argument("report", help="Path to validation_report.json")
    parser.add_argument("--telegram", action="store_true", help="Send to Telegram")
    parser.add_argument("--slack", action="store_true", help="Send to Slack")
    args = parser.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"❌ Report not found: {path}")
        return 1

    message = build_alert_message(path)
    print("📤 Отправка алерта...\n")
    print(message)

    sent = False
    if args.telegram or (not args.slack and TELEGRAM_BOT_TOKEN):
        if send_telegram_alert(message):
            print("✅ Отправлено в Telegram")
            sent = True
    if args.slack or (not args.telegram and SLACK_WEBHOOK_URL):
        if send_slack_alert(message):
            print("✅ Отправлено в Slack")
            sent = True

    if not sent:
        print("⚠️ Алерты не отправлены (нет настроенных каналов)")
        print("Настройте переменные: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID или SLACK_WEBHOOK_URL")

    return 0

if __name__ == "__main__":
    sys.exit(main())
