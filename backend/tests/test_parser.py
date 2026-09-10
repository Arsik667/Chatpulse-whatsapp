"""Тесты парсера на синтетических мини-чатах во всех поддерживаемых форматах."""

import io
import zipfile
from datetime import datetime

import pandas as pd
import pytest

from analyzer_core.parser import ChatParseError, detect_date_order, load_chat, parse_chat, read_export

LRM, NNBSP = "‎", " "

ANDROID_EN = """\
12/31/20, 11:58 PM - Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them. Tap to learn more.
12/31/20, 11:59 PM - John Smith: Happy new year!
See you

tomorrow
1/1/21, 12:00 AM - Jane: <Media omitted>
1/1/21, 12:01 AM - Jane: This message was deleted
1/1/21, 12:02 AM - John Smith: check https://example.com
1/1/21, 12:03 AM - John Smith added Bob
1/13/21, 9:15 AM - Bob: hi <This message was edited>
"""

ANDROID_RU = """\
31.12.2020, 23:59 - Сообщения и звонки защищены сквозным шифрованием. Никто за пределами этого чата не может их прочитать.
31.12.2020, 23:59 - Иван: Привет!
01.01.2021, 00:01 - Мария: <Без медиафайлов>
01.01.2021, 00:02 - Мария: Вы удалили это сообщение
01.01.2021, 00:03 - Иван изменил тему с «Старое: имя» на «Новое»
01.01.2021, 00:04 - ~ Пётр: я не из контактов
"""

IOS_EN = f"""\
[12/31/20, 11:59:01{NNBSP}PM] Chat: {LRM}Messages and calls are end-to-end encrypted. No one outside of this chat can read them.
[12/31/20, 11:59:05{NNBSP}PM] John: Hello
{LRM}[1/1/21, 12:00:10{NNBSP}AM] Jane: {LRM}image omitted
[1/1/21, 12:01:00{NNBSP}AM] Jane: {LRM}Missed voice call, {LRM}Tap to call back
[1/1/21, 12:02:00{NNBSP}AM] John: {LRM}Voice call, {LRM}12 min
[1/1/21, 12:30:00{NNBSP}AM] Jane: {LRM}Video call, {LRM}1 hr 5 min
[1/1/21, 12:40:00{NNBSP}AM] John: {LRM}Voice call, {LRM}No answer
[1/1/21, 12:41:00{NNBSP}AM] Chat: {LRM}John added Bob
[1/13/21, 9:00:00{NNBSP}AM] Bob: I added you to the doc
"""

IOS_RU = f"""\
[31.12.20, 23:59:59] Иван: Привет
[01.01.21, 00:00:01] Мария: {LRM}изображение отсутствует
[01.01.21, 00:01:00] Мария: {LRM}Пропущенный аудиозвонок
[01.01.21, 00:02:00] Иван: {LRM}Видеозвонок, {LRM}1 ч 5 мин
[01.01.21, 00:03:00] Иван: {LRM}<вложение: 00000012-PHOTO-2021-01-01.jpg>
"""


def kinds(chat):
    return chat.messages["kind"].tolist()


# --- форматы --------------------------------------------------------------------

def test_android_en_12h():
    chat = parse_chat(ANDROID_EN)
    df = chat.messages

    assert chat.platform == "android"
    assert chat.date_order == "MDY"  # 1/13/21 — месяц идёт первым
    assert kinds(chat) == ["system", "text", "media", "deleted", "text", "system", "text"]
    assert df.loc[0, "timestamp"] == datetime(2020, 12, 31, 23, 58)
    assert df.loc[2, "timestamp"] == datetime(2021, 1, 1, 0, 0)  # 12:00 AM — полночь
    assert df.loc[1, "author"] == "John Smith"
    assert df.loc[1, "text"] == "Happy new year!\nSee you\n\ntomorrow"  # многострочное
    assert df.loc[6, "text"] == "hi"  # приписка «edited» убрана


def test_android_ru_24h():
    chat = parse_chat(ANDROID_RU)
    df = chat.messages

    assert chat.platform == "android"
    assert chat.date_order == "DMY"
    assert kinds(chat) == ["system", "text", "media", "deleted", "system", "text"]
    assert pd.isna(df.loc[4, "author"])  # у служебного события нет автора
    assert df.loc[5, "author"] == "Пётр"  # «~ » перед номером не из контактов срезан


def test_ios_en_calls_media_and_system():
    chat = parse_chat(IOS_EN)
    df = chat.messages

    assert chat.platform == "ios"
    assert chat.date_order == "MDY"
    assert kinds(chat) == ["system", "text", "media", "call", "call", "call", "call", "system", "text"]
    assert df.loc[2, "timestamp"] == datetime(2021, 1, 1, 0, 0, 10)
    assert LRM not in "".join(df["text"])

    calls = df[df["kind"] == "call"]
    assert calls["call_type"].tolist() == ["voice", "voice", "video", "voice"]
    assert calls["call_missed"].tolist() == [True, False, False, True]
    assert calls["call_duration_s"].fillna(-1).tolist() == [-1, 720, 3900, -1]


def test_ios_ru():
    chat = parse_chat(IOS_RU)
    df = chat.messages

    assert chat.platform == "ios"
    assert chat.date_order == "DMY"
    assert kinds(chat) == ["text", "media", "call", "call", "media"]
    assert df.loc[3, "call_type"] == "video"
    assert df.loc[3, "call_duration_s"] == 3900
    assert bool(df.loc[2, "call_missed"]) is True


# --- порядок даты ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("dates", "ampm", "expected"),
    [
        (["13/01/21", "01/02/21"], False, "DMY"),
        (["01/13/21", "01/02/21"], False, "MDY"),
        (["01/02/21"], False, "DMY"),   # неоднозначно, 24 часа → Европа
        (["01/02/21"], True, "MDY"),    # неоднозначно, AM/PM → США
        (["2021-01-02"], False, "YMD"),
    ],
)
def test_detect_date_order(dates, ampm, expected):
    assert detect_date_order(dates, ampm) == expected


def test_messages_are_sorted_and_bad_dates_skipped():
    text = (
        "02.01.21, 10:00 - A: второе\n"
        "01.01.21, 10:00 - B: первое\n"
        "31.02.21, 10:00 - A: такой даты нет\n"
    )
    df = parse_chat(text).messages
    assert df["text"].tolist() == ["первое", "второе"]


# --- чтение файла ---------------------------------------------------------------

def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_zip_picks_chat_txt_and_ignores_media():
    data = make_zip({
        "IMG-20210101-WA0001.jpg": b"\xff\xd8 binary",
        "notes.txt": "просто документ, который переслали в чат".encode(),
        "__MACOSX/._WhatsApp Chat with John.txt": b"junk",
        "WhatsApp Chat with John.txt": ANDROID_EN.encode(),
    })
    chat = load_chat(data, "export.zip")
    assert chat.platform == "android"
    assert len(chat.messages) == 7


def test_zip_without_txt():
    with pytest.raises(ChatParseError, match="нет .txt"):
        load_chat(make_zip({"photo.jpg": b"123"}), "export.zip")


def test_fake_zip():
    with pytest.raises(ChatParseError, match="не zip"):
        read_export(b"hello", "chat.zip")


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_encodings(encoding):
    chat = load_chat(ANDROID_RU.encode(encoding), "chat.txt")
    assert chat.messages.loc[1, "text"] == "Привет!"


# --- «грязные» файлы ------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "\n\n  \n"])
def test_empty_file(text):
    with pytest.raises(ChatParseError, match="пустой"):
        parse_chat(text)


def test_not_a_whatsapp_export():
    with pytest.raises(ChatParseError, match="формат"):
        parse_chat("Список покупок:\nмолоко\nхлеб\n")


def test_only_system_messages():
    chat = parse_chat(ANDROID_EN.splitlines()[0])
    assert kinds(chat) == ["system"]
