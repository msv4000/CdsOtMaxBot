#!/usr/bin/env python3
"""
Проверка подключения к API платформы MAX и получение информации о боте.
Использование:
  MAX_BOT_TOKEN="your_token" python3 get_me.py
  или запуск на сервере, где есть /etc/max-bot.env
"""
import json
import os
import urllib.request

TOKEN = os.environ.get("MAX_BOT_TOKEN", "")
if not TOKEN and os.path.exists("/etc/max-bot.env"):
    with open("/etc/max-bot.env") as f:
        for line in f:
            if line.startswith("MAX_BOT_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()

if not TOKEN:
    print("Ошибка: не задан MAX_BOT_TOKEN")
    exit(1)

req = urllib.request.Request(
    "https://platform-api2.max.ru/me",
    headers={"Authorization": TOKEN}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))
