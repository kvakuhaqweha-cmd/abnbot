#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиентский Telegram-бот для пошагового заказа линейного бетононасоса (@abntrassa).
Написан полностью с нуля, без перегруженного интерфейса:
1. По очереди спрашивает у клиента:
   - Адрес объекта (текстом, координатами или геопозицией 📎) -> сам находит координаты,
     формирует ссылку Яндекс.Навигатора и считает пробег (км от МКАД) с ближайшего съезда.
   - Необходимую длину трассы (м).
   - По умолчанию уже включает в стоимость: 1 смену, 4 угла поворота, 1 гибкий шланг, 1 пусковую смесь.
     Если клиенту нужно больше 4 углов или больше 1 шланга — он может указать это одной кнопкой.
   - Желаемую дату и время поставки.
   - Что и сколько качать (например: 26м3 М350 гравий).
   - Что заливают (например: отмостка, плита, фундамент).
   - Способ оплаты (Наличные / Безнал) -> если выбран Безнал, обязательно запрашивает название компании.
   - Контактный телефон.
   - Дополнительные сообщения / пожелания к заявке (можно дописывать отдельные сообщения).
2. Формирует заявку строго по шаблону и перенаправляет клиента в личные сообщения @abntrassa
   с уже готовым текстом заявки и всеми комментариями.
"""

from datetime import datetime, timedelta
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ==============================================================================
# НАСТРОЙКИ БОТА
# ==============================================================================
BOT_TOKEN = ""
MANAGER_USERNAME = "abntrassa"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")

# Тарифы (в рублях)
PRICES = {
    "shift_nal": 23000,      # Смена (Наличные)
    "shift_beznal": 25000,   # Смена (Безнал)
    "pipe_per_m": 200,       # Трасса / бетоновод за 1 м
    "corner": 500,           # Угол поворота за 1 шт (по дефолту 4 шт = 2000 р)
    "hose": 2000,            # Гибкий шланг за 1 шт (по дефолту 1 шт = 2000 р)
    "mixture": 2000,         # Пусковая смесь за 1 шт (по дефолту 1 шт = 2000 р)
    "mileage_per_km": 100,   # Пробег от МКАД за 1 км
}

# Координаты съездов МКАД для авторасчёта пробега до объекта
MKAD_EXITS = [
    {"id": "entuziastov", "name": "Шоссе Энтузиастов", "lat": 55.7764, "lon": 37.8427},
    {"id": "nosovihinskoe", "name": "Носовихинское шоссе", "lat": 55.7512, "lon": 37.8442},
    {"id": "kosino", "name": "Северо-Восточная хорда (Косино)", "lat": 55.7161, "lon": 37.8384},
    {"id": "ryazanskiy", "name": "Рязанский проспект", "lat": 55.7092, "lon": 37.8329},
    {"id": "novoryazanskoe", "name": "Новорязанское шоссе (М-5)", "lat": 55.6852, "lon": 37.8286},
    {"id": "kotelniki", "name": "Улица Верхние Поля (Котельники)", "lat": 55.6575, "lon": 37.8318},
    {"id": "kapotnya", "name": "Капотня / Дзержинский", "lat": 55.6352, "lon": 37.8130},
    {"id": "besedinskoe", "name": "Бесединское шоссе", "lat": 55.6186, "lon": 37.7752},
    {"id": "kashirskoe", "name": "Каширское шоссе (А-105)", "lat": 55.5955, "lon": 37.7263},
    {"id": "m4don", "name": "Трасса М-4 «Дон»", "lat": 55.5786, "lon": 37.6815},
    {"id": "simferopolskoe", "name": "Симферопольское шоссе (М-2)", "lat": 55.5721, "lon": 37.6022},
    {"id": "varshavskoe", "name": "Варшавское шоссе", "lat": 55.5750, "lon": 37.5938},
    {"id": "kaluzhskoe", "name": "Калужское шоссе", "lat": 55.6052, "lon": 37.4932},
    {"id": "kievskoe", "name": "Киевское шоссе (М-3)", "lat": 55.6382, "lon": 37.4589},
    {"id": "borovskoe", "name": "Боровское шоссе", "lat": 55.6612, "lon": 37.4345},
    {"id": "minskoe", "name": "Минское / Можайское шоссе", "lat": 55.7126, "lon": 37.3924},
    {"id": "rublevskoe", "name": "Рублёво-Успенское шоссе", "lat": 55.7645, "lon": 37.3692},
    {"id": "novorizhskoe", "name": "Новорижское шоссе (М-9)", "lat": 55.7885, "lon": 37.3702},
    {"id": "volokolamskoe", "name": "Волоколамское шоссе", "lat": 55.8295, "lon": 37.3928},
    {"id": "putilkovskoe", "name": "Путилковское шоссе", "lat": 55.8548, "lon": 37.3962},
    {"id": "kurkinskoe", "name": "Куркинское шоссе", "lat": 55.8758, "lon": 37.4295},
    {"id": "leningradskoe", "name": "Ленинградское шоссе (М-10)", "lat": 55.8819, "lon": 37.4439},
    {"id": "m11neva", "name": "Трасса М-11 «Нева»", "lat": 55.8942, "lon": 37.4792},
    {"id": "dmitrovskoe", "name": "Дмитровское шоссе (А-104)", "lat": 55.9089, "lon": 37.5435},
    {"id": "altufevskoe", "name": "Алтуфьевское шоссе", "lat": 55.9094, "lon": 37.5872},
    {"id": "ostashkovskoe", "name": "Осташковское шоссе", "lat": 55.8952, "lon": 37.6695},
    {"id": "yaroslavskoe", "name": "Ярославское шоссе (М-8)", "lat": 55.8761, "lon": 37.7235},
    {"id": "schelkovskoe", "name": "Щёлковское шоссе (А-103)", "lat": 55.8165, "lon": 37.8388},
]

USER_SESSIONS = {}


def create_new_session() -> dict:
    """Создаёт чистую анкету клиента с базовой комплектацией (4 угла, 1 шланг, 1 пусковая)."""
    return {
        "step": "address",  # Текущий шаг анкеты
        "address": "",
        "coords_str": "",
        "navi_url": "",
        "distance_km": 0,
        "exit_name": "",
        "pipe_m": 0,        # Длина трассы (м)
        "corners": 4,       # По дефолту 4 угла поворота входят в начальную стоимость
        "hoses": 1,         # По дефолту 1 гибкий шланг входит в начальную стоимость
        "mixtures": 1,      # По дефолту 1 пусковая смесь входит в начальную стоимость
        "date_str": "",     # Дата поставки (например: 15.10.2026)
        "time_str": "",     # Время подачи (например: 08:00)
        "concrete_info": "",  # Качать: 26м3 М350 гравий
        "pour_type": "",    # Заливают: отмостка
        "payment_type": "", # 'наличные' или 'безнал'
        "company_name": "", # Название компании (обязательно при безнале)
        "contact": "",      # Контакт: +79104047482
        "extra_messages": [],  # Отдельные сообщения/пожелания клиента к заявке
    }


def get_session(chat_id: int) -> dict:
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = create_new_session()
    return USER_SESSIONS[chat_id]


# ==============================================================================
# РАСЧЁТ СТОИМОСТИ
# ==============================================================================
def calculate_total(session: dict, payment_kind: str) -> int:
    """
    Считает итоговую стоимость аренды.
    По дефолту уже включены: 1 смена + 4 угла (2000р) + 1 шланг (2000р) + 1 пусковая (2000р).
    Плюс: метраж трассы (pipe_m * 200) и пробег от МКАД (distance_km * 100).
    """
    shift_price = PRICES["shift_beznal"] if payment_kind == "безнал" else PRICES["shift_nal"]
    pipe_cost = int(round(session["pipe_m"] * PRICES["pipe_per_m"]))
    corners_cost = int(round(session["corners"] * PRICES["corner"]))
    hoses_cost = int(round(session["hoses"] * PRICES["hose"]))
    mixture_cost = int(round(session["mixtures"] * PRICES["mixture"]))
    mileage_cost = int(round(session["distance_km"] * PRICES["mileage_per_km"]))
    return shift_price + pipe_cost + corners_cost + hoses_cost + mixture_cost + mileage_cost


# ==============================================================================
# ГЕОКОДИРОВАНИЕ, КООРДИНАТЫ И РАСЧЁТ КМ ОТ МКАД
# ==============================================================================
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_inside_mkad(lat: float, lon: float) -> bool:
    inside = False
    n = len(MKAD_EXITS)
    j = n - 1
    for i in range(n):
        xi, yi = MKAD_EXITS[i]["lat"], MKAD_EXITS[i]["lon"]
        xj, yj = MKAD_EXITS[j]["lat"], MKAD_EXITS[j]["lon"]
        intersect = ((yi > lon) != (yj > lon)) and (
            lat < (xj - xi) * (lon - yi) / (yj - yi + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def find_nearest_exit(lat: float, lon: float) -> tuple:
    best = MKAD_EXITS[0]
    min_d = float("inf")
    for ex in MKAD_EXITS:
        d = haversine_km(lat, lon, ex["lat"], ex["lon"])
        if d < min_d:
            min_d = d
            best = ex
    return best, min_d


def build_yandex_navi_url(lat: float, lon: float) -> str:
    return f"https://yandex.ru/navi/?whatshere%5Bpoint%5D={lon:.6f}%2C{lat:.6f}&whatshere%5Bzoom%5D=16"


def reverse_geocode(lat: float, lon: float) -> str:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AbnTrassaClientBot/3.0", "Accept-Language": "ru"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            disp = data.get("display_name", "")
            if disp:
                # Убираем индекс и название страны в конце для аккуратного вида
                parts = [p.strip() for p in disp.split(",")]
                filtered = [p for p in parts if not p.isdigit() and p.lower() not in ("россия", "центральный федеральный округ")]
                return ", ".join(filtered[:4])
    except Exception:
        pass
    return f"Точка по координатам ({lat:.6f}, {lon:.6f})"


def geocode_text_address(query: str):
    """Возвращает (lat, lon, formatted_address) по текстовому адресу или координатам."""
    # Проверка, не ввёл ли клиент координаты напрямую (например: 56.205411, 37.992066)
    coord_match = re.search(r"(\d{2}\.\d{3,})\s*[,;\s]\s*(\d{2}\.\d{3,})", query)
    if coord_match:
        lat = float(coord_match.group(1))
        lon = float(coord_match.group(2))
        addr = reverse_geocode(lat, lon)
        return lat, lon, addr

    # 1. Поиск через Nominatim OpenStreetMap (отлично возвращает полные русские адреса МО)
    for suffix in (", Московская область", ", Москва", ""):
        try:
            url = (
                "https://nominatim.openstreetmap.org/search?format=json&q="
                + urllib.parse.quote(query + suffix)
                + "&limit=1"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AbnTrassaClientBot/3.0", "Accept-Language": "ru"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                if results:
                    r = results[0]
                    lat, lon = float(r["lat"]), float(r["lon"])
                    disp = r.get("display_name", query)
                    parts = [p.strip() for p in disp.split(",")]
                    filtered = [
                        p for p in parts
                        if not p.isdigit() and p.lower() not in ("россия", "центральный федеральный округ", "московская область")
                    ]
                    clean_addr = ", ".join(filtered[:4]) or query
                    return lat, lon, clean_addr
        except Exception:
            pass

    # 2. Запасной поиск через Photon
    try:
        url = (
            "https://photon.komoot.io/api/?q="
            + urllib.parse.quote(query + " Московская область")
            + "&lat=55.7558&lon=37.6173&limit=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AbnTrassaClientBot/3.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            features = data.get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                props = features[0].get("properties", {})
                parts = [props.get("street"), props.get("housenumber"), props.get("name"), props.get("city"), props.get("county")]
                clean_addr = ", ".join([p for p in parts if p]) or query
                return float(coords[1]), float(coords[0]), clean_addr
    except Exception:
        pass

    return None


def calc_road_km_from_mkad(lat: float, lon: float) -> tuple:
    """Возвращает (distance_km, exit_name) от ближайшего съезда МКАД."""
    nearest_exit, direct_km = find_nearest_exit(lat, lon)
    if is_inside_mkad(lat, lon):
        return 0, nearest_exit["name"]

    try:
        osrm_url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{nearest_exit['lon']},{nearest_exit['lat']};{lon},{lat}?overview=false"
        )
        req = urllib.request.Request(osrm_url, headers={"User-Agent": "AbnTrassaClientBot/3.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            routes = data.get("routes", [])
            if routes:
                road_km = max(1, int(round(routes[0]["distance"] / 1000.0)))
                return road_km, nearest_exit["name"]
    except Exception:
        pass

    return max(1, int(round(direct_km * 1.25))), nearest_exit["name"]


# ==============================================================================
# ФОРМИРОВАНИЕ ИТОГОВОЙ ЗАЯВКИ ПО ШАБЛОНУ
# ==============================================================================
def format_final_application(session: dict) -> str:
    """
    Формирует заявку строго по образцу:
    Заявка на 15.10.2026
    к 08:00
    Адрес: Дружная улица, 3, территория Хотьковский, Сергиево-Посадский городской округ
    56.205411, 37.992066
    https://yandex.ru/navi/-/CXBiYVom
    Качать: 26м3 М350 гравий
    АБН: линейный, 90м трассы
    Оплата: наличные, 48000р
    Заливают: отмостка
    Контакт: +79104047482
    """
    date_part = session["date_str"] or "не указана"
    time_part = session["time_str"] or "08:00"
    if not time_part.lower().startswith("к "):
        time_line = f"к {time_part}"
    else:
        time_line = time_part

    lines = [
        f"Заявка на {date_part}",
        time_line,
        f"Адрес: {session['address'] or 'не указан'}",
    ]

    if session["coords_str"]:
        lines.append(session["coords_str"])
    if session["navi_url"]:
        lines.append(session["navi_url"])

    lines.append(f"Качать: {session['concrete_info'] or 'не указано'}")

    # Строка АБН: линейный, Xм трассы (+ доп. углы/шланги, если больше стандарта)
    abn_extras = []
    if session["corners"] > 4:
        abn_extras.append(f"углы {session['corners']} шт (доп. +{session['corners'] - 4} шт)")
    if session["hoses"] > 1:
        abn_extras.append(f"шланги {session['hoses']} шт (доп. +{session['hoses'] - 1} шт)")
    if session["mixtures"] > 1:
        abn_extras.append(f"пусковая смесь {session['mixtures']} шт")

    abn_str = f"линейный, {session['pipe_m']}м трассы"
    if abn_extras:
        abn_str += f" ({', '.join(abn_extras)})"
    lines.append(f"АБН: {abn_str}")

    # Строка Оплата
    pay_type = session["payment_type"] or "наличные"
    total_rub = calculate_total(session, pay_type)
    if pay_type == "безнал":
        comp = session["company_name"] or "не указана"
        lines.append(f"Оплата: безнал ({comp}), {total_rub}р")
    else:
        lines.append(f"Оплата: наличные, {total_rub}р")

    lines.append(f"Заливают: {session['pour_type'] or 'не указано'}")
    lines.append(f"Контакт: {session['contact'] or 'не указан'}")

    if session["extra_messages"]:
        lines.append("")
        lines.append("Сообщение от клиента:")
        for m in session["extra_messages"]:
            lines.append(f"— {m}")

    return "\n".join(lines)


def get_manager_deeplink(session: dict) -> str:
    app_text = format_final_application(session)
    encoded = urllib.parse.quote(app_text, safe="")
    return f"https://t.me/{MANAGER_USERNAME}?text={encoded}"


# ==============================================================================
# РАБОТА С TELEGRAM BOT API
# ==============================================================================
def tg_api(token: str, method: str, payload: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_message(token: str, chat_id: int, text: str, reply_markup: dict = None, parse_mode: str = "Markdown"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_api(token, "sendMessage", payload)


def answer_callback(token: str, callback_id: str, text: str = ""):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        tg_api(token, "answerCallbackQuery", payload)
    except Exception:
        pass


# ==============================================================================
# КЛАВИАТУРЫ ДЛЯ ШАГОВ АНКЕТЫ (ПРОСТЫЕ И НЕ ПЕРЕГРУЖЕННЫЕ)
# ==============================================================================
def kb_pipe_length() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Без доп. трассы (0 м)", "callback_data": "pipe:0"},
                {"text": "20 м", "callback_data": "pipe:20"},
                {"text": "40 м", "callback_data": "pipe:40"},
            ],
            [
                {"text": "60 м", "callback_data": "pipe:60"},
                {"text": "90 м", "callback_data": "pipe:90"},
                {"text": "100 м", "callback_data": "pipe:100"},
            ],
        ]
    }


def kb_extras_check() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Достаточно базового (4 угла, 1 шланг, 1 пусковая)", "callback_data": "extras:ok"}],
            [{"text": "➕ Нужно больше углов или шлангов", "callback_data": "extras:more"}],
        ]
    }


def kb_extra_corners() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Оставить 4 угла", "callback_data": "corners:4"},
                {"text": "6 углов", "callback_data": "corners:6"},
                {"text": "8 углов", "callback_data": "corners:8"},
            ]
        ]
    }


def kb_extra_hoses() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Оставить 1 шланг", "callback_data": "hoses:1"},
                {"text": "2 шланга", "callback_data": "hoses:2"},
                {"text": "3 шланга", "callback_data": "hoses:3"},
            ]
        ]
    }


def kb_dates() -> dict:
    now = datetime.now()
    d0 = now.strftime("%d.%m.%Y")
    d1 = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    d2 = (now + timedelta(days=2)).strftime("%d.%m.%Y")
    return {
        "inline_keyboard": [
            [
                {"text": f"Сегодня ({d0})", "callback_data": f"date:{d0}"},
                {"text": f"Завтра ({d1})", "callback_data": f"date:{d1}"},
            ],
            [
                {"text": f"Послезавтра ({d2})", "callback_data": f"date:{d2}"},
            ],
        ]
    }


def kb_times() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "к 08:00", "callback_data": "time:08:00"},
                {"text": "к 09:00", "callback_data": "time:09:00"},
                {"text": "к 10:00", "callback_data": "time:10:00"},
            ],
            [
                {"text": "к 12:00", "callback_data": "time:12:00"},
                {"text": "к 14:00", "callback_data": "time:14:00"},
                {"text": "к 16:00", "callback_data": "time:16:00"},
            ],
        ]
    }


def kb_pour_types() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Отмостка", "callback_data": "pour:отмостка"},
                {"text": "Плита", "callback_data": "pour:плита"},
                {"text": "Фундамент", "callback_data": "pour:фундамент"},
            ],
            [
                {"text": "Лента", "callback_data": "pour:лента"},
                {"text": "Перекрытие", "callback_data": "pour:перекрытие"},
                {"text": "Стены / Колонны", "callback_data": "pour:стены"},
            ],
        ]
    }


def kb_payment(session: dict) -> dict:
    sum_nal = calculate_total(session, "наличные")
    sum_beznal = calculate_total(session, "безнал")
    return {
        "inline_keyboard": [
            [{"text": f"💵 Наличные — {sum_nal} р", "callback_data": "pay:наличные"}],
            [{"text": f"💳 Безнал — {sum_beznal} р (указать компанию)", "callback_data": "pay:безнал"}],
        ]
    }


def kb_skip_comment() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Без комментария — сформировать заявку", "callback_data": "comment:skip"}],
        ]
    }


def kb_final_order(session: dict) -> dict:
    url = get_manager_deeplink(session)
    return {
        "inline_keyboard": [
            [{"text": f"✈️ Отправить заявку менеджеру @{MANAGER_USERNAME}", "url": url}],
            [{"text": "🔄 Заполнить новую заявку", "callback_data": "action:restart"}],
        ]
    }


# ==============================================================================
# ПЕРЕХОДЫ ПО ШАГАМ ДИАЛОГА
# ==============================================================================
def ask_step_pipe(token: str, chat_id: int, session: dict):
    session["step"] = "pipe"
    msg = (
        f"✅ *Адрес принят:* {session['address']}\n"
        f"🛣 Удалённость: *{session['distance_km']} км от МКАД*\n\n"
        "📏 *Шаг 2. Укажите необходимую длину трассы (бетоновода) в метрах:*\n"
        "Напишите число в чат (например: `90`) или выберите кнопку ниже:"
    )
    send_message(token, chat_id, msg, kb_pipe_length())


def ask_step_extras(token: str, chat_id: int, session: dict):
    session["step"] = "extras_choice"
    msg = (
        f"✅ Длина трассы: *{session['pipe_m']} м*\n\n"
        "ℹ️ В начальную стоимость по умолчанию уже входят:\n"
        "• *4 угла поворота*\n"
        "• *1 гибкий шланг*\n"
        "• *1 пусковая смесь*\n\n"
        "Нужно ли вам *больше 4 углов* или *больше 1 шланга*?"
    )
    send_message(token, chat_id, msg, kb_extras_check())


def ask_step_date(token: str, chat_id: int, session: dict):
    session["step"] = "date"
    send_message(
        token,
        chat_id,
        "📅 *Шаг 3. На какую дату планируется поставка?*\n"
        "Напишите дату (например: `15.10.2026`) или выберите кнопку ниже:",
        kb_dates(),
    )


def ask_step_time(token: str, chat_id: int, session: dict):
    session["step"] = "time"
    send_message(
        token,
        chat_id,
        "⏰ *Шаг 4. К какому времени подать бетононасос?*\n"
        "Напишите время (например: `08:00`) или выберите кнопку:",
        kb_times(),
    )


def ask_step_concrete(token: str, chat_id: int, session: dict):
    session["step"] = "concrete"
    send_message(
        token,
        chat_id,
        "🧱 *Шаг 5. Какой объём и марку бетона будете качать?*\n"
        "Напишите одним сообщением (например: `26м3 М350 гравий`):",
    )


def ask_step_pour(token: str, chat_id: int, session: dict):
    session["step"] = "pour"
    send_message(
        token,
        chat_id,
        "🏗 *Шаг 6. Что именно заливаете?*\n"
        "Напишите (например: `отмостка`) или выберите кнопку:",
        kb_pour_types(),
    )


def ask_step_payment(token: str, chat_id: int, session: dict):
    session["step"] = "payment"
    sum_nal = calculate_total(session, "наличные")
    sum_beznal = calculate_total(session, "безнал")
    extras_note = ""
    if session["corners"] > 4 or session["hoses"] > 1:
        extras_note = f"\n• Углы: {session['corners']} шт, Шланги: {session['hoses']} шт"

    msg = (
        "💰 *Предварительный расчёт стоимости:*\n"
        f"• Трасса: {session['pipe_m']} м\n"
        f"• Пробег: {session['distance_km']} км от МКАД"
        f"{extras_note}\n"
        "• Включено в базу: смена, 4 угла, 1 шланг, 1 пусковая смесь\n\n"
        f"💵 Наличные: *{sum_nal} р*\n"
        f"💳 Безнал: *{sum_beznal} р*\n\n"
        "Выберите удобный способ оплаты:"
    )
    send_message(token, chat_id, msg, kb_payment(session))


def ask_step_company(token: str, chat_id: int, session: dict):
    session["step"] = "company"
    send_message(
        token,
        chat_id,
        "🏢 *Укажите название вашей компании (для оплаты по безналу):*\n"
        "Напишите название организации в чат (например: `ООО СтройМонолит`):",
    )


def ask_step_contact(token: str, chat_id: int, session: dict):
    session["step"] = "contact"
    send_message(
        token,
        chat_id,
        "📞 *Шаг 7. Укажите контактный номер телефона для связи:*\n"
        "Напишите номер в чат (например: `+79104047482`):",
    )


def ask_step_comment(token: str, chat_id: int, session: dict):
    session["step"] = "comment"
    send_message(
        token,
        chat_id,
        "💬 *Хотите добавить отдельное сообщение или пожелание к заявке?*\n"
        "Напишите любое сообщение в чат (оно прикрепится к вашей заявке) или нажмите кнопку ниже:",
        kb_skip_comment(),
    )


def show_final_order(token: str, chat_id: int, session: dict):
    session["step"] = "done"
    app_text = format_final_application(session)
    send_message(
        token,
        chat_id,
        "✅ *Ваша заявка полностью готова!*\n\n"
        "Ниже сформированный текст заявки. Вы можете *дописать любое сообщение прямо в чат* (оно автоматически добавится к заявке) "
        f"или сразу нажать кнопку **«✈️ Отправить заявку менеджеру @{MANAGER_USERNAME}»** — откроется диалог с уже вписанным текстом:",
    )
    # Отправляем сам текст заявки без Markdown-искажений, с кнопкой перехода на @abntrassa
    send_message(token, chat_id, app_text, kb_final_order(session), parse_mode=None)


# ==============================================================================
# ОБРАБОТКА НАЖАТИЙ НА КНОПКИ (CALLBACK_QUERY)
# ==============================================================================
def handle_callback(token: str, cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    data = cb.get("data", "")

    if not chat_id:
        return

    session = get_session(chat_id)

    if data == "action:restart":
        USER_SESSIONS[chat_id] = create_new_session()
        answer_callback(token, cb_id, "Начинаем новую заявку")
        send_welcome(token, chat_id)
        return

    if data.startswith("pipe:"):
        session["pipe_m"] = int(data.split(":")[1])
        answer_callback(token, cb_id, f"Трасса: {session['pipe_m']} м")
        ask_step_extras(token, chat_id, session)

    elif data == "extras:ok":
        session["corners"] = 4
        session["hoses"] = 1
        session["mixtures"] = 1
        answer_callback(token, cb_id, "Базовый комплект сохранён")
        ask_step_date(token, chat_id, session)

    elif data == "extras:more":
        session["step"] = "extra_corners"
        answer_callback(token, cb_id)
        send_message(
            token,
            chat_id,
            "🔢 *Сколько всего углов поворота вам потребуется?*\n"
            "(В базу уже включены 4 угла, каждый дополнительный угол +500 р).\n"
            "Напишите общее количество углов числом (например: `6`) или выберите кнопку:",
            kb_extra_corners(),
        )

    elif data.startswith("corners:"):
        session["corners"] = max(4, int(data.split(":")[1]))
        session["step"] = "extra_hoses"
        answer_callback(token, cb_id, f"Углов: {session['corners']} шт")
        send_message(
            token,
            chat_id,
            "🔢 *Сколько всего гибких шлангов вам потребуется?*\n"
            "(В базу уже включён 1 шланг, каждый дополнительный шланг +2000 р).\n"
            "Напишите общее количество шлангов числом (например: `2`) или выберите кнопку:",
            kb_extra_hoses(),
        )

    elif data.startswith("hoses:"):
        session["hoses"] = max(1, int(data.split(":")[1]))
        answer_callback(token, cb_id, f"Шлангов: {session['hoses']} шт")
        ask_step_date(token, chat_id, session)

    elif data.startswith("date:"):
        session["date_str"] = data.split(":", 1)[1]
        answer_callback(token, cb_id, f"Дата: {session['date_str']}")
        ask_step_time(token, chat_id, session)

    elif data.startswith("time:"):
        session["time_str"] = data.split(":", 1)[1]
        answer_callback(token, cb_id, f"Время: к {session['time_str']}")
        ask_step_concrete(token, chat_id, session)

    elif data.startswith("pour:"):
        session["pour_type"] = data.split(":", 1)[1]
        answer_callback(token, cb_id, f"Заливают: {session['pour_type']}")
        ask_step_payment(token, chat_id, session)

    elif data.startswith("pay:"):
        pay_kind = data.split(":", 1)[1]
        session["payment_type"] = pay_kind
        answer_callback(token, cb_id, f"Оплата: {pay_kind}")
        if pay_kind == "безнал":
            ask_step_company(token, chat_id, session)
        else:
            ask_step_contact(token, chat_id, session)

    elif data == "comment:skip":
        answer_callback(token, cb_id, "Формирую заявку")
        show_final_order(token, chat_id, session)


# ==============================================================================
# ОБРАБОТКА ВХОДЯЩИХ СООБЩЕНИЙ КЛИЕНТА
# ==============================================================================
def send_welcome(token: str, chat_id: int):
    welcome_text = (
        "👋 *Здравствуйте! Здесь вы можете быстро рассчитать стоимость и заказать линейный бетононасос.*\n\n"
        "В базовую стоимость смены по умолчанию уже включены:\n"
        "• *4 угла поворота*\n"
        "• *1 гибкий шланг*\n"
        "• *1 пусковая смесь*\n\n"
        "📍 *Шаг 1. Напишите адрес вашего объекта* (например: `Сергиев Посад, Хотьково, ул. Дружная, 3`) "
        "или прикрепите *Геопозицию* через скрепку 📎:"
    )
    send_message(token, chat_id, welcome_text)


def handle_message(token: str, msg: dict):
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return

    session = get_session(chat_id)

    # 1. Если клиент прислал геопозицию (Location) на шаге адреса (или в любой момент)
    if "location" in msg:
        loc = msg["location"]
        lat, lon = float(loc["latitude"]), float(loc["longitude"])
        addr = reverse_geocode(lat, lon)
        km, exit_name = calc_road_km_from_mkad(lat, lon)
        session["address"] = addr
        session["coords_str"] = f"{lat:.6f}, {lon:.6f}"
        session["navi_url"] = build_yandex_navi_url(lat, lon)
        session["distance_km"] = km
        session["exit_name"] = exit_name
        ask_step_pipe(token, chat_id, session)
        return

    text = msg.get("text", "").strip()
    if not text:
        return

    # 2. Команды запуска / сброса
    if text.startswith("/start") or text.startswith("/reset") or text.startswith("/new"):
        USER_SESSIONS[chat_id] = create_new_session()
        send_welcome(token, chat_id)
        return

    step = session["step"]

    # ШАГ 1: АДРЕС ОБЪЕКТА
    if step == "address":
        # Если клиент сразу прислал ссылку на Яндекс.Навигатор / Карты в сообщении
        url_match = re.search(r"(https?://\S+)", text)
        custom_url = url_match.group(1) if url_match else ""
        clean_query = re.sub(r"https?://\S+", "", text).strip()

        send_message(token, chat_id, "🔎 Определяю координаты адреса и расстояние от МКАД...")
        found = geocode_text_address(clean_query or text)
        if found:
            lat, lon, full_addr = found
            km, exit_name = calc_road_km_from_mkad(lat, lon)
            session["address"] = full_addr
            session["coords_str"] = f"{lat:.6f}, {lon:.6f}"
            session["navi_url"] = custom_url or build_yandex_navi_url(lat, lon)
            session["distance_km"] = km
            session["exit_name"] = exit_name
            ask_step_pipe(token, chat_id, session)
        else:
            # Если геокодер не нашёл точные координаты, сохраняем адрес как ввёл клиент и спрашиваем км от МКАД
            session["address"] = clean_query or text
            session["navi_url"] = custom_url
            session["step"] = "manual_km"
            send_message(
                token,
                chat_id,
                f"📍 Адрес записан: *{session['address']}*\n"
                "Подскажите, сколько примерно *км от МКАД* до вашего объекта? (Напишите число, например `25`, или `0`, если объект внутри МКАД):",
            )
        return

    # Запасной шаг, если клиент вводил редкий адрес без координат
    if step == "manual_km":
        nums = re.findall(r"\d+", text)
        if nums:
            session["distance_km"] = int(nums[0])
            ask_step_pipe(token, chat_id, session)
        else:
            send_message(token, chat_id, "Пожалуйста, напишите расстояние от МКАД числом (например: `20` или `0`).")
        return

    # ШАГ 2: ДЛИНА ТРАССЫ
    if step == "pipe":
        nums = re.findall(r"\d+", text)
        if nums:
            session["pipe_m"] = int(nums[0])
            ask_step_extras(token, chat_id, session)
        else:
            send_message(
                token,
                chat_id,
                "Пожалуйста, укажите необходимую длину трассы числом в метрах (например: `90`) или нажмите кнопку ниже:",
                kb_pipe_length(),
            )
        return

    # ШАГ 2б: ДОПОЛНИТЕЛЬНЫЕ УГЛЫ / ШЛАНГИ (если нужно больше 4 углов или 1 шланга)
    if step == "extras_choice":
        low = text.lower()
        if low in ("нет", "ок", "достаточно", "база", "не нужно", "-"):
            ask_step_date(token, chat_id, session)
        else:
            session["step"] = "extra_corners"
            send_message(
                token,
                chat_id,
                "🔢 Напишите общее количество *углов поворота*, которое вам нужно (по умолчанию 4 шт):",
                kb_extra_corners(),
            )
        return

    if step == "extra_corners":
        nums = re.findall(r"\d+", text)
        if nums:
            session["corners"] = max(4, int(nums[0]))
            session["step"] = "extra_hoses"
            send_message(
                token,
                chat_id,
                "🔢 Теперь напишите общее количество *гибких шлангов*, которое вам нужно (по умолчанию 1 шт):",
                kb_extra_hoses(),
            )
        else:
            send_message(token, chat_id, "Напишите количество углов числом (например: `6`).", kb_extra_corners())
        return

    if step == "extra_hoses":
        nums = re.findall(r"\d+", text)
        if nums:
            session["hoses"] = max(1, int(nums[0]))
            ask_step_date(token, chat_id, session)
        else:
            send_message(token, chat_id, "Напишите количество шлангов числом (например: `2`).", kb_extra_hoses())
        return

    # ШАГ 3: ДАТА ПОСТАВКИ
    if step == "date":
        session["date_str"] = text
        ask_step_time(token, chat_id, session)
        return

    # ШАГ 4: ВРЕМЯ ПОДАЧИ
    if step == "time":
        session["time_str"] = text
        ask_step_concrete(token, chat_id, session)
        return

    # ШАГ 5: ЧТО КАЧАТЬ (ОБЪЁМ И МАРКА)
    if step == "concrete":
        session["concrete_info"] = text
        ask_step_pour(token, chat_id, session)
        return

    # ШАГ 6: ЧТО ЗАЛИВАЮТ
    if step == "pour":
        session["pour_type"] = text
        ask_step_payment(token, chat_id, session)
        return

    # ШАГ 7: ВЫБОР ОПЛАТЫ (если написали текстом вместо кнопки)
    if step == "payment":
        low = text.lower()
        if "безнал" in low:
            session["payment_type"] = "безнал"
            ask_step_company(token, chat_id, session)
        elif "нал" in low:
            session["payment_type"] = "наличные"
            ask_step_contact(token, chat_id, session)
        else:
            send_message(token, chat_id, "Пожалуйста, выберите способ оплаты кнопкой ниже:", kb_payment(session))
        return

    # ШАГ 7б: НАЗВАНИЕ КОМПАНИИ (при выборе Безнала)
    if step == "company":
        session["company_name"] = text
        ask_step_contact(token, chat_id, session)
        return

    # ШАГ 8: КОНТАКТНЫЙ ТЕЛЕФОН
    if step == "contact":
        session["contact"] = text
        ask_step_comment(token, chat_id, session)
        return

    # ШАГ 9 и ФИНАЛ: ОТДЕЛЬНЫЕ СООБЩЕНИЯ / ПОЖЕЛАНИЯ К ЗАЯВКЕ
    if step in ("comment", "done"):
        if text.lower() not in ("нет", "пропустить", "-"):
            session["extra_messages"].append(text)
        show_final_order(token, chat_id, session)
        return


# ==============================================================================
# ЗАПУСК БОТА
# ==============================================================================
def resolve_token() -> str:
    if BOT_TOKEN.strip():
        return BOT_TOKEN.strip()
    env_tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if env_tok:
        return env_tok
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("bot_token"):
                    return cfg["bot_token"].strip()
        except Exception:
            pass

    print("=" * 65)
    print("НАСТРОЙКА TELEGRAM-БОТА (ПЕРВЫЙ ЗАПУСК)")
    print("=" * 65)
    tok = input("Вставьте токен вашего бота от @BotFather и нажмите Enter: ").strip()
    if tok:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"bot_token": tok}, f, ensure_ascii=False, indent=2)
            print(f"Токен сохранён в {CONFIG_FILE}!")
        except Exception:
            pass
    return tok


def main():
    token = resolve_token()
    if not token:
        print("Ошибка: токен не указан.")
        sys.exit(1)

    try:
        me = tg_api(token, "getMe")
        bot_info = me.get("result", {})
        print("=" * 65)
        print(f"✅ Пошаговый клиентский бот запущен: @{bot_info.get('username')}")
        print(f"Готовые заявки перенаправляются на: @{MANAGER_USERNAME}")
        print("Для остановки бота нажмите Ctrl+C.")
        print("=" * 65)
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram API: {e}")
        sys.exit(1)

    offset = 0
    while True:
        try:
            resp = tg_api(token, "getUpdates", {"offset": offset, "timeout": 25})
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    handle_callback(token, upd["callback_query"])
                elif "message" in upd:
                    handle_message(token, upd["message"])
        except KeyboardInterrupt:
            print("\nБот остановлен.")
            break
        except Exception as e:
            print(f"Переподключение через 3 сек ({e})...")
            time.sleep(3)


if __name__ == "__main__":
    main()
