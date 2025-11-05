import os
import datetime
import re
import calendar
import argparse
from collections import Counter
from statistics import mean, median

from telethon.sync import TelegramClient
import matplotlib.pyplot as plt

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

def plural_days(n):
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return "дней"
    elif n % 10 == 1:
        return "день"
    elif 2 <= n % 10 <= 4:
        return "дня"
    else:
        return "дней"

def main(days_count: int):
    if (not TELEGRAM_CHANNEL) or (TELEGRAM_CHANNEL.strip() == ''):
        print("Ошибка: переменная окружения TG_CHANNEL должна быть установлена.")
        exit(1)
    
    with client:
        channel = client.get_entity(TELEGRAM_CHANNEL)
        if isinstance(channel, list):
            channel = channel[0]

        start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_count)

        day_counter = Counter()
        hour_counter = Counter()
        parsed_hour_counter = Counter()
        total_messages = 0

        for message in client.iter_messages(channel):
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

        # Группировка по дням
        dates = sorted(day_counter.keys())
        counts = [day_counter[date] for date in dates]

        # Преобразуем даты в формат "дд.MM" для оси X
        date_labels = [date.strftime("%d.%m.%y") for date in dates]
        
        xrotation = 90 # поворот подписей по оси X
        # Добавляем день недели, если это отчёт за неделю
        if days_count == 7:
            xrotation = 0
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            date_labels = [f"{label}\n{weekday_names[date.weekday()]}" for label, date in zip(date_labels, dates)]

        # Градиентный цвет столбцов
        cmap = plt.get_cmap('cool')
        colors = [cmap(i / max(len(dates), 1)) for i in range(len(dates))]

        # Вычисляем среднее и медиану
        if counts:
            avg = mean(counts)
            med = median(counts)
        else:
            avg = med = 0.0

        # --- График по дням ---
        plt.figure(figsize=(16, 6))
        plt.bar(date_labels, counts, color=colors, zorder=2)  # столбцы поверх сетки
        plt.xlabel("Дата")
        plt.ylabel("Количество оповещений")
        plt.title("Статистика уведомлений по дням за (" + str(days_count) + " " + plural_days(days_count) + ")")
        if counts:
            plt.axhline(avg, color='red', linestyle='--', linewidth=1, label=f'Среднее: {avg:.2f}', zorder=3)
            plt.axhline(med, color='green', linestyle='-.', linewidth=1, label=f'Медиана: {med:.2f}', zorder=3)
        # step = max(1, len(date_labels) // days_count)
        # plt.xticks(date_labels[::step], rotation=90)
        plt.xticks(date_labels, rotation=xrotation)
        max_count = max(counts) if counts else 0
        plt.yticks(range(0, max_count, 1 if max_count < 10 else max(1, max_count // 10)))
        plt.grid(axis='y', linestyle='-', alpha=0.8, zorder=1)  # сетка под графиком
        if counts:
            plt.legend()
        plt.tight_layout()
        plt.savefig("data/stat.png", dpi=200)
        plt.close()

        # --- частота оповещений по часам ---
        hour_labels = [f"{h:02d}:00" for h in range(24)]
        hour_counts = [hour_counter.get(h, 0) for h in range(24)]

        plt.figure(figsize=(12, 6))
        cmap2 = plt.get_cmap('plasma')
        colors2 = [cmap2(i / 24) for i in range(24)]
        plt.bar(hour_labels, hour_counts, color=colors2, zorder=2)
        plt.xlabel("Час суток")
        plt.ylabel("Количество оповещений")
        plt.title("Частота публикации оповещений по часам (за " + str(days_count) + " " + plural_days(days_count) + ")")
        plt.xticks(rotation=90)
        # plt.yticks(range(0, max(hour_counts) + 2, 2))
        plt.grid(axis='y', linestyle='-', alpha=0.8, zorder=1)

        total = total_messages
        for i, count in enumerate(hour_counts):
            percent = (count / total * 100) if total > 0 else 0
            if percent > 0:
                plt.text(
                    i, count, f"{percent:.1f}%", ha='center', va='bottom',
                    fontsize=9, color='black', rotation=0
                )

        plt.tight_layout()
        plt.savefig("data/stat_by_hour.png", dpi=200)
        plt.close()

        # --- частота parsed_time по часам ---
        parsed_hour_counts = [parsed_hour_counter.get(h, 0) for h in range(24)]

        plt.figure(figsize=(12, 6))
        cmap3 = plt.get_cmap('viridis')
        colors3 = [cmap3(i / 24) for i in range(24)]
        plt.bar(hour_labels, parsed_hour_counts, color=colors3, zorder=2)
        plt.xlabel("Час")
        plt.ylabel("Количество оповещений")
        plt.text(
            0.5, 0.5, "Приблизительные данные!*", fontsize=45, color='gray',
            ha='center', va='center', alpha=0.2,
            transform=plt.gca().transAxes, zorder=10
        )
        plt.figtext(
            0.05, 0.001, "* Неизвестная точность из-за нечёткого формата сообщений и переносов сроков.",
            fontsize=10, color='black',
            ha='left', va='bottom', alpha=0.4
        )
        plt.title("Время до которого будет завершён ремонт (за " + str(days_count) + " " + plural_days(days_count) + ")")
        plt.xticks(rotation=90)
        # plt.yticks(range(0, max(parsed_hour_counts) + 2, 2))
        plt.grid(axis='y', linestyle='-', alpha=0.8, zorder=1)

        total_parsed = parsed_messages_count
        for i, count in enumerate(parsed_hour_counts):
            percent = (count / total_parsed * 100) if total_parsed > 0 else 0
            if percent > 0:
                plt.text(
                    i, count, f"{percent:.1f}%", ha='center', va='bottom',
                    fontsize=9, color='black', rotation=0
                )

        plt.tight_layout()
        plt.savefig("data/stat_by_parsed_hour.png", dpi=200)
        plt.close()

        # --- отправка статистики одним сообщением ---
        message_text = (
            f"Статистика за {days_count} " + plural_days(days_count) + "\n"
            f"Среднее количество оповещений в день: {avg:.2f}\n"
            f"Медиана: {med:.2f}"
            f"\nВсего оповещений: {total_messages}\n"
            f"\n#статистика"
        )
        files = [
            "data/stat.png",
            "data/stat_by_hour.png",
            "data/stat_by_parsed_hour.png"
        ]
        client.send_file(
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

    client = TelegramClient('data/session', API_ID, API_HASH).start()
    client.session.save_entities = False

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
        print("Создание сессии Telegram...")
        exit(0)
    if args.weekly and args.monthly:
        parser.error("Параметры --weekly и --monthly взаимоисключающие.")

    if args.monthly:
        selected_days = days_in_prev_month()
    else:
        selected_days = 7

    main(selected_days)

