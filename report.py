import os
from statistics import mean, median

import matplotlib.pyplot as plt


def plural_days(n: int) -> str:
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return "дней"
    if n % 10 == 1:
        return "день"
    if 2 <= n % 10 <= 4:
        return "дня"
    return "дней"


def create_report(
    *,
    day_counter,
    hour_counter,
    parsed_hour_counter,
    total_messages: int,
    parsed_messages_count: int,
    days_count: int,
    output_dir: str = "data",
):
    # Группировка по дням
    dates = sorted(day_counter.keys())
    counts = [day_counter[date] for date in dates]

    # Преобразуем даты в формат "дд.MM" для оси X
    date_labels = [date.strftime("%d.%m.%y") for date in dates]

    xrotation = 90  # поворот подписей по оси X
    # Добавляем день недели, если это отчёт за неделю
    if days_count == 7:
        xrotation = 0
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        date_labels = [f"{label}\n{weekday_names[date.weekday()]}" for label, date in zip(date_labels, dates)]

    # Градиентный цвет столбцов
    cmap = plt.get_cmap("cool")
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
        plt.axhline(avg, color="red", linestyle="--", linewidth=1, label=f"Среднее: {avg:.2f}", zorder=3)
        plt.axhline(med, color="green", linestyle="-.", linewidth=1, label=f"Медиана: {med:.2f}", zorder=3)
    # step = max(1, len(date_labels) // days_count)
    # plt.xticks(date_labels[::step], rotation=90)
    plt.xticks(date_labels, rotation=xrotation)
    max_count = max(counts) if counts else 0
    plt.yticks(range(0, max_count, 1 if max_count < 10 else max(1, max_count // 10)))
    plt.grid(axis="y", linestyle="-", alpha=0.8, zorder=1)  # сетка под графиком
    if counts:
        plt.legend()
    plt.tight_layout()
    by_day_path = os.path.join(output_dir, "stat.png")
    plt.savefig(by_day_path, dpi=200)
    plt.close()

    # --- частота оповещений по часам ---
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    hour_counts = [hour_counter.get(h, 0) for h in range(24)]

    plt.figure(figsize=(12, 6))
    cmap2 = plt.get_cmap("plasma")
    colors2 = [cmap2(i / 24) for i in range(24)]
    plt.bar(hour_labels, hour_counts, color=colors2, zorder=2)
    plt.xlabel("Час суток")
    plt.ylabel("Количество оповещений")
    plt.title("Частота публикации оповещений по часам (за " + str(days_count) + " " + plural_days(days_count) + ")")
    plt.xticks(rotation=90)
    # plt.yticks(range(0, max(hour_counts) + 2, 2))
    plt.grid(axis="y", linestyle="-", alpha=0.8, zorder=1)

    total = total_messages
    for i, count in enumerate(hour_counts):
        percent = (count / total * 100) if total > 0 else 0
        if percent > 0:
            plt.text(
                i, count, f"{percent:.1f}%", ha="center", va="bottom",
                fontsize=9, color="black", rotation=0
            )

    plt.tight_layout()
    by_hour_path = os.path.join(output_dir, "stat_by_hour.png")
    plt.savefig(by_hour_path, dpi=200)
    plt.close()

    # --- частота parsed_time по часам ---
    parsed_hour_counts = [parsed_hour_counter.get(h, 0) for h in range(24)]

    plt.figure(figsize=(12, 6))
    cmap3 = plt.get_cmap("viridis")
    colors3 = [cmap3(i / 24) for i in range(24)]
    plt.bar(hour_labels, parsed_hour_counts, color=colors3, zorder=2)
    plt.xlabel("Час")
    plt.ylabel("Количество оповещений")
    plt.text(
        0.5, 0.5, "Приблизительные данные!*", fontsize=45, color="gray",
        ha="center", va="center", alpha=0.2,
        transform=plt.gca().transAxes, zorder=10
    )
    plt.figtext(
        0.05, 0.001, "* Неизвестная точность из-за нечёткого формата сообщений и переносов сроков.",
        fontsize=10, color="black",
        ha="left", va="bottom", alpha=0.4
    )
    plt.title("Время до которого будет завершён ремонт (за " + str(days_count) + " " + plural_days(days_count) + ")")
    plt.xticks(rotation=90)
    # plt.yticks(range(0, max(parsed_hour_counts) + 2, 2))
    plt.grid(axis="y", linestyle="-", alpha=0.8, zorder=1)

    total_parsed = parsed_messages_count
    for i, count in enumerate(parsed_hour_counts):
        percent = (count / total_parsed * 100) if total_parsed > 0 else 0
        if percent > 0:
            plt.text(
                i, count, f"{percent:.1f}%", ha="center", va="bottom",
                fontsize=9, color="black", rotation=0
            )

    plt.tight_layout()
    by_parsed_hour_path = os.path.join(output_dir, "stat_by_parsed_hour.png")
    plt.savefig(by_parsed_hour_path, dpi=200)
    plt.close()

    # --- отправка статистики одним сообщением ---
    message_text = (
        f"Статистика за {days_count} " + plural_days(days_count) + "\n"
        f"Среднее количество оповещений в день: {avg:.2f}\n"
        f"Медиана: {med:.2f}"
        f"\nВсего оповещений: {total_messages}\n"
        f"\n#статистика"
    )
    files = [by_day_path, by_hour_path, by_parsed_hour_path]

    return files, message_text
