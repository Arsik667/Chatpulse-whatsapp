"""Парсинг экспорта чата WhatsApp в pandas.DataFrame.

WhatsApp отдаёт чат как .txt, а экспорт «с медиа» — как .zip, внутри которого
лежит тот же .txt плюс фото и видео. Формат строк зависит от платформы и локали:

    Android:  31.12.20, 23:59 - Иван: Привет
              12/31/20, 11:59 PM - John: Hi
    iOS:      [31.12.20, 23:59:59] Иван: Привет
              [12/31/20, 11:59:59 PM] John: Hi

Как работает парсер:
1. read_export()       — байты файла → текст (распаковка .zip, кодировка);
2. detect_platform()   — Android или iOS, по первым строкам файла;
3. parse_chat()        — строки → сообщения: многострочные склеиваем,
                         порядок «день/месяц» определяем по всем датам файла,
                         каждое сообщение относим к одному из типов KINDS.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from .messages import DEFAULT_LANG, message

# Типы сообщений (колонка `kind`):
#   text    — обычный текст
#   media   — фото / видео / стикер / документ (сам файл в .txt не попадает)
#   call    — аудио- или видеозвонок (iOS пишет их прямо в переписку)
#   deleted — «Это сообщение удалено»
#   system  — служебные события: шифрование, смена темы, кого-то добавили...
KINDS = ("text", "media", "call", "deleted", "system")

COLUMNS = ["timestamp", "author", "text", "kind", "call_type", "call_missed", "call_duration_s"]

# Сколько непустых строк смотрим, чтобы определить платформу.
DETECT_LINES = 200

# Больше этого не распаковываем из .zip — защита от zip-бомб.
MAX_CHAT_BYTES = 200 * 1024 * 1024

# LRM (U+200E) — невидимый символ направления текста. iOS ставит его перед
# медиа, звонками и служебными сообщениями: для классификации он полезен,
# а в самом тексте — мусор.
LRM = "\u200e"


class ChatParseError(ValueError):
    """Файл не удалось разобрать.

    code — ключ из messages.MESSAGES, по нему текст переводится: exc.text("en").
    str(exc) — тот же текст по-русски.
    """

    def __init__(self, code: str, **params):
        self.code = code
        self.params = params
        super().__init__(message(code, DEFAULT_LANG, **params))

    def text(self, lang: str = DEFAULT_LANG) -> str:
        return message(self.code, lang, **self.params)


@dataclass
class ParsedChat:
    messages: pd.DataFrame  # колонки COLUMNS, по одной строке на сообщение
    platform: str           # "android" | "ios"
    date_order: str         # "DMY" | "MDY" | "YMD"


# --- заголовок сообщения: дата, время, остаток строки --------------------------

_DATE = r"(?P<date>\d{1,4}[./-]\d{1,2}[./-]\d{1,4})"
# 23:59 | 23:59:59 | 11:59 PM | 11:59 p. m.
_TIME = r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)(?:\s?(?P<ampm>[ap]\.?\s?m\.?))?"

HEADER_RE = {
    "android": re.compile(rf"^{_DATE},?\s{_TIME}\s[-–]\s(?P<rest>.*)$", re.IGNORECASE),
    "ios": re.compile(rf"^\[{_DATE},?\s{_TIME}\]\s?(?P<rest>.*)$", re.IGNORECASE),
}

# «Имя: текст». Кавычки в имени запрещаем, чтобы служебное
# «Иван изменил тему на "План: лето"» не превратилось в сообщение от автора
# «Иван изменил тему на "План».
_AUTHOR_RE = re.compile(r'^(?P<author>[^:"«»“”\n]{1,80}):(?:\s(?P<text>.*))?$', re.DOTALL)


# --- классификация текста сообщения -------------------------------------------

_MEDIA_RE = re.compile(
    r"^<(?:media omitted|без медиафайлов|медиафайл отсутствует|медиа отсутству[ею]т)>$"
    r"|\b(?:image|video|audio|sticker|gif|document|contact card) omitted$"
    r"|\b(?:изображение|фото|видео|аудио|аудиофайл|стикер|gif|документ|карточка контакта)"
    r" отсутствует$"
    r"|\((?:file attached|файл добавлен|файл прикрепл[её]н)\)$"
    r"|^<(?:attached|вложение|прикреплено): [^>]+>$",
    re.IGNORECASE,
)

_DELETED_RE = re.compile(
    r"^(?:this message was deleted|you deleted this message"
    r"|(?:данное|это) сообщение удалено|вы удалили (?:данное|это) сообщение)\.?$",
    re.IGNORECASE,
)

# Приписка к отредактированным сообщениям — из текста её убираем.
_EDITED_RE = re.compile(r"\s*<(?:this message was edited|сообщение изменено)>$", re.IGNORECASE)

# «Voice call, 12 min» / «Missed video call» / «Пропущенный аудиозвонок» / «Видеозвонок, 1 ч»
_CALL_RE = re.compile(
    r"^(?P<missed>missed |silenced |пропущенный )?(?:group |групповой )?"
    r"(?P<media>voice|video|аудио|видео) ?(?:call|звонок)"
    r"(?:, ?(?P<details>.*))?$",
    re.IGNORECASE,
)
_NO_ANSWER_RE = re.compile(r"no answer|declined|нет ответа|без ответа|не отвечает|отклон", re.IGNORECASE)
_CLOCK_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})")          # 1:05:30 | 12:40
_DURATION_RE = re.compile(r"(\d+)\s*([hmsчмс])[a-zа-я]*", re.IGNORECASE)  # 1 hr 5 min | 12 мин
_UNIT_SECONDS = {"h": 3600, "ч": 3600, "m": 60, "м": 60, "s": 1, "с": 1}

# Уведомления о шифровании и смене кода безопасности — всегда служебные.
# На iOS они приходят «от имени» собеседника, поэтому одного отсутствия автора мало.
_NOTICE_RE = re.compile(
    r"^(?:messages|сообщения)\b.*(?:end-to-end encrypt|сквозным шифрованием)"
    r"|^(?:your )?security code with .+ changed"
    r"|^(?:ваш )?код безопасности\b.*изменил",
    re.IGNORECASE,
)

# Прочие события группы. Сверяем только сообщения, начинающиеся с LRM, —
# у обычного текста его нет, поэтому «I added you to the doc» останется текстом.
_EVENT_RE = re.compile(
    r"\b(?:created (?:group|this group)|added|left|removed|joined using"
    r"|changed (?:the|this|their|to)|pinned a message|blocked|unblocked"
    r"|turned (?:on|off) disappearing|waiting for this message)\b"
    r"|создал|добавил|покинул|вышел|удалил|изменил|присоединил|закрепил"
    r"|заблокировал|исчезающие сообщения|ожидание сообщения",
    re.IGNORECASE,
)


# --- чтение файла -------------------------------------------------------------

def read_export(data: bytes, filename: str = "") -> str:
    """Байты загруженного файла → текст чата. Понимает .txt и .zip."""
    is_zip = data[:4] == b"PK\x03\x04"
    if filename.lower().endswith(".zip") and not is_zip:
        raise ChatParseError("not_a_zip")
    if is_zip:
        data = _chat_from_zip(data)

    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    # WhatsApp пишет в UTF-8; битые байты заменяем, а не падаем.
    return data.decode("utf-8-sig", errors="replace")


def _chat_from_zip(data: bytes) -> bytes:
    """Достаёт из архива .txt с перепиской, медиафайлы не трогает."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            txts = [
                info for info in zf.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith(".txt")
                and not info.filename.startswith("__MACOSX/")
            ]
            if not txts:
                raise ChatParseError("zip_without_chat")

            # Обычно .txt в архиве один. Но если в чат пересылали .txt-документы,
            # берём тот, чьи первые строки больше всего похожи на переписку.
            chat = txts[0] if len(txts) == 1 else max(txts, key=lambda info: _header_score(zf, info))
            if chat.file_size > MAX_CHAT_BYTES:
                raise ChatParseError("chat_too_large")
            return zf.read(chat)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        # RuntimeError — архив с паролем, NotImplementedError — редкое сжатие.
        raise ChatParseError("zip_unreadable", reason=str(exc)) from exc


def _header_score(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    with zf.open(info) as f:
        head = f.read(64 * 1024).decode("utf-8", errors="replace")
    lines = [_clean_line(line) for line in head.splitlines()[:DETECT_LINES]]
    return max(sum(bool(rx.match(line)) for line in lines) for rx in HEADER_RE.values())


# --- разбор текста ------------------------------------------------------------

def _clean_line(line: str) -> str:
    # iOS ставит «узкий неразрывный пробел» U+202F перед AM/PM и LRM в начало строки.
    return line.replace("\u202f", " ").replace("\xa0", " ").lstrip("\ufeff" + LRM).rstrip()


def detect_platform(lines: list[str]) -> str:
    """Android или iOS — смотрим, какая регулярка чаще срабатывает в начале файла."""
    scores = dict.fromkeys(HEADER_RE, 0)
    checked = 0
    for line in lines:
        line = _clean_line(line)
        if not line:
            continue
        for platform, rx in HEADER_RE.items():
            if rx.match(line):
                scores[platform] += 1
        checked += 1
        if checked >= DETECT_LINES:
            break

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        raise ChatParseError("unknown_format")
    return best


def detect_date_order(dates: list[str], uses_ampm: bool) -> str:
    """ДД.ММ или ММ/ДД? По одной дате не понять (01/02 — это 1 февраля или 2 января?),
    поэтому ищем по всему файлу дату, где одно из чисел > 12."""
    parts = [re.split(r"[./-]", d) for d in set(dates)]
    if len(parts[0][0]) == 4:
        return "YMD"
    if any(int(p[0]) > 12 for p in parts):
        return "DMY"
    if any(int(p[1]) > 12 for p in parts):
        return "MDY"
    # Всё неоднозначно: 12-часовой формат почти всегда означает американскую локаль.
    return "MDY" if uses_ampm else "DMY"


def _to_datetime(date_s: str, time_s: str, ampm: str | None, order: str,
                 date_cache: dict) -> datetime | None:
    if date_s not in date_cache:
        a, b, c = (int(x) for x in re.split(r"[./-]", date_s))
        y, m, d = {"DMY": (c, b, a), "MDY": (c, a, b), "YMD": (a, b, c)}[order]
        date_cache[date_s] = (y + 2000 if y < 100 else y, m, d)
    year, month, day = date_cache[date_s]

    hour, minute, *sec = (int(x) for x in re.split(r"[:.]", time_s))
    if ampm:
        hour = hour % 12 + (12 if ampm.lower().startswith("p") else 0)
    try:
        return datetime(year, month, day, hour, minute, sec[0] if sec else 0)
    except ValueError:  # 31.02 и прочие невозможные даты
        return None


def _parse_duration(details: str) -> float | None:
    if clock := _CLOCK_RE.search(details):
        h, m, s = clock.groups()
        return float(int(h or 0) * 3600 + int(m) * 60 + int(s))
    parts = _DURATION_RE.findall(details)
    if not parts:
        return None
    return float(sum(int(num) * _UNIT_SECONDS[unit.lower()] for num, unit in parts))


def classify(author: str | None, text: str) -> tuple[str, str, tuple]:
    """Определяет тип сообщения. Возвращает (kind, очищенный текст, данные звонка)."""
    had_lrm = text.startswith(LRM)
    text = _EDITED_RE.sub("", text.replace(LRM, "")).strip()
    no_call = (None, None, None)

    if author is None or _NOTICE_RE.search(text):
        return "system", text, no_call
    if _DELETED_RE.match(text):
        return "deleted", text, no_call
    if call := _CALL_RE.match(text):
        details = call["details"] or ""
        missed = bool(call["missed"]) or bool(_NO_ANSWER_RE.search(details))
        call_type = "video" if call["media"].lower() in ("video", "видео") else "voice"
        return "call", text, (call_type, missed, None if missed else _parse_duration(details))
    if _MEDIA_RE.search(text):
        return "media", text, no_call
    if had_lrm and _EVENT_RE.search(text):
        return "system", text, no_call
    return "text", text, no_call


def parse_chat(text: str) -> ParsedChat:
    """Текст экспорта → ParsedChat с DataFrame сообщений."""
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise ChatParseError("empty_file")

    platform = detect_platform(lines)
    header_re = HEADER_RE[platform]

    # Проход 1: режем файл на сообщения. Строка без даты в начале —
    # продолжение предыдущего (многострочного) сообщения.
    raw: list[list] = []  # [date, time, ampm, rest]
    for line in lines:
        line = _clean_line(line)
        if m := header_re.match(line):
            raw.append([m["date"], m["time"], m["ampm"], m["rest"]])
        elif raw:
            raw[-1][3] += "\n" + line

    # Проход 2: даты, авторы, типы.
    order = detect_date_order([r[0] for r in raw], uses_ampm=any(r[2] for r in raw))
    date_cache: dict = {}  # локальный кеш: между запросами ничего не храним
    rows = []
    for date_s, time_s, ampm, rest in raw:
        ts = _to_datetime(date_s, time_s, ampm, order, date_cache)
        if ts is None:
            continue
        if am := _AUTHOR_RE.match(rest):
            # «~ Имя» — так новые версии WhatsApp помечают номера не из контактов.
            author = am["author"].replace(LRM, "").strip().lstrip("~").strip()
            body = am["text"] or ""
        else:
            author, body = None, rest
        kind, body, call = classify(author or None, body)
        rows.append((ts, author or None, body, kind, *call))

    if not rows:
        raise ChatParseError("no_valid_dates")

    df = pd.DataFrame(rows, columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["call_missed"] = df["call_missed"].astype("boolean")
    df["call_duration_s"] = df["call_duration_s"].astype("float64")
    # Экспорт и так хронологический, но если на телефоне меняли время, строки
    # могут идти не по порядку. Сортировка стабильная — порядок внутри одной
    # минуты (Android пишет время без секунд) сохраняется.
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return ParsedChat(messages=df, platform=platform, date_order=order)


def load_chat(data: bytes, filename: str = "") -> ParsedChat:
    """Главная точка входа: байты .txt/.zip → ParsedChat."""
    return parse_chat(read_export(data, filename))
