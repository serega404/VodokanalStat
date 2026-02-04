import os
import datetime
import re
import calendar
import argparse
import asyncio
from collections import Counter

from telethon import TelegramClient

from report import create_report

# Конфиг

API_ID = int(os.environ.get('TG_API_ID', '0'))
API_HASH = os.environ.get('TG_API_HASH', '')
TELEGRAM_CHANNEL = os.environ.get('TG_CHANNEL', '')
SEND_TO = os.environ.get('TG_SEND_TO', TELEGRAM_CHANNEL)

SEND_SILENT = os.environ.get('SEND_SILENT', '').strip().lower() in {'1', 'true', 'yes', 'on'}

_TIME_RANGE_PATTERN = re.compile(r"(\d{1,2})\s*[-:]\s*(\d{2})")
_HOUR_ONLY_PATTERN = re.compile(r"(\d{1,2})\s*ч\b", re.IGNORECASE)

def days_in_prev_month():
    today = datetime.datetime.now()
    year = today.year
    month = today.month
    # Если январь, то предыдущий месяц — декабрь прошлого года
    if month == 1:
        prev_month = 12
        year -= 1
    else:
        prev_month = month - 1
    return calendar.monthrange(year, prev_month)[1]


def extract_time(text):
    # Извлекает время из строки. Возвращает объект datetime.time или None.
    # Поддерживает форматы: "до 17-00", "17- 00", "23:00", "12ч", "1ч"
    # Ищем HH-MM или HH:MM
    match = _TIME_RANGE_PATTERN.search(text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return datetime.time(hour=hour, minute=minute)
        else:
            return None
    # Ищем HHч
    match = _HOUR_ONLY_PATTERN.search(text)
    if match:
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return datetime.time(hour=hour, minute=0)
        else:
            return None
    return None

async def main(days_count: int):
    if (not TELEGRAM_CHANNEL) or (TELEGRAM_CHANNEL.strip() == ''):
        print("Ошибка: переменная окружения TG_CHANNEL должна быть установлена.")
        exit(1)
    
    client = TelegramClient('data/session', API_ID, API_HASH)
    async with client:
        channel = await client.get_entity(TELEGRAM_CHANNEL)
        if isinstance(channel, list):
            channel = channel[0]

        start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_count)

        day_counter = Counter()
        hour_counter = Counter()
        parsed_hour_counter = Counter()
        total_messages = 0

        async for message in client.iter_messages(channel):
            msg_date = message.date
            if msg_date is None:
                continue
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=datetime.timezone.utc)
            else:
                msg_date = msg_date.astimezone(datetime.timezone.utc)

            if msg_date < start_date:
                break

            # Пропускаем пересланные сообщения
            if getattr(message, 'fwd_from', None):
                continue

            text = message.text or ""
            if not text:
                continue
            if any(tag in text for tag in ("#полезное", "#статистика")):
                continue

            total_messages += 1
            day_counter[msg_date.date()] += 1
            hour_counter[msg_date.hour] += 1

            parsed_time = extract_time(text)
            if parsed_time:
                parsed_hour_counter[parsed_time.hour] += 1

        parsed_messages_count = sum(parsed_hour_counter.values())

        channel_name = getattr(channel, 'title', 'Unknown Channel')
        print(f"Получено {total_messages} сообщений из {channel_name} за последние {days_count} дней.")
        print(f"Найдено {parsed_messages_count} сообщений с временной меткой")
        # for dt, txt in time_messages:
            # parsed_time = extract_time(txt)
            # print(f"{dt}: {txt} -> {parsed_time}")

        files, message_text = create_report(
            day_counter=day_counter,
            hour_counter=hour_counter,
            parsed_hour_counter=parsed_hour_counter,
            total_messages=total_messages,
            parsed_messages_count=parsed_messages_count,
            days_count=days_count,
        )
        await client.send_file(
            SEND_TO,
            files,
            caption=message_text,
            silent=SEND_SILENT
        )

if __name__ == "__main__":
    if not os.path.exists('data'):
        os.makedirs('data')

    if not API_ID or not API_HASH:
        print("Ошибка: переменные окружения TG_API_ID и TG_API_HASH должны быть установлены.")
        exit(1)

    parser = argparse.ArgumentParser(description="ВодоКанал статистика публикаций")
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Сформировать статистику за последние 7 дней."
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Сформировать статистику за предыдущий полный месяц."
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Создать сессию Telegram и завершить выполнение."
    )

    args = parser.parse_args()

    if args.auth:
        async def auth():
            client = TelegramClient('data/session', API_ID, API_HASH)
            async with client:
                pass
            print("Сессия создана.")
        print("Создание сессии Telegram...")
        asyncio.run(auth())
        exit(0)
    if args.weekly and args.monthly:
        parser.error("Параметры --weekly и --monthly взаимоисключающие.")

    if args.monthly:
        selected_days = days_in_prev_month()
    else:
        selected_days = 7

    asyncio.run(main(selected_days))
