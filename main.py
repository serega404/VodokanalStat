import os
from dotenv import load_dotenv

load_dotenv()

import datetime
import re
import calendar
import argparse
import asyncio
from collections import Counter

from telethon import TelegramClient, events
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
import json

from report import create_report

# Конфиг

API_ID = int(os.environ.get('TG_API_ID', '0'))
API_HASH = os.environ.get('TG_API_HASH', '')
TELEGRAM_CHANNEL = os.environ.get('TG_CHANNEL', '')
FORWARD_FROM = os.environ.get('TG_FORWARD_FROM', '')
FORWARD_TO = os.environ.get('TG_FORWARD_TO', TELEGRAM_CHANNEL)
SEND_TO = os.environ.get('TG_SEND_TO', TELEGRAM_CHANNEL)
BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '').strip()

SEND_SILENT = os.environ.get('SEND_SILENT', '').strip().lower() in {'1', 'true', 'yes', 'on'}

_TIME_RANGE_PATTERN = re.compile(r"(\d{1,2})\s*[-:]\s*(\d{2})")
_HOUR_ONLY_PATTERN = re.compile(r"(\d{1,2})\s*ч\b", re.IGNORECASE)

def send_report_via_bot(files, message_text):
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    media = []
    files_payload = {}
    for idx, path in enumerate(files):
        attach_name = f"file{idx}"
        files_payload[attach_name] = open(path, "rb")
        item = {
            "type": "photo",
            "media": f"attach://{attach_name}",
        }
        if idx == 0:
            item["caption"] = message_text
        media.append(item)

    try:
        resp = requests.post(
            f"{base_url}/sendMediaGroup",
            data={
                "chat_id": SEND_TO,
                "disable_notification": SEND_SILENT,
                "media": json.dumps(media),
            },
            files=files_payload,
            timeout=90,
        )
        if not resp.ok:
            print(f"Ошибка отправки: {resp.status_code} {resp.text}")
            exit(1)
    finally:
        for fh in files_payload.values():
            fh.close()

async def forward_via_bot(message, target_chat):
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    # Ensure temp dir
    temp_dir = os.path.join("data", "temp_forward")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    try:
        if message.media:
            path = await message.download_media(file=temp_dir)
            
            if not path:
                 if message.text:
                     data = {"chat_id": target_chat, "text": message.text, "disable_notification": SEND_SILENT}
                     await asyncio.to_thread(requests.post, f"{base_url}/sendMessage", data=data)
                 return

            method = "sendDocument"
            file_key = "document"
            
            if getattr(message, 'photo', None):
                method = "sendPhoto"
                file_key = "photo"
            elif getattr(message, 'video', None):
                method = "sendVideo"
                file_key = "video"
            elif getattr(message, 'voice', None):
                method = "sendVoice"
                file_key = "voice"
            elif getattr(message, 'audio', None):
                method = "sendAudio"
                file_key = "audio"
            
            if not os.path.exists(path):
                 return

            with open(path, "rb") as f:
                data = {
                    "chat_id": target_chat,
                    "caption": message.text or "",
                    "disable_notification": SEND_SILENT
                }
                files = {file_key: f}
                
                resp = await asyncio.to_thread(requests.post, f"{base_url}/{method}", data=data, files=files)
            
            try:
                os.remove(path)
            except:
                pass
                
            if not resp.ok:
                 print(f"Ошибка Bot API ({method}): {resp.status_code} {resp.text}")

        elif message.text:
            data = {
                "chat_id": target_chat,
                "text": message.text,
                "disable_notification": SEND_SILENT
            }
            resp = await asyncio.to_thread(requests.post, f"{base_url}/sendMessage", data=data)
            if not resp.ok:
                print(f"Ошибка Bot API (sendMessage): {resp.status_code} {resp.text}")

    except Exception as e:
        print(f"Ошибка forward_via_bot: {e}")

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

async def report_job(client, days_count: int):
    print(f"Формирование отчета за {days_count} дн.")
    try:
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

        files, message_text = create_report(
            day_counter=day_counter,
            hour_counter=hour_counter,
            parsed_hour_counter=parsed_hour_counter,
            total_messages=total_messages,
            parsed_messages_count=parsed_messages_count,
            days_count=days_count,
        )
        
        if not BOT_TOKEN:
            await client.send_file(
                SEND_TO,
                files,
                caption=message_text,
                silent=SEND_SILENT
            )
        else:
            await asyncio.to_thread(send_report_via_bot, files, message_text)
            
    except Exception as e:
        print(f"Ошибка при формировании отчета: {e}")

async def main():
    if not os.path.exists('data'):
        os.makedirs('data')

    if not API_ID or not API_HASH:
        print("Ошибка: переменные окружения TG_API_ID и TG_API_HASH должны быть установлены.")
        exit(1)

    if (not TELEGRAM_CHANNEL) or (TELEGRAM_CHANNEL.strip() == ''):
        print("Ошибка: переменная окружения TG_CHANNEL должна быть установлена.")
        exit(1)

    parser = argparse.ArgumentParser(description="ВодоКанал статистика публикаций")
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Включить еженедельные отчеты."
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Включить ежемесячные отчеты."
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Создать сессию Telegram и завершить выполнение."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Запустить выбранные отчеты (weekly/monthly) немедленно при старте."
    )

    args = parser.parse_args()

    client = TelegramClient('data/session', API_ID, API_HASH)

    if args.auth:
        print("Создание сессии Telegram...")
        async with client:
            pass
        print("Сессия создана.")
        exit(0)

    await client.start()

    if FORWARD_FROM:
        print(f"Включаем пересылку сообщений из {FORWARD_FROM} в {FORWARD_TO}")
        @client.on(events.NewMessage(chats=FORWARD_FROM))
        async def forward_handler(event):
            text = event.message.text or ""
            if not any(keyword in text.lower() for keyword in ["аварийные", "работы", "продлены", "аварийных", "работ", "продлеваются"]):
                return
            
            try:
                if BOT_TOKEN:
                    await forward_via_bot(event.message, FORWARD_TO)
                else:
                    # Отправляем копию сообщения (без тега пересылки)
                    await client.send_message(FORWARD_TO, event.message.text, file=event.message.media, silent=SEND_SILENT)
            except Exception as e:
                print(f"Ошибка пересылки: {e}")

    scheduler = AsyncIOScheduler()

    async def monthly_wrapper():
        days = days_in_prev_month()
        await report_job(client, days)

    if args.weekly:
        # Каждый понедельник в 00:00
        scheduler.add_job(report_job, CronTrigger(day_of_week='mon', hour=0, minute=0), args=[client, 7])
        print("Планировщик: Weekly отчет включен (Пн, 00:00).")
        
        if args.run_now:
            print("Instant Run: Запуск Weekly отчета...")
            asyncio.create_task(report_job(client, 7))

    if args.monthly:
        # 1 числа каждого месяца в 00:00
        scheduler.add_job(monthly_wrapper, CronTrigger(day=1, hour=0, minute=0))
        print("Планировщик: Monthly отчет включен (1-е число, 00:00).")

        if args.run_now:
            print("Instant Run: Запуск Monthly отчета...")
            asyncio.create_task(monthly_wrapper())

    scheduler.start()
    print("Сервис запущен.")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
