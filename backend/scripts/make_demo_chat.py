"""Генератор синтетического чата WhatsApp — для демо и замера скорости.

    python scripts/make_demo_chat.py --messages 50000 --platform ios --out demo.txt
    python scripts/make_demo_chat.py --lang en --out ../examples/demo_chat_en.txt

Переписка полностью выдуманная: реальные чаты в репозиторий не кладём.
У «участников» разный характер, чтобы на дашборде было что посмотреть:
Алиса отвечает быстро и пишет короче, Максим — медленнее, но чаще звонит.

Английская версия — тот же чат «в переводе»: случайные числа тянутся в том же
порядке, поэтому времена, длины разговоров и звонки совпадают с русской.
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

LRM = "\u200e"
NNBSP = "\u202f"  # iOS и новые Android ставят узкий неразрывный пробел перед AM/PM

# (средняя задержка ответа в секундах, вероятность звонка вместо сообщения) —
# по порядку имён в локали
TRAITS = [(45, 0.002), (240, 0.008)]

LOCALES = {
    "ru": {
        "names": ["Алиса", "Максим"],
        "phrases": [
            "привет", "как дела?", "норм, работаю", "го гулять вечером?", "давай в семь",
            "я опаздываю минут на десять", "купи хлеба пожалуйста", "смотри что нашла",
            "ахахах", "это лучшее что я видел сегодня", "спишемся позже", "уже еду",
            "котик опять уронил цветок", "какой фильм посмотрим?", "может пиццу закажем",
            "доброе утро", "спокойной ночи", "ты где?", "скинь фотки с выходных",
            "завтра дедлайн, не могу", "поздравляю!!!", "кофе?", "в метро, плохо ловит",
            "хочу на море", "напомни про субботу", "вот это да", "согласна", "обожаю этот плейлист",
        ],
        "notice": "Сообщения и звонки защищены сквозным шифрованием.",
        "media": {"ios": f"{LRM}изображение отсутствует", "android": "<Без медиафайлов>"},
        "deleted": "Это сообщение удалено",
        "missed": f"{LRM}Пропущенный аудиозвонок",
        "calls": ["Аудиозвонок", "Видеозвонок"],
        "hours": "ч",
        "minutes": "мин",
    },
    "en": {
        "names": ["Alice", "Max"],
        "phrases": [
            "hey", "how are you?", "fine, working", "walk tonight?", "let's meet at seven",
            "running ten minutes late", "grab some bread please", "look what I found",
            "hahaha", "best thing I've seen today", "talk later", "on my way",
            "the cat knocked over the plant again", "which movie tonight?", "maybe order pizza",
            "good morning", "good night", "where are you?", "send the weekend photos",
            "deadline tomorrow, can't", "congrats!!!", "coffee?", "on the subway, bad signal",
            "I want to go to the sea", "remind me about saturday", "wow", "agreed", "love this playlist",
        ],
        "notice": "Messages and calls are end-to-end encrypted. No one outside of this chat, "
                  "not even WhatsApp, can read or listen to them.",
        "media": {"ios": f"{LRM}image omitted", "android": "<Media omitted>"},
        "deleted": "This message was deleted",
        "missed": f"{LRM}Missed voice call",
        "calls": ["Voice call", "Video call"],
        "hours": "hr",
        "minutes": "min",
    },
}

EMOJI = ["😂", "❤️", "👍", "🔥", "😍", "🙈", "😭", "🥲", "👀", "🎉", "🤔", "☕", "🐱"]
LINKS = ["https://youtu.be/dQw4w9WgXcQ", "https://maps.app.goo.gl/xyz", "https://habr.com/ru/articles/1/"]

# Частоты по закону Ципфа: первые фразы и эмодзи встречаются заметно чаще —
# как в живой переписке, иначе облако слов получается «плоским».
PHRASE_WEIGHTS = [1 / (i + 1) ** 0.8 for i in range(len(LOCALES["ru"]["phrases"]))]
EMOJI_WEIGHTS = [1 / (i + 1) for i in range(len(EMOJI))]


def random_text(rnd: random.Random, phrases: list[str]) -> str:
    text = rnd.choices(phrases, PHRASE_WEIGHTS)[0]
    if rnd.random() < 0.35:
        text += " " + rnd.choices(EMOJI, EMOJI_WEIGHTS)[0] * rnd.randint(1, 3)
    if rnd.random() < 0.03:
        text = f"{rnd.choice(LINKS)} {text}"
    if rnd.random() < 0.03:
        text += "\n" + rnd.choice(phrases)  # многострочное сообщение
    return text


def fmt(platform: str, lang: str, t: datetime, author: str, text: str) -> str:
    """Строка экспорта: русская локаль — 31.12.25, 23:59; английская (США) — 12/31/25, 11:59 PM."""
    ios = platform == "ios"
    if lang == "ru":
        stamp = f"{t:%d.%m.%y, %H:%M:%S}" if ios else f"{t:%d.%m.%y, %H:%M}"
    else:
        clock = f"{t.hour % 12 or 12}:{t:%M:%S}" if ios else f"{t.hour % 12 or 12}:{t:%M}"
        stamp = f"{t.month}/{t.day}/{t:%y}, {clock}{NNBSP}{'AM' if t.hour < 12 else 'PM'}"
    return f"[{stamp}] {author}: {text}" if ios else f"{stamp} - {author}: {text}"


def special(platform: str, kind: str, rnd: random.Random, loc: dict) -> str:
    """Медиа / удалённое / звонок в формате нужной платформы и языка."""
    if kind == "media":
        return loc["media"][platform]
    if kind == "deleted":
        return loc["deleted"]
    if rnd.random() < 0.25:
        return loc["missed"]
    minutes = rnd.randint(1, 90)
    h, m = divmod(minutes, 60)
    duration = f"{h} {loc['hours']} {m} {loc['minutes']}" if h else f"{m} {loc['minutes']}"
    return f"{LRM}{rnd.choice(loc['calls'])}, {LRM}{duration}"


def generate(n_messages: int, platform: str, seed: int = 42, lang: str = "ru") -> str:
    loc = LOCALES[lang]
    rnd = random.Random(seed)
    names = loc["names"]
    people = dict(zip(names, TRAITS))
    t = datetime(2025, 9, 1, 9, 0)
    lines = [fmt(platform, lang, t, names[0], f"{LRM}{loc['notice']}")]

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
                t += timedelta(seconds=rnd.expovariate(1 / people[author][0]))
            else:  # тот же человек дописывает мысль
                t += timedelta(seconds=rnd.randint(3, 40))

            roll = rnd.random()
            if platform == "ios" and roll < people[author][1]:
                text = special(platform, "call", rnd, loc)
            elif roll < 0.06:
                text = special(platform, "media", rnd, loc)
            elif roll < 0.07:
                text = special(platform, "deleted", rnd, loc)
            else:
                text = random_text(rnd, loc["phrases"])
            lines.append(fmt(platform, lang, t, author, text))
            written += 1
            if written >= n_messages:
                break
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Синтетический экспорт WhatsApp-чата.")
    parser.add_argument("--messages", type=int, default=3000, help="сколько сообщений (по умолчанию 3000)")
    parser.add_argument("--platform", choices=["android", "ios"], default="ios")
    parser.add_argument("--lang", choices=list(LOCALES), default="ru", help="язык переписки и формат дат")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("demo_chat.txt"))
    args = parser.parse_args()

    args.out.write_text(generate(args.messages, args.platform, args.seed, args.lang), encoding="utf-8")
    print(f"Готово: {args.out} ({args.messages} сообщений, {args.platform}, {args.lang})")


if __name__ == "__main__":
    main()
