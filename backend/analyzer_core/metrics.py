"""Метрики чата — всё, что показывают дашборд и PDF-отчёт.

Каждая функция принимает DataFrame из parser.parse_chat() и возвращает обычные
dict/list из int, float и str, которые можно сразу отдать как JSON.
analyze() собирает их в один отчёт — это и есть JSON-контракт, общий для
API, фронтенда и CLI.

Термины:
- «сообщение» — строка с kind из MESSAGE_KINDS (текст, медиа, удалённое).
  Звонки и служебные события считаются отдельно и в сообщения не входят;
- «разговор» начинается с первого сообщения после паузы дольше gap_hours.
  Тот, кто его написал, — инициатор. Ответ через паузу дольше gap_hours —
  уже не «ответ», а начало нового разговора, в среднее время ответа он не входит;
- «слово» — последовательность букв (WORD_RE); ссылки, числа и эмодзи словами
  не считаются.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache
from importlib import resources

import numpy as np
import pandas as pd

from .parser import ParsedChat

MESSAGE_KINDS = ("text", "media", "deleted")
DEFAULT_GAP_HOURS = 6.0
MIN_WORD_LEN = 3

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\d+")  # @79991234567 — упоминания в группах
# Слово — буквы (любого алфавита), можно через дефис или апостроф: «что-то», «don't».
WORD_RE = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")

# Эмодзи ищем регуляркой по диапазонам Unicode — без внешних библиотек и быстро.
_EMOJI_CHAR = "\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A\u231B\u23E9-\u23FA"
_EMOJI_MOD = "\uFE0F\U0001F3FB-\U0001F3FF\U000E0020-\U000E007F"  # вариация, тон кожи, теги
EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF]{2}"                    # флаги — пара букв-индикаторов
    "|[0-9#*]\uFE0F?\u20E3"                           # 1️⃣ #️⃣
    f"|[{_EMOJI_CHAR}][{_EMOJI_MOD}]*"              # 👍 👍🏽 ❤️
    f"(?:\u200D[{_EMOJI_CHAR}][{_EMOJI_MOD}]*)*"   # ZWJ-последовательности 👨‍👩‍👧
)


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е").replace("’", "'")


def _pct(part: float, total: float) -> float:
    return round(100 * part / total, 1) if total else 0.0


def _messages(df: pd.DataFrame) -> pd.DataFrame:
    """Только сообщения участников — без звонков и служебных событий."""
    return df[df["kind"].isin(MESSAGE_KINDS)]


def _with_counts(m: pd.DataFrame) -> pd.DataFrame:
    """Добавляет число слов и ссылок. Считаем только в текстовых сообщениях."""
    is_text = m["kind"] == "text"
    text = m["text"].where(is_text, "")
    without_urls = text.str.replace(URL_RE.pattern, " ", regex=True, flags=re.IGNORECASE)
    return m.assign(
        is_text=is_text,
        is_media=m["kind"] == "media",
        words=without_urls.str.count(WORD_RE.pattern),
        links=text.str.count(URL_RE.pattern, flags=re.IGNORECASE),
    )


def _conversation_starts(m: pd.DataFrame, gap_hours: float) -> pd.Series:
    """True для сообщений, открывающих разговор (первое в чате или после паузы)."""
    gap = m["timestamp"].diff()
    return gap.isna() | (gap > pd.Timedelta(hours=gap_hours))


# --- 1. общая статистика ---------------------------------------------------------

def summary_stats(df: pd.DataFrame) -> dict:
    m = _with_counts(_messages(df))
    text_messages = int(m["is_text"].sum())
    words = int(m["words"].sum())
    return {
        "messages": len(m),
        "text_messages": text_messages,
        "words": words,
        "media": int(m["is_media"].sum()),
        "links": int(m["links"].sum()),
        "deleted": int((m["kind"] == "deleted").sum()),
        # среднее по текстовым сообщениям: у фото и стикеров слов нет
        "avg_words_per_message": round(words / text_messages, 2) if text_messages else 0.0,
    }


# --- 2. по участникам ------------------------------------------------------------

def participant_stats(df: pd.DataFrame, gap_hours: float = DEFAULT_GAP_HOURS) -> list[dict]:
    m = _with_counts(_messages(df))
    if m.empty:
        return []

    starts = _conversation_starts(m, gap_hours)
    agg = m.groupby("author").agg(
        messages=("kind", "size"),
        text_messages=("is_text", "sum"),
        words=("words", "sum"),
        media=("is_media", "sum"),
        links=("links", "sum"),
    )
    agg["initiations"] = m[starts].groupby("author").size().reindex(agg.index, fill_value=0)
    # groupby уже отсортировал по имени, стабильная сортировка сохранит его при равенстве
    agg = agg.sort_values("messages", ascending=False, kind="stable")

    total, total_starts = len(m), int(starts.sum())
    return [
        {
            "name": name,
            "messages": int(row.messages),
            "share": _pct(row.messages, total),
            "words": int(row.words),
            "avg_words": round(row.words / row.text_messages, 2) if row.text_messages else 0.0,
            "media": int(row.media),
            "links": int(row.links),
            "initiations": int(row.initiations),
            "initiation_share": _pct(row.initiations, total_starts),
        }
        for name, row in agg.iterrows()
    ]


# --- 3. время ответа ---------------------------------------------------------------

def response_times(df: pd.DataFrame, gap_hours: float = DEFAULT_GAP_HOURS) -> list[dict]:
    """Сколько участник отвечает на сообщение собеседника.

    Ответ — сообщение, перед которым стоит сообщение другого человека.
    Время считаем от последнего сообщения собеседника: если A прислал три
    сообщения подряд, а B ответил, засчитывается пауза после третьего.
    """
    m = _messages(df)
    if m["author"].nunique() < 2:
        return []

    prev_author = m["author"].shift()
    delay = m["timestamp"].diff().dt.total_seconds()
    is_reply = prev_author.notna() & (m["author"] != prev_author) & (delay <= gap_hours * 3600)

    replies = pd.DataFrame({"author": m.loc[is_reply, "author"], "delay": delay[is_reply]})
    agg = replies.groupby("author")["delay"].agg(["median", "mean", "count"])
    agg = agg.sort_values("count", ascending=False, kind="stable")
    return [
        {
            "name": name,
            "median_s": round(float(row["median"]), 1),
            "mean_s": round(float(row["mean"]), 1),
            "responses": int(row["count"]),
        }
        for name, row in agg.iterrows()
    ]


# --- 4. звонки ---------------------------------------------------------------------

def call_stats(df: pd.DataFrame) -> dict:
    calls = df[df["kind"] == "call"]
    missed = calls["call_missed"].fillna(False).astype(bool)
    durations = calls.loc[~missed, "call_duration_s"].dropna()

    by_author = (
        calls.assign(missed=missed, completed=~missed)
        .groupby("author")
        .agg(
            total=("kind", "size"),
            completed=("completed", "sum"),
            missed=("missed", "sum"),
            duration_s=("call_duration_s", "sum"),
        )
        .sort_values("total", ascending=False, kind="stable")
    )
    return {
        "total": len(calls),
        "completed": int((~missed).sum()),
        "missed": int(missed.sum()),
        "voice": int((calls["call_type"] == "voice").sum()),
        "video": int((calls["call_type"] == "video").sum()),
        "total_duration_s": float(durations.sum()),
        "avg_duration_s": round(float(durations.mean()), 1) if len(durations) else None,
        "longest_s": float(durations.max()) if len(durations) else None,
        # author звонка — тот, кто звонил (для пропущенного — чей звонок пропустили)
        "by_participant": [
            {
                "name": name,
                "total": int(row.total),
                "completed": int(row.completed),
                "missed": int(row.missed),
                "duration_s": float(row.duration_s),
            }
            for name, row in by_author.iterrows()
        ],
    }


# --- 5. активность по часам и дням недели ----------------------------------------

def activity_heatmap(df: pd.DataFrame) -> dict:
    """Матрица 7×24: строка — день недели (0 = понедельник), столбец — час."""
    ts = _messages(df)["timestamp"]
    matrix = np.zeros((7, 24), dtype=int)
    np.add.at(matrix, (ts.dt.dayofweek.to_numpy(), ts.dt.hour.to_numpy()), 1)
    return {
        "matrix": matrix.tolist(),
        "by_hour": matrix.sum(axis=0).tolist(),
        "by_weekday": matrix.sum(axis=1).tolist(),
    }


# --- 6. таймлайн и «тишины» -------------------------------------------------------

def timeline(df: pd.DataFrame, top_silences: int = 3) -> dict:
    m = _messages(df)
    if m.empty:
        return {"dates": [], "counts": [], "most_active_day": None, "longest_silences": []}

    daily = m["timestamp"].dt.normalize().value_counts().sort_index()
    # дни без сообщений тоже нужны на графике — дозаполняем нулями
    all_days = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(all_days, fill_value=0)
    peak = daily.idxmax()

    ts = m["timestamp"].reset_index(drop=True)
    authors = m["author"].reset_index(drop=True)
    gaps = ts.diff().dt.total_seconds().dropna()
    silences = [
        {
            "start": ts[i - 1].isoformat(),
            "end": ts[i].isoformat(),
            "duration_s": float(gaps[i]),
            "broken_by": authors[i],  # кто первым написал после паузы
        }
        for i in gaps.nlargest(top_silences).index
        if gaps[i] > 0
    ]
    return {
        "dates": daily.index.strftime("%Y-%m-%d").tolist(),
        "counts": [int(c) for c in daily],
        "most_active_day": {"date": peak.strftime("%Y-%m-%d"), "count": int(daily[peak])},
        "longest_silences": silences,
    }


# --- 7. топ-слова -------------------------------------------------------------------

@cache
def load_stopwords() -> frozenset[str]:
    """Стоп-слова из stopwords/*.txt. Кешируем: это не данные пользователя."""
    words: set[str] = set()
    folder = resources.files(__package__) / "stopwords"
    for lang in ("ru", "en"):
        for line in (folder / f"{lang}.txt").read_text("utf-8").splitlines():
            line = line.split("#", 1)[0]
            words.update(_normalize(w) for w in line.split())
    return frozenset(words)


def _name_tokens(df: pd.DataFrame) -> set[str]:
    """Имена участников по словам: «Иван Петров» → {«иван», «петров»}."""
    names = " ".join(df["author"].dropna().unique())
    return set(WORD_RE.findall(_normalize(names)))


def top_words(df: pd.DataFrame, n: int = 50) -> list[dict]:
    texts = df.loc[df["kind"] == "text", "text"]
    blob = MENTION_RE.sub(" ", URL_RE.sub(" ", _normalize("\n".join(texts))))
    stop = load_stopwords() | _name_tokens(df)
    counts = Counter(w for w in WORD_RE.findall(blob) if len(w) >= MIN_WORD_LEN and w not in stop)
    return [{"word": w, "count": c} for w, c in counts.most_common(n)]


# --- 8. топ-эмодзи ------------------------------------------------------------------

def top_emoji(df: pd.DataFrame, n: int = 20) -> list[dict]:
    texts = df.loc[df["kind"] == "text", "text"]
    found = Counter(EMOJI_RE.findall("\n".join(texts)))

    # «❤️» и «❤» — одно и то же сердце, отличаются только селектором U+FE0F.
    # Считаем их вместе, а показываем тот вариант, что встречался чаще.
    totals: Counter = Counter()
    shown: dict[str, tuple[str, int]] = {}
    for emoji, count in found.items():
        key = emoji.replace("\uFE0F", "")
        totals[key] += count
        if count > shown.get(key, ("", 0))[1]:
            shown[key] = (emoji, count)
    return [{"emoji": shown[key][0], "count": c} for key, c in totals.most_common(n)]


# --- отчёт целиком ------------------------------------------------------------------

def analyze(
    chat: ParsedChat,
    *,
    gap_hours: float = DEFAULT_GAP_HOURS,
    top_words_n: int = 50,
    top_emoji_n: int = 20,
) -> dict:
    """Все метрики одним словарём — общий JSON-контракт для API, фронтенда и CLI."""
    df = chat.messages
    ts = _messages(df)["timestamp"]
    participants = participant_stats(df, gap_hours)

    report = {
        "meta": {
            "platform": chat.platform,
            "date_order": chat.date_order,
            "participants": [p["name"] for p in participants],
            "first_message": ts.min().isoformat() if len(ts) else None,
            "last_message": ts.max().isoformat() if len(ts) else None,
            "days": (ts.max().normalize() - ts.min().normalize()).days + 1 if len(ts) else 0,
            # Android пишет время без секунд — тогда время ответа точно до минуты
            "has_seconds": bool((ts.dt.second != 0).any()),
            "system_events": int((df["kind"] == "system").sum()),
            "gap_hours": gap_hours,
        },
        "summary": summary_stats(df),
        "participants": participants,
        "response_times": response_times(df, gap_hours),
        "calls": call_stats(df),
        "activity": activity_heatmap(df),
        "timeline": timeline(df),
        "top_words": top_words(df, top_words_n),
        "top_emoji": top_emoji(df, top_emoji_n),
    }
    report["warnings"] = _warnings(report)
    return report


def _warnings(report: dict) -> list[str]:
    """Пояснения к «грязным» экспортам — кодами. Тексты на двух языках лежат
    в messages.py (для API и CLI) и в словаре фронтенда."""
    warnings = []
    if report["summary"]["messages"] == 0:
        warnings.append("no_messages")
    elif len(report["participants"]) == 1:
        warnings.append("single_participant")
    if report["summary"]["messages"] and not report["meta"]["has_seconds"]:
        warnings.append("no_seconds")
    return warnings
