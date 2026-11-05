#!/usr/bin/env python3
import json
import os
import re
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

import timetable_service

API = "https://platform-api2.max.ru"
TOKEN = os.environ.get("MAX_BOT_TOKEN", "")
SECRET = os.environ.get("MAX_WEBHOOK_SECRET", "")

BASE_ROUTE_URL = "https://transport.nov.ru/timetable/table.html?route={}"
MAX_TICKET_BOT_URL = "https://max.ru/id5406119655_1_bot"
PDF_TICKETS_URL = "https://bot-api.transport.nov.ru/media/vidy_proedzdnih.pdf"
IMG_TOPUP_URL = "https://bot-api.transport.nov.ru/media/popolnenie.png"

def button(text, payload):
    return {"type": "callback", "text": text, "payload": payload}

def link_button(text, url):
    return {"type": "link", "text": text, "url": url}

def keyboard(rows):
    return [{
        "type": "inline_keyboard",
        "payload": {"buttons": rows}
    }]

def main_menu():
    text = (
        "Здравствуйте!\n"
        "Рады приветствовать Вас в чат - бот «Транспорт Великого Новгорода».\n"
        "Я Ваш виртуальный помощник по городскому общественному транспорту."
    )
    buttons = [
        [button("Расписание движения городских маршрутов", "ask_route")],
        [button("Как приобрести билет посредством чат-бота", "how_to_buy")],
        [button("Как пополнить проездные билеты в мобильном приложении «Транспортная карта»", "how_to_topup")],
        [button("Узнать стоимость проезда", "fares")],
        [button("Узнать виды проездных билетов и их стоимость", "ticket_types")],
        [button("Перевозчики", "carriers")],
        [button("Полезная информация", "useful_info")]
    ]
    return {
        "text": text,
        "attachments": keyboard(buttons)
    }

def ask_route_menu():
    return {
        "text": (
            "🚌 Введите номер интересующего маршрута в чат\n"
            "(например: 1, 4, 11, 101 или троллейбус 2):"
        ),
        "attachments": keyboard([
            [button("🏠 Главное меню", "menu")]
        ])
    }

def route_link_message(route):
    vehicle_icon = "🚌" if route.get('vehicle') == 1 else "🚎"
    vehicle_name = "Автобус" if route.get('vehicle') == 1 else "Троллейбус"
    url = BASE_ROUTE_URL.format(route['id'])

    route_points = ""
    if route.get('point1') and route.get('point2'):
        route_points = f"\n{route['point1']} ⇄ {route['point2']}"

    text = (
        f"{vehicle_icon} **{vehicle_name} №{route['number']}**{route_points}\n\n"
        f"Расписание движения доступно на сайте:\n{url}"
    )
    attachments = keyboard([
        [link_button("🌐 Открыть расписание на сайте", url)],
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def route_not_found_message(text_entered):
    return {
        "text": (
            f"Маршрут «{text_entered}» не найден.\n\n"
            "Пожалуйста, проверьте номер и введите его снова (например: 1, 4, 11 или 101):"
        ),
        "attachments": keyboard([
            [button("🏠 Главное меню", "menu")]
        ])
    }

def disambiguate_menu(matched_routes):
    rows = []
    for r in matched_routes:
        v_icon = "🚌" if r.get('vehicle') == 1 else "🚎"
        v_name = "Автобус" if r.get('vehicle') == 1 else "Троллейбус"
        url = BASE_ROUTE_URL.format(r['id'])
        rows.append([link_button(f"🌐 {v_icon} {v_name} №{r['number']}", url)])
    rows.append([button("🏠 Главное меню", "menu")])

    return {
        "text": "Найдено несколько маршрутов с таким номером. Выберите нужный:",
        "attachments": keyboard(rows)
    }

def how_to_buy_menu():
    text = (
        "🎫 **Как приобрести билет посредством чат-бота**\n\n"
        "**Шаг 1. Авторизация (при первом входе)**\n"
        f"• Запустите [чат-бот «MAX»]({MAX_TICKET_BOT_URL}) на своем мобильном устройстве.\n"
        "• Подтвердите свой номер телефона.\n"
        "• Нажмите кнопку «Продолжить». Этим действием вы принимаете условия работы сервиса.\n\n"
        "**Шаг 2. Сканирование QR-кода**\n"
        "• Найдите в салоне транспортного средства наклейку с официальным QR-кодом Транспортной Системы «Электронный проездной» или числовой идентификатор.\n"
        "• Включите камеру мобильного устройства и наведите её на QR-код для считывания или введите числовой идентификатор.\n\n"
        "**Шаг 3. Подтверждение и оплата**\n"
        "• В интерфейсе чат-бота автоматически появятся параметры вашей поездки (маршрут, номер транспорта).\n"
        "• Проверьте данные и нажмите кнопку «Оплатить».\n"
        "• Дождитесь успешного списания денежных средств.\n\n"
        "**Шаг 4. Контроль поездки**\n"
        "• После оплаты на экране вашего устройства мгновенно отобразится QR-код (билет в электронном виде), а также информация о купленном билете будет отображена в разделе «Активные билеты» чат-бота.\n"
        "• Договор перевозки считается заключенным. Кассовый чек будет отправлен на ваш email.\n\n"
        "⚠️ **Важно:** Сохраняйте билет на экране до конца поездки. При проверке вы обязаны предъявить его контролеру.\n\n"
        "ℹ️ **Внимание:** Пользователь самостоятельно несет ответственность за исправность своего Мобильного устройства (заряд батареи, экран) "
        "и наличие интернета у своего сотового оператора. Пожалуйста, убедитесь, что устройство работает, "
        "чтобы подтвердить оплату проезда контролеру."
    )
    attachments = keyboard([
        [link_button("📲 Перейти в чат-бот «MAX»", MAX_TICKET_BOT_URL)],
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def how_to_topup_menu():
    text = (
        "📲 **Как пополнить проездные билеты в мобильном приложении «Транспортная карта»**\n\n"
        "Памятка с подробной инструкцией по пополнению проездных билетов доступна по кнопке ниже:"
    )
    attachments = keyboard([
        [link_button("🖼 Открыть памятку (изображение)", IMG_TOPUP_URL)],
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def fares_menu():
    text = (
        "💰 **Стоимость проезда в общественном транспорте:**\n\n"
        "💳 **43 рубля** — стоимость одной поездки при оплате с использованием транспортной карты «Береста»\n\n"
        "💵 **45 рублей** — стоимость одной поездки при использовании иных способов оплаты"
    )
    attachments = keyboard([
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def ticket_types_menu():
    text = (
        "📋 **Виды проездных билетов и их стоимость**\n\n"
        "Подробный перечень видов проездных билетов, тарифов и правил использования размещен в официальном документе:"
    )
    attachments = keyboard([
        [link_button("📄 Скачать документ (PDF)", PDF_TICKETS_URL)],
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def carriers_menu():
    text = (
        "🏢 **Перевозчики Великого Новгорода**\n\n"
        "🚍 **Акционерное общество «Автобусный парк»**\n"
        "_Обслуживает городские маршруты №№:_ 1А, 2К, 3, 4, 5, 6, 7, 7А, 8, 8а, 13, 15, 15А, 16, 17, 17А, 19, 20, 21, 24, 26, 26а, 27, 32, 44М, 45, 53Т, 71.\n\n"
        "📍 **Адрес:** 173020, г. В. Новгород, ул. Хутынская, д. 10\n"
        "📞 **Диспетчер:** 8 (8162) 63-34-16\n"
        "☎️ **Приёмная:** 8 (8162) 63-64-40\n"
        "📧 **E-mail:** buspark53@yandex.ru\n\n"
        "────────────────────\n\n"
        "🚌 **ООО «Городское пассажирское автотранспортное предприятие»**\n"
        "_Обслуживает городские маршруты №№:_ 1, 2, 9, 10, 11, 11а, 12, 14, 18, 22, 35, 35а, 36, 72, 101.\n\n"
        "📍 **Адрес:** 173015, г. В. Новгород, ул. Нехинская, д. 1\n"
        "📞 **Диспетчер:** 8 (8162) 62-14-20\n"
        "☎️ **Приёмная:** 8 (8162) 62-15-65\n"
        "📧 **E-mail:** karpov@mpatp1.ru"
    )
    attachments = keyboard([
        [button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def useful_info_menu():
    text = (
        "ℹ️ **Полезная информация**\n\n"
        "Выберите интересующий раздел:"
    )
    buttons = [
        [button("📍 Основные точки продажи проездных билетов", "sales_points")],
        [button("🏛 Претензионный центр по вопросам оплаты", "claims_center")],
        [button("🏠 Главное меню", "menu")]
    ]
    return {
        "text": text,
        "attachments": keyboard(buttons)
    }

def sales_points_menu():
    text = (
        "📍 **Основные точки по продаже проездных билетов**\n\n"
        "1️⃣ **ул. Фёдоровский ручей, у д. 15:**\n"
        "• **20 – 24 числа месяца:** с 9:00 до 18:00\n"
        "  *(перерыв на обед с 13:00 до 14:00)*\n"
        "• **1 – 4 и 25 – 31 числа месяца:** с 7:00 до 19:00\n"
        "  *(перерыв на обед с 12:30 до 14:00)*\n"
        "• **Выходные дни:** с 5 по 19 число месяца.\n\n"
        "2️⃣ **ул. Свободы, д. 16/11**\n"
        "*(вход через крыльцо пункта выдачи интернет-магазина Wildberries)*:\n"
        "• **5 – 8 и 20 – 24 числа месяца:** с 9:00 до 18:00\n"
        "  *(перерыв на обед с 13:00 до 14:00)*\n"
        "• **1 – 4 и 25 – 31 числа месяца:** с 7:00 до 19:00\n"
        "  *(перерыв на обед с 12:30 до 14:00)*\n"
        "• **Выходные дни:** с 9 по 19 число месяца.\n\n"
        "3️⃣ **ул. Хутынская, д. 10 (АО «Автобусный парк»):**\n"
        "• **Ежедневно:** с 7:00 до 19:00\n"
        "  *(перерыв с 13:00 до 13:30)*.\n\n"
        "4️⃣ **ул. Нехинская, д. 1 (ООО «Городское ПАТП»):**\n"
        "• **Понедельник – пятница:** с 8:30 до 19:00\n"
        "  *(тех. перерывы: 10:30–10:45, 12:45–13:00, 15:00–15:15, 17:15–17:30)*\n"
        "• **Суббота – воскресенье:** с 8:30 до 19:00\n"
        "  *(обед с 16:00 до 17:00; тех. перерывы: 10:30–10:45, 12:45–13:00, 15:00–15:15)*"
    )
    attachments = keyboard([
        [button("◀ Назад", "useful_info"), button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def claims_center_menu():
    text = (
        "🏛 **Претензионный центр по вопросам, касающимся электронной оплаты проезда**\n\n"
        "📍 **Адрес:** ул. Германа, д. 39, 2 этаж, «Бухгалтерия ООО «ЦДС ОТ»»\n\n"
        "🕒 **Режим работы:** с 7:45 до 17:30 *(по рабочим дням)*\n"
        "🍽 **Перерыв:** с 12:00 до 14:00\n"
        "📞 **Телефон:** 8 (8162) 777-850"
    )
    attachments = keyboard([
        [button("◀ Назад", "useful_info"), button("🏠 Главное меню", "menu")]
    ])
    return {
        "text": text,
        "attachments": attachments
    }

def api_request(path, data):
    url = API + path
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": TOKEN,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"API ERROR {e.code} on {path}: {err_body}", flush=True)
        raise

def send_to_user(user_id, message):
    query = urllib.parse.urlencode({"user_id": str(user_id)})
    api_request("/messages?" + query, message)

def answer_callback(callback_id, message):
    query = urllib.parse.urlencode({"callback_id": str(callback_id)})
    api_request("/answers?" + query, {"message": message})

def search_routes(text):
    text_clean = text.lower().strip()

    is_trolley = bool(re.search(r'троллейбус|тролейбус|\bт\b', text_clean))
    is_bus = bool(re.search(r'автобус|\bа\b', text_clean))

    # Match number like "1", "1а", "2к", "4", "101"
    m = re.search(r'([0-9]+[а-яa-z]*)', text_clean)
    if not m:
        return []

    target_num = m.group(1).lower()

    all_matches = []
    for v in (1, 2):
        if is_trolley and v != 2:
            continue
        if is_bus and v != 1:
            continue

        routes = timetable_service.get_routes(v)
        for r in routes:
            r_num = str(r['number']).lower().strip()
            if r_num == target_num:
                all_matches.append(r)
            elif ',' in r_num:
                parts = [p.strip() for p in r_num.split(',')]
                if target_num in parts:
                    all_matches.append(r)

    return all_matches

def process_update(update):
    event_type = update.get("update_type", "")

    if event_type == "bot_started":
        user = update.get("user") or {}
        user_id = user.get("user_id")
        if user_id:
            send_to_user(user_id, main_menu())
        return

    if event_type == "message_created":
        message = update.get("message") or {}
        sender = message.get("sender") or {}

        # Не отвечаем на сообщения ботов
        if sender.get("is_bot"):
            return

        user_id = sender.get("user_id")
        body = message.get("body") or {}
        raw_text = (body.get("text") or "").strip()
        text = raw_text.lower()

        if not user_id:
            return

        # Сервисные команды
        if text in ("/start", "меню", "главное меню"):
            send_to_user(user_id, main_menu())
            return

        if text in ("расписание", "расписания"):
            send_to_user(user_id, ask_route_menu())
            return

        # Поиск маршрута по введенному номеру
        matched = search_routes(raw_text)
        if len(matched) == 1:
            send_to_user(user_id, route_link_message(matched[0]))
            return
        elif len(matched) > 1:
            send_to_user(user_id, disambiguate_menu(matched))
            return
        else:
            send_to_user(user_id, route_not_found_message(raw_text))
            return

    if event_type == "message_callback":
        callback = update.get("callback") or {}
        callback_id = callback.get("callback_id")
        payload = str(callback.get("payload") or "")

        if not callback_id:
            return

        if payload == "menu":
            answer_callback(callback_id, main_menu())
        elif payload in ("ask_route", "tt_vehicle"):
            answer_callback(callback_id, ask_route_menu())
        elif payload == "how_to_buy":
            answer_callback(callback_id, how_to_buy_menu())
        elif payload == "how_to_topup":
            answer_callback(callback_id, how_to_topup_menu())
        elif payload == "fares":
            answer_callback(callback_id, fares_menu())
        elif payload == "ticket_types":
            answer_callback(callback_id, ticket_types_menu())
        elif payload == "carriers":
            answer_callback(callback_id, carriers_menu())
        elif payload == "useful_info":
            answer_callback(callback_id, useful_info_menu())
        elif payload == "sales_points":
            answer_callback(callback_id, sales_points_menu())
        elif payload == "claims_center":
            answer_callback(callback_id, claims_center_menu())
        else:
            answer_callback(callback_id, main_menu())

def process_event(event):
    updates = event if isinstance(event, list) else [event]
    for update in updates:
        if not isinstance(update, dict):
            continue
        try:
            process_update(update)
        except Exception as exc:
            print(
                "Ошибка обработки события {}: {}".format(
                    update.get("update_type", "unknown"), exc
                ),
                flush=True
            )

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_error(404)
            return

        if not SECRET or self.headers.get("X-Max-Bot-Api-Secret") != SECRET:
            self.send_error(403)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1024 * 1024:
                self.send_error(400)
                return

            raw_body = self.rfile.read(length)
            event = json.loads(raw_body.decode("utf-8"))

        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "11")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

        process_event(event)

    def log_message(self, fmt, *args):
        print(
            "{} - {}".format(
                self.log_date_time_string(), fmt % args
            ),
            flush=True
        )

if __name__ == "__main__":
    if not TOKEN or not SECRET:
        raise RuntimeError("Не заданы MAX_BOT_TOKEN или MAX_WEBHOOK_SECRET")

    print("MAX bot webhook запущен на 127.0.0.1:8081", flush=True)
    HTTPServer(("127.0.0.1", 8081), WebhookHandler).serve_forever()
