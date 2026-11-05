import os
import re
import html
import time
from datetime import datetime
from html.parser import HTMLParser
import pymysql

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'transport_nov_ru'),
    'password': os.environ.get('DB_PASSWORD', 'De^h78ytqL'),
    'database': os.environ.get('DB_NAME', 'transport_rcit'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Cache structure: { group_id: { 'time': timestamp, 'header': [...], 'columns': [...] } }
TABLE_CACHE = {}
CACHE_TTL = 3600  # 1 hour

def get_connection():
    return pymysql.connect(**DB_CONFIG)

class TableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = []
        self.current_cell = []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = []
        elif tag == 'tr':
            self.current_row = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.in_cell = False
            cell_text = "".join(self.current_cell)
            cell_text = html.unescape(cell_text).replace('\xa0', ' ').strip()
            self.current_row.append(cell_text)
        elif tag == 'tr':
            if self.current_row:
                self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)

def clean_stop_name(raw_name):
    clean = re.sub(r'\s+', ' ', raw_name).strip()
    return clean

def parse_html_table(html_content):
    parser = TableHTMLParser()
    parser.feed(html_content)
    rows = parser.rows
    if not rows:
        return [], []

    header = [clean_stop_name(h) for h in rows[0]]
    num_cols = len(header)

    columns = [[] for _ in range(num_cols)]
    for row in rows[1:]:
        for col_idx in range(num_cols):
            val = row[col_idx] if col_idx < len(row) else ""
            val = val.strip()
            # If cell contains a time like 5:14, 05:14, 6:19*
            if re.search(r'\d{1,2}:\d{2}', val):
                columns[col_idx].append(val)

    return header, columns

def get_routes(vehicle_type):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, number, point1, point2, vehicle FROM timetable_routes "
                "WHERE vehicle = %s AND visibility = 1 ORDER BY num, number",
                (vehicle_type,)
            )
            return cur.fetchall()
    finally:
        conn.close()

def get_route(route_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, number, point1, point2, vehicle FROM timetable_routes WHERE id = %s",
                (route_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()

def get_groups(route_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, route, title FROM timetable_groupes WHERE route = %s AND visibility = 1 ORDER BY num",
                (route_id,)
            )
            return cur.fetchall()
    finally:
        conn.close()

def get_group(group_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, route, title FROM timetable_groupes WHERE id = %s",
                (group_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()

def get_table_data(group_id):
    now_ts = time.time()
    if group_id in TABLE_CACHE:
        cached = TABLE_CACHE[group_id]
        if now_ts - cached['time'] < CACHE_TTL:
            return cached['header'], cached['columns']

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, date FROM timetable_tables "
                "WHERE `group` = %s AND visibility = 1 AND date <= CURDATE() "
                "ORDER BY date DESC LIMIT 1",
                (group_id,)
            )
            tbl = cur.fetchone()
            if not tbl:
                cur.execute(
                    "SELECT id, text, date FROM timetable_tables "
                    "WHERE `group` = %s AND visibility = 1 "
                    "ORDER BY date DESC LIMIT 1",
                    (group_id,)
                )
                tbl = cur.fetchone()

            if not tbl or not tbl['text']:
                return [], []

            header, columns = parse_html_table(tbl['text'])
            TABLE_CACHE[group_id] = {
                'time': now_ts,
                'header': header,
                'columns': columns
            }
            return header, columns
    finally:
        conn.close()

def get_schedule_result(route_id, group_id, col_idx):
    route = get_route(route_id)
    group = get_group(group_id)
    header, columns = get_table_data(group_id)

    if not header or col_idx >= len(header):
        return {
            'route': route,
            'group': group,
            'stop_name': 'Остановка не найдена',
            'times': [],
            'message': 'Расписание для выбранной остановки не найдено.'
        }

    stop_name = header[col_idx]
    times = columns[col_idx] if col_idx < len(columns) else []

    if not times:
        vehicle_icon = "🚌" if (route and route.get('vehicle') == 1) else "🚎"
        route_num = route['number'] if route else ""
        grp_title = group['title'] if group else ""
        msg = f"{vehicle_icon} **Маршрут №{route_num}** — {grp_title}\n📍 Остановка: **{stop_name}**\n\nДля данной остановки рейсы не указаны."
        return {
            'route': route,
            'group': group,
            'stop_name': stop_name,
            'times': [],
            'message': msg
        }

    # Find nearest departure time
    now = datetime.now()
    cur_minutes = now.hour * 60 + now.minute

    nearest_idx = None
    min_diff = None

    for idx, t in enumerate(times):
        m = re.search(r'(\d{1,2}):(\d{2})', t)
        if m:
            h, mn = int(m.group(1)), int(m.group(2))
            dep_min = h * 60 + mn
            if dep_min >= cur_minutes:
                diff = dep_min - cur_minutes
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    nearest_idx = idx
                    break

    formatted_times = []
    for idx, t in enumerate(times):
        if idx == nearest_idx:
            formatted_times.append(f"[⏱ {t}]")
        else:
            formatted_times.append(t)

    schedule_str = "; ".join(formatted_times)

    vehicle_icon = "🚌" if (route and route.get('vehicle') == 1) else "🚎"
    route_num = route['number'] if route else ""
    grp_title = group['title'] if group else ""

    info_note = ""
    if nearest_idx is not None:
        info_note = "\n\n💡 _[⏱] — отмечен ближайший рейс относительно текущего времени._"
    else:
        info_note = f"\n\n💡 _На сегодня все рейсы завершены. Первый рейс: {times[0]}._"

    msg = (
        f"{vehicle_icon} **Маршрут №{route_num}** — **{grp_title}**\n"
        f"📍 Остановка: **{stop_name}**\n\n"
        f"⏱ **Время отправления:**\n{schedule_str}"
        f"{info_note}"
    )

    return {
        'route': route,
        'group': group,
        'stop_name': stop_name,
        'times': times,
        'message': msg
    }
