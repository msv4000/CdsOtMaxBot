#!/usr/bin/env python3
"""
Скрипт проверки логики поиска маршрутов.
Запуск:
  python test_search.py [запрос]
"""
import sys
import os

# Подключаем корневой каталог
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import search_routes, BASE_ROUTE_URL

test_queries = sys.argv[1:] if len(sys.argv) > 1 else ["1", "4", "11", "101", "2", "троллейбус 2", "1а", "999"]

for q in test_queries:
    matches = search_routes(q)
    print(f"\n--- Запрос: '{q}' ---")
    if not matches:
        print("  ❌ Не найдено")
    elif len(matches) == 1:
        r = matches[0]
        v_name = "Автобус" if r.get('vehicle') == 1 else "Троллейбус"
        print(f"  ✅ Найден 1 маршрут: {v_name} №{r['number']} (id={r['id']})")
        print(f"     Ссылка: {BASE_ROUTE_URL.format(r['id'])}")
    else:
        print(f"  ⚠️ Найдено несколько маршрутов ({len(matches)}):")
        for r in matches:
            v_name = "Автобус" if r.get('vehicle') == 1 else "Троллейбус"
            print(f"     - {v_name} №{r['number']} (id={r['id']})")
