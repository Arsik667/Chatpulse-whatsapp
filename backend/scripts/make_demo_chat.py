"""Генератор синтетического чата WhatsApp — для демо и замера скорости.

    python scripts/make_demo_chat.py --messages 50000 --platform ios --out demo.txt

Переписка полностью выдуманная: реальные чаты в репозиторий не кладём.
У «участников» разный характер, чтобы на дашборде было что посмотреть:
Алиса отвечает быстро и пишет короче, Максим — медленнее, но чаще звонит.
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

LRM = "\u200e"

PEOPLE = {
    # имя: (средняя задержка ответа в секундах, вероятность звонка вместо сообщения)
    "Алиса": (45, 0.002),
    "Максим": (240, 0.008),
}

PHRASES = [
    "привет", "как дела?", "норм, работаю", "го гулять вечером?", "давай в семь",
    "я опаздываю минут на десять", "купи хлеба пожалуйста", "смотри что нашла",
    "ахахах", "это лучшее что я видел сегодня", "спишемся позже", "уже еду",
    "котик опять уронил цветок", "какой фильм посмотрим?", "может пиццу закажем",
    "доброе утро", "спокойной ночи", "ты где?", "скинь фотки с выходных",
    "завтра дедлайн, не могу", "поздравляю!!!", "кофе?", "в метро, плохо ловит",
    "хочу на море", "напомни про субботу", "вот это да", "согласна", "обожаю этот плейлист",
]
EMOJI = ["😂", "❤️", "👍", "🔥", "😍", "🙈", "😭", "🥲", "👀", "🎉", "🤔", "☕", "🐱"]
LINKS = ["https://youtu.be/dQw4w9WgXcQ", "https://maps.app.goo.gl/xyz", "https://habr.com/ru/articles/1/"]

# Частоты по закону Ципфа: первые фразы и эмодзи встречаются заметно чаще —
# как в живой переписке, иначе облако слов получается «плоским».
PHRASE_WEIGHTS = [1 / (i + 1) ** 0.8 for i in range(len(PHRASES))]
EMOJI_WEIGHTS = [1 / (i + 1) for i in range(len(EMOJI))]


def random_text(rnd: random.Random) -> str:
    text = rnd.choices(PHRASES, PHRASE_WEIGHTS)[0]
    if rnd.random() < 0.35:
        text += " " + rnd.choices(EMOJI, EMOJI_WEIGHTS)[0] * rnd.randint(1, 3)
    if rnd.random() < 0.03:
        text = f"{rnd.choice(LINKS)} {text}"
    if rnd.random() < 0.03:
        text += "\n" + rnd.choice(PHRASES)  # многострочное сообщение
    return text


def fmt(platform: str, t: datetime, author: str, text: str) -> str:
    if platform == "ios":
        return f"[{t:%d.%m.%y, %H:%M:%S}] {author}: {text}"
    return f"{t:%d.%m.%y, %H:%M} - {author}: {text}"


def special(platform: str, kind: str, rnd: random.Random) -> str:
    """Медиа / удалённое / звонок в формате нужной платформы."""
    ios = platform == "ios"
    if kind == "media":
        return f"{LRM}изображение отсутствует" if ios else "<Без медиафайлов>"
    if kind == "deleted":
        return "Это сообщение удалено"
    if rnd.random() < 0.25:
        return f"{LRM}Пропущенный аудиозвонок"
    minutes = rnd.randint(1, 90)
    duration = f"{minutes // 60} ч {minutes % 60} мин" if minutes >= 60 else f"{minutes} мин"
    return f"{LRM}{rnd.choice(['Аудиозвонок', 'Видеозвонок'])}, {LRM}{duration}"


def generate(n_messages: int, platform: str, seed: int = 42) -> str:
    rnd = random.Random(seed)
    names = list(PEOPLE)
    t = datetime(2025, 9, 1, 9, 0)
    lines = [fmt(platform, t, names[0], f"{LRM}Сообщения и звонки защищены сквозным шифрованием.")]

    written = 0
    while written < n_messages:
        # Новый разговор: пауза в среднем 9 часов, ночью никто не пишет.
        t += timedelta(hours=rnd.expovariate(1 / 9))
        if t.hour < 8:
            t = t.replace(hour=rnd.randint(8, 11), minute=rnd.randint(0, 59))
        author = rnd.choice(names)
        length = rnd.randint(2, 30) * (2 if t.weekday() >= 5 else 1)  # в выходные болтают дольше

        for _ in range(length):
            if rnd.random() < 0.55:  # собеседник отвечает — со своей скоростью
                author = names[1 - names.index(author)]
                t += timedelta(seconds=rnd.expovariate(1 / PEOPLE[author][0]))
            else:  # тот же человек дописывает мысль
                t += timedelta(seconds=rnd.randint(3, 40))

            roll = rnd.random()
            if platform == "ios" and roll < PEOPLE[author][1]:
                text = special(platform, "call", rnd)
            elif roll < 0.06:
                text = special(platform, "media", rnd)
            elif roll < 0.07:
                text = special(platform, "deleted", rnd)
            else:
                text = random_text(rnd)
            lines.append(fmt(platform, t, author, text))
            written += 1
            if written >= n_messages:
                break
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Синтетический экспорт WhatsApp-чата.")
    parser.add_argument("--messages", type=int, default=3000, help="сколько сообщений (по умолчанию 3000)")
    parser.add_argument("--platform", choices=["android", "ios"], default="ios")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("demo_chat.txt"))
    args = parser.parse_args()

    args.out.write_text(generate(args.messages, args.platform, args.seed), encoding="utf-8")
    print(f"Готово: {args.out} ({args.messages} сообщений, {args.platform})")


if __name__ == "__main__":
    main()
