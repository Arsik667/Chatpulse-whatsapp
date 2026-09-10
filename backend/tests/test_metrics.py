"""Тесты метрик на мини-чате, где все ответы посчитаны вручную.

01.03.21 — понедельник. Сообщения (звонки в них не входят):
  1  пн 10:00:00  Анна   текст   «Привет! Как дела? 😂😂»      — начало разговора
  2  пн 10:01:00  Борис  текст   ответ Анне через 60 с
  3  пн 10:01:30  Борис  ссылка
  4  пн 10:05:00  Анна   фото    ответ через 210 с
  5  пн 10:06:00  Борис  текст   ответ через 60 с
  6  пн 20:00:00  Борис  текст   пауза 9 ч 54 мин > 6 ч — начало разговора
     пн 20:30:00  Анна   звонок 10 мин
  8  вт 09:00:00  Анна   текст   пауза 13 ч — начало разговора
     чт 09:00:00  Борис  пропущенный видеозвонок
 10  чт 09:00:30  Борис  удалено пауза 2 дня — начало разговора
 11  чт 12:00:00  Анна   текст   ответ через 10770 с (< 6 ч)
"""

import json

import pytest

from analyzer_core import analyze, parse_chat
from analyzer_core.metrics import (
    activity_heatmap,
    call_stats,
    participant_stats,
    response_times,
    summary_stats,
    timeline,
    top_emoji,
    top_words,
)

LRM = "\u200e"

CHAT = f"""\
[01.03.21, 09:59:00] Анна: {LRM}Messages and calls are end-to-end encrypted.
[01.03.21, 10:00:00] Анна: Привет! Как дела? 😂😂
[01.03.21, 10:01:00] Борис: Привет, Анна! Отлично 👍🏽
[01.03.21, 10:01:30] Борис: https://example.com смотри
[01.03.21, 10:05:00] Анна: {LRM}image omitted
[01.03.21, 10:06:00] Борис: котик котик котик ❤️
[01.03.21, 20:00:00] Борис: Проснулась? ❤
[01.03.21, 20:30:00] Анна: {LRM}Voice call, {LRM}10 min
[02.03.21, 09:00:00] Анна: Доброе утро 👨‍👩‍👧
[04.03.21, 09:00:00] Борис: {LRM}Missed video call
[04.03.21, 09:00:30] Борис: Это сообщение удалено
[04.03.21, 12:00:00] Анна: котик 🇷🇺
"""


@pytest.fixture(scope="module")
def df():
    return parse_chat(CHAT).messages


def by_name(rows):
    return {r["name"]: r for r in rows}


def test_summary(df):
    assert summary_stats(df) == {
        "messages": 9,
        "text_messages": 7,
        "words": 14,  # ссылка и эмодзи словами не считаются
        "media": 1,
        "links": 1,
        "deleted": 1,
        "avg_words_per_message": 2.0,
    }


def test_participants_and_initiations(df):
    rows = participant_stats(df)
    assert [r["name"] for r in rows] == ["Борис", "Анна"]  # по убыванию сообщений

    boris, anna = by_name(rows)["Борис"], by_name(rows)["Анна"]
    assert (boris["messages"], boris["share"]) == (5, 55.6)
    assert (anna["messages"], anna["share"]) == (4, 44.4)
    assert (boris["words"], boris["avg_words"], boris["links"]) == (8, 2.0, 1)
    assert anna["media"] == 1
    # разговоры начинали: Анна (1, 8), Борис (6, 10)
    assert (anna["initiations"], boris["initiations"]) == (2, 2)
    assert anna["initiation_share"] == 50.0


def test_response_times(df):
    rows = by_name(response_times(df))
    assert rows["Борис"] == {"name": "Борис", "median_s": 60.0, "mean_s": 60.0, "responses": 2}
    # 210 с и 10770 с; ответы через паузу > 6 ч не засчитаны
    assert rows["Анна"] == {"name": "Анна", "median_s": 5490.0, "mean_s": 5490.0, "responses": 2}


def test_calls(df):
    calls = call_stats(df)
    assert {k: calls[k] for k in ("total", "completed", "missed", "voice", "video")} == {
        "total": 2, "completed": 1, "missed": 1, "voice": 1, "video": 1,
    }
    assert calls["total_duration_s"] == calls["avg_duration_s"] == calls["longest_s"] == 600
    people = by_name(calls["by_participant"])
    assert people["Анна"] == {"name": "Анна", "total": 1, "completed": 1, "missed": 0, "duration_s": 600.0}
    assert people["Борис"]["missed"] == 1


def test_activity_heatmap(df):
    heat = activity_heatmap(df)
    assert heat["matrix"][0][10] == 5  # пн 10:00–10:59
    assert heat["by_weekday"] == [6, 1, 0, 2, 0, 0, 0]
    assert sum(heat["by_hour"]) == 9
    assert heat["by_hour"][9] == 2


def test_timeline_and_silences(df):
    tl = timeline(df)
    assert tl["dates"] == ["2021-03-01", "2021-03-02", "2021-03-03", "2021-03-04"]
    assert tl["counts"] == [6, 1, 0, 2]  # среда без сообщений дозаполнена нулём
    assert tl["most_active_day"] == {"date": "2021-03-01", "count": 6}

    silences = tl["longest_silences"]
    assert [s["duration_s"] for s in silences] == [172830, 46800, 35640]
    assert silences[0] == {
        "start": "2021-03-02T09:00:00",
        "end": "2021-03-04T09:00:30",
        "duration_s": 172830.0,
        "broken_by": "Борис",
    }


def test_top_words_skip_stopwords_names_and_links(df):
    words = {w["word"]: w["count"] for w in top_words(df)}
    assert list(words)[:2] == ["котик", "привет"]
    assert words["котик"] == 4
    assert "как" not in words      # стоп-слово
    assert "анна" not in words     # имя участника
    assert "example" not in words  # из ссылки


def test_top_emoji(df):
    emoji = top_emoji(df)
    assert emoji[:2] == [{"emoji": "😂", "count": 2}, {"emoji": "❤️", "count": 2}]  # ❤️ + ❤
    found = {e["emoji"] for e in emoji}
    assert {"👍🏽", "👨‍👩‍👧", "🇷🇺"} <= found  # тон кожи, ZWJ-семья и флаг — целиком


def test_report_is_json_serializable():
    report = analyze(parse_chat(CHAT))
    json.dumps(report)  # не должно быть numpy-типов и Timestamp
    assert report["meta"]["participants"] == ["Борис", "Анна"]
    assert report["meta"]["days"] == 4
    assert report["meta"]["has_seconds"] is True
    assert report["meta"]["system_events"] == 1
    assert report["warnings"] == []


# --- пустые состояния -------------------------------------------------------------

def test_only_system_messages():
    report = analyze(parse_chat("01.01.21, 10:00 - Иван создал группу «Тест»\n"))
    json.dumps(report)
    assert report["summary"]["messages"] == 0
    assert report["participants"] == report["response_times"] == []
    assert report["timeline"]["most_active_day"] is None
    assert report["top_words"] == report["top_emoji"] == []
    assert report["calls"]["total"] == 0
    assert "нет сообщений" in report["warnings"][0]


def test_single_participant_android_without_calls():
    chat = "01.01.21, 10:00 - Иван: заметка себе\n01.01.21, 18:00 - Иван: ещё одна\n"
    report = analyze(parse_chat(chat))
    assert [p["name"] for p in report["participants"]] == ["Иван"]
    assert report["response_times"] == []
    assert report["calls"] == {
        "total": 0, "completed": 0, "missed": 0, "voice": 0, "video": 0,
        "total_duration_s": 0.0, "avg_duration_s": None, "longest_s": None, "by_participant": [],
    }
    assert report["meta"]["has_seconds"] is False
    assert any("один участник" in w for w in report["warnings"])
    assert any("без секунд" in w for w in report["warnings"])
