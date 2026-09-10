"""ChatPulse из терминала: анализ экспорта WhatsApp без фронтенда и Docker.

    python report_cli.py chat.txt --out report.pdf
    python report_cli.py "WhatsApp Chat.zip" --json report.json --no-pdf
    python report_cli.py chat.txt --lang en          # сводка и PDF на английском

Считает всё тот же analyzer_core.analyze_file(), что и API, а графики в PDF
строятся из того же JSON-отчёта, который получает фронтенд.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # без GUI: работает и в голом терминале, и в Docker

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.dates import AutoDateLocator, num2date  # noqa: E402
from matplotlib.table import Table  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from analyzer_core import DEFAULT_GAP_HOURS, LANGS, ChatParseError, analyze_file, message  # noqa: E402

ACCENT = "#4F46E5"
ACCENT_2 = "#10B981"
MISSED = "#F59E0B"
MUTED = "#6B7280"
GRID = "#E5E7EB"
A4 = (8.27, 11.69)
PLATFORMS = {"android": "Android", "ios": "iOS"}
# Названия месяцев пишем сами: strftime("%b") зависит от локали системы.
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",  # идёт с matplotlib и умеет кириллицу
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": GRID,
    "axes.titleweight": "bold",
    "axes.titlesize": 11,
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})

# Подписи сводки и PDF на двух языках. Тексты ошибок и предупреждений лежат
# в analyzer_core/messages.py — их делят CLI и API.
TEXTS = {
    "ru": {
        "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "units": ("с", "мин", "ч", "дн"),
        "no_messages": "нет сообщений",
        "period": "{first} – {last} ({days} дн.)",
        # терминал
        "summary": "Сообщений {messages} · слов {words} · медиа {media} · ссылок {links} · "
                   "в среднем {avg} слова на сообщение",
        "term_head": ("Участник", "Сообщ.", "Доля", "Начинал", "Ответ, медиана"),
        "term_calls": "Звонки: {total} (пропущено {missed}), общая длительность {duration}, в среднем {avg}",
        "no_calls": "Звонков в экспорте нет.",
        "term_peak": "Самый активный день: {date} — {count} сообщ.",
        "term_silence": "  тишина #{i}: {duration} ({start} → {end}, первым написал(а) {who})",
        "top_words": "Топ-слова:",
        "top_emoji": "Топ-эмодзи:",
        "read_error": "Не удалось прочитать {path}: {reason}",
        "error": "Ошибка: {message}",
        # PDF: первая страница
        "pdf_title": "ChatPulse — отчёт по чату WhatsApp",
        "subtitle": "Отчёт по чату WhatsApp · {platform} · {period}",
        "kpis": ("сообщений", "слов", "медиа", "ссылок", "слов в сообщении"),
        "participants": "Участники",
        "table_head": ("Участник", "Сообщ.", "Доля", "Слов", "Слов/сообщ.", "Медиа", "Начинал", "Ответ*"),
        "reply_note": "* медиана времени ответа на сообщение собеседника",
        "more_people": " · ещё участников: {n}",
        "no_people": "Нет сообщений от участников.",
        "by_day": "Сообщения по дням",
        "per_day": "за день",
        "rolling": "среднее за {n} дней",
        "peak": "пик: {count} · {date}",
        "in_short": "Коротко",
        "hl_calls": "Звонки: {total} (голосовых {voice}, видео {video}), пропущено {missed}",
        "hl_durations": "Длительность звонков: всего {total}, в среднем {avg}, самый долгий {longest}",
        "hl_peak": "Самый активный день: {date} — {count} сообщений",
        "hl_silence": "Тишина {i}: {duration} — {start} → {end}, первым написал(а) {who}",
        "footer": "Отчёт собран локально: файл чата не сохранялся и никуда не отправлялся.",
        # PDF: участники
        "by_person": "Сообщения по участникам",
        "starts": "Кто начинает разговор (первое сообщение после паузы > {gap} ч)",
        "starts_value": "{n} раз · {pct}",
        "starts_axis": "% разговоров",
        "replies": "Время ответа на сообщение собеседника, медиана",
        "replies_value": "{median} · среднее {mean}",
        "minutes": "минуты",
        "need_two": "Нужно хотя бы два участника",
        "calls_by_person": "Звонки по участникам (кто звонил)",
        "completed": "состоялись",
        "missed": "пропущены",
        "no_calls_short": "Звонков в экспорте нет",
        # PDF: активность, слова, эмодзи
        "heatmap": "Активность: день недели × час",
        "by_hour": "По часам суток",
        "by_weekday": "По дням недели",
        "words": "Топ-слова (без стоп-слов и имён участников)",
        "no_words": "Текстовых сообщений нет",
        "emoji": "Топ-эмодзи",
        "no_emoji": "Эмодзи не найдены",
    },
    "en": {
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "units": ("s", "min", "h", "d"),
        "no_messages": "no messages",
        "period": "{first} – {last} ({days} days)",
        "summary": "Messages {messages} · words {words} · media {media} · links {links} · "
                   "{avg} words per message on average",
        "term_head": ("Participant", "Msgs", "Share", "Started", "Reply, median"),
        "term_calls": "Calls: {total} ({missed} missed), total duration {duration}, average {avg}",
        "no_calls": "No calls in the export.",
        "term_peak": "Most active day: {date} — {count} messages",
        "term_silence": "  silence #{i}: {duration} ({start} → {end}, broken by {who})",
        "top_words": "Top words:",
        "top_emoji": "Top emoji:",
        "read_error": "Could not read {path}: {reason}",
        "error": "Error: {message}",
        "pdf_title": "ChatPulse — WhatsApp chat report",
        "subtitle": "WhatsApp chat report · {platform} · {period}",
        "kpis": ("messages", "words", "media", "links", "words per message"),
        "participants": "Participants",
        "table_head": ("Participant", "Msgs", "Share", "Words", "Words/msg", "Media", "Started", "Reply*"),
        "reply_note": "* median time to reply to someone else's message",
        "more_people": " · {n} more participants",
        "no_people": "No messages from participants.",
        "by_day": "Messages per day",
        "per_day": "per day",
        "rolling": "{n}-day average",
        "peak": "peak: {count} · {date}",
        "in_short": "Highlights",
        "hl_calls": "Calls: {total} ({voice} voice, {video} video), {missed} missed",
        "hl_durations": "Call time: {total} in total, {avg} on average, longest {longest}",
        "hl_peak": "Most active day: {date} — {count} messages",
        "hl_silence": "Silence {i}: {duration} — {start} → {end}, broken by {who}",
        "footer": "Generated locally: the chat file was not stored or sent anywhere.",
        "by_person": "Messages per participant",
        "starts": "Who starts conversations (first message after a pause > {gap} h)",
        "starts_value": "{n} times · {pct}",
        "starts_axis": "% of conversations",
        "replies": "Time to reply to someone else's message, median",
        "replies_value": "{median} · mean {mean}",
        "minutes": "minutes",
        "need_two": "At least two participants are needed",
        "calls_by_person": "Calls per participant (who called)",
        "completed": "answered",
        "missed": "missed",
        "no_calls_short": "No calls in the export",
        "heatmap": "Activity: weekday × hour",
        "by_hour": "By hour of day",
        "by_weekday": "By weekday",
        "words": "Top words (without stop words and participants' names)",
        "no_words": "No text messages",
        "emoji": "Top emoji",
        "no_emoji": "No emoji found",
    },
}


# --- форматирование ---------------------------------------------------------------

def fmt_int(n: float, lang: str = "ru") -> str:
    """12 345 по-русски, 12,345 по-английски."""
    text = f"{int(n):,}"
    return text.replace(",", " ") if lang == "ru" else text


def fmt_num(x: float, lang: str = "ru") -> str:
    """Дробь: 2,53 по-русски, 2.53 по-английски."""
    text = f"{x:g}"
    return text.replace(".", ",") if lang == "ru" else text


def fmt_pct(x: float, lang: str = "ru") -> str:
    return f"{fmt_num(x, lang)}%"


def fmt_duration(seconds: float | None, lang: str = "ru") -> str:
    """45 с · 3 мин · 1 ч 5 мин · 2 дн 3 ч (или 45 s · 3 min · 1 h 5 min · 2 d 3 h)"""
    if seconds is None:
        return "—"
    sec, mins, hrs, days = TEXTS[lang]["units"]
    s = int(round(seconds))
    if s < 60:
        return f"{s} {sec}"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} {mins}" + (f" {s} {sec}" if s and m < 10 else "")
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} {hrs}" + (f" {m} {mins}" if m else "")
    d, h = divmod(h, 24)
    return f"{d} {days}" + (f" {h} {hrs}" if h else "")


def fmt_date(iso: str, with_time: bool = False, lang: str = "ru") -> str:
    """31.12.2025 по-русски, 31 Dec 2025 по-английски."""
    dt = datetime.fromisoformat(iso)
    text = f"{dt.day} {MONTHS_EN[dt.month - 1]} {dt.year}" if lang == "en" else f"{dt:%d.%m.%Y}"
    return f"{text} {dt:%H:%M}" if with_time else text


def _axis_date(value: float, lang: str) -> str:
    dt = num2date(value)
    return f"{dt.day} {MONTHS_EN[dt.month - 1]} {dt:%y}" if lang == "en" else f"{dt:%d.%m.%y}"


def emoji_name(emoji: str) -> str:
    """Шрифты matplotlib не рисуют цветные эмодзи, поэтому в PDF подписываем их именами."""
    if len(emoji) == 2 and all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in emoji):
        return "flag " + "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in emoji)
    skip = {0x200D, 0xFE0F, *range(0x1F3FB, 0x1F400)}  # ZWJ, вариация, тон кожи
    names = [unicodedata.name(c, "").lower() for c in emoji if ord(c) not in skip]
    return " + ".join(n for n in names if n) or "emoji"


def period(meta: dict, lang: str = "ru") -> str:
    tx = TEXTS[lang]
    if not meta["first_message"]:
        return tx["no_messages"]
    return tx["period"].format(
        first=fmt_date(meta["first_message"], lang=lang),
        last=fmt_date(meta["last_message"], lang=lang),
        days=meta["days"],
    )


# --- сводка в терминал --------------------------------------------------------------

def print_summary(report: dict, lang: str = "ru") -> None:
    tx = TEXTS[lang]
    meta, summary = report["meta"], report["summary"]
    responses = {r["name"]: r for r in report["response_times"]}

    print(f"\nChatPulse · WhatsApp ({PLATFORMS[meta['platform']]}) · {period(meta, lang)}\n")
    print(tx["summary"].format(
        messages=fmt_int(summary["messages"], lang), words=fmt_int(summary["words"], lang),
        media=fmt_int(summary["media"], lang), links=fmt_int(summary["links"], lang),
        avg=fmt_num(summary["avg_words_per_message"], lang),
    ))

    if report["participants"]:
        name, msgs, share, started, reply = tx["term_head"]
        print(f"\n{name:<22}{msgs:>9}{share:>8}{started:>9}{reply:>16}")
        for p in report["participants"]:
            median = responses[p["name"]]["median_s"] if p["name"] in responses else None
            print(
                f"{p['name'][:21]:<22}{fmt_int(p['messages'], lang):>9}{fmt_pct(p['share'], lang):>8}"
                f"{fmt_pct(p['initiation_share'], lang):>9}{fmt_duration(median, lang):>16}"
            )

    calls = report["calls"]
    if calls["total"]:
        print("\n" + tx["term_calls"].format(
            total=calls["total"], missed=calls["missed"],
            duration=fmt_duration(calls["total_duration_s"], lang), avg=fmt_duration(calls["avg_duration_s"], lang),
        ))
    else:
        print("\n" + tx["no_calls"])

    timeline = report["timeline"]
    if timeline["most_active_day"]:
        peak = timeline["most_active_day"]
        print(tx["term_peak"].format(date=fmt_date(peak["date"], lang=lang), count=fmt_int(peak["count"], lang)))
    for i, s in enumerate(timeline["longest_silences"], 1):
        print(tx["term_silence"].format(
            i=i, duration=fmt_duration(s["duration_s"], lang), who=s["broken_by"],
            start=fmt_date(s["start"], True, lang), end=fmt_date(s["end"], True, lang),
        ))

    if report["top_words"]:
        print(tx["top_words"], ", ".join(f"{w['word']} ({w['count']})" for w in report["top_words"][:10]))
    if report["top_emoji"]:
        print(tx["top_emoji"], "  ".join(f"{e['emoji']} {e['count']}" for e in report["top_emoji"][:10]))
    for code in report["warnings"]:
        print(f"⚠ {message(code, lang)}")


# --- страницы PDF -------------------------------------------------------------------

def _empty(ax, text: str) -> None:
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", color=MUTED, fontsize=10, transform=ax.transAxes)


def _style_bars(ax, y, labels, min_slots: int) -> None:
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0, labelcolor="#111827")
    # при 2–3 участниках не раздуваем столбцы на всю высоту — оставляем пустые «слоты» снизу
    n = len(labels)
    ax.set_ylim(n - 0.5 - max(n, min_slots), n - 0.5)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _hbars(ax, labels, values, *, lang="ru", color=ACCENT, texts=None, pad=1.2, min_slots=3) -> None:
    """Горизонтальные столбцы сверху вниз, подписи значений справа."""
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.6)
    _style_bars(ax, y, labels, min_slots)
    peak = max(values)
    for yi, v, t in zip(y, values, texts or [fmt_int(v, lang) for v in values]):
        ax.text(v + peak * 0.015, yi, t, va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, peak * pad or 1)


def _timeline_chart(ax, tl: dict, lang: str) -> None:
    tx = TEXTS[lang]
    days = np.array(tl["dates"], dtype="datetime64[D]")
    counts = np.array(tl["counts"], dtype=float)
    top = counts.max()

    ax.plot(days, counts, color=ACCENT, alpha=0.35, linewidth=0.8, label=tx["per_day"])
    if len(counts) >= 14:
        # Скользящее среднее: неделя, а для многолетних чатов — месяц. Делим на
        # реальное число дней в окне, чтобы у краёв линия не проваливалась к нулю.
        size = 7 if len(counts) <= 365 else 30
        window = np.ones(size)
        smooth = np.convolve(counts, window, "same") / np.convolve(np.ones_like(counts), window, "same")
        ax.plot(days, smooth, color=ACCENT, linewidth=1.8, label=tx["rolling"].format(n=size))

    for i, s in enumerate(tl["longest_silences"], 1):
        start, end = np.datetime64(s["start"]), np.datetime64(s["end"])
        ax.axvspan(start, end, color=MISSED, alpha=0.22, linewidth=0)
        ax.text(start + (end - start) / 2, top * 1.1, str(i), ha="center", color="#B45309", fontsize=8)

    peak = tl["most_active_day"]
    px = np.datetime64(peak["date"])
    on_right = (px - days[0]) > (days[-1] - days[0]) * 0.7
    ax.scatter([px], [peak["count"]], color=ACCENT, s=14, zorder=3)
    ax.annotate(tx["peak"].format(count=fmt_int(peak["count"], lang), date=fmt_date(peak["date"], lang=lang)),
                xy=(px, peak["count"]), xytext=(-8 if on_right else 8, 0), textcoords="offset points",
                ha="right" if on_right else "left", va="center", fontsize=8, color=MUTED)

    ax.xaxis.set_major_locator(AutoDateLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _axis_date(value, lang)))
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylim(0, top * 1.22 or 1)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncols=2)


def _highlights(report: dict, lang: str) -> list[str]:
    tx = TEXTS[lang]
    calls, tl = report["calls"], report["timeline"]
    lines = []
    if calls["total"]:
        lines.append(tx["hl_calls"].format(
            total=calls["total"], voice=calls["voice"], video=calls["video"], missed=calls["missed"]))
        lines.append(tx["hl_durations"].format(
            total=fmt_duration(calls["total_duration_s"], lang), avg=fmt_duration(calls["avg_duration_s"], lang),
            longest=fmt_duration(calls["longest_s"], lang)))
    else:
        lines.append(tx["no_calls"])
    if tl["most_active_day"]:
        peak = tl["most_active_day"]
        lines.append(tx["hl_peak"].format(date=fmt_date(peak["date"], lang=lang), count=fmt_int(peak["count"], lang)))
    for i, s in enumerate(tl["longest_silences"], 1):
        lines.append(tx["hl_silence"].format(
            i=i, duration=fmt_duration(s["duration_s"], lang), who=s["broken_by"],
            start=fmt_date(s["start"], True, lang), end=fmt_date(s["end"], True, lang)))
    return lines


def page_overview(pdf: PdfPages, report: dict, lang: str = "ru") -> None:
    """Первая страница — одностраничная выжимка: цифры, участники, таймлайн, рекорды."""
    tx = TEXTS[lang]
    meta, summary, tl = report["meta"], report["summary"], report["timeline"]
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.94, "ChatPulse", fontsize=26, weight="bold", color=ACCENT)
    fig.text(0.07, 0.915, tx["subtitle"].format(platform=PLATFORMS[meta["platform"]], period=period(meta, lang)),
             fontsize=10, color=MUTED)

    values = [
        fmt_int(summary["messages"], lang), fmt_int(summary["words"], lang), fmt_int(summary["media"], lang),
        fmt_int(summary["links"], lang), fmt_num(summary["avg_words_per_message"], lang),
    ]
    for i, (label, value) in enumerate(zip(tx["kpis"], values)):
        fig.text(0.07 + i * 0.18, 0.855, value, fontsize=18, weight="bold")
        fig.text(0.07 + i * 0.18, 0.838, label, fontsize=8.5, color=MUTED)

    y = 0.79  # «курсор» сверху вниз: высота блоков зависит от числа участников
    fig.text(0.07, y, tx["participants"], fontsize=11, weight="bold")
    y -= 0.012
    people = report["participants"][:10]
    if people:
        responses = {r["name"]: r for r in report["response_times"]}
        widths = [0.21, 0.1, 0.08, 0.1, 0.15, 0.08, 0.11, 0.13]
        rows = [
            [
                p["name"][:24], fmt_int(p["messages"], lang), fmt_pct(p["share"], lang), fmt_int(p["words"], lang),
                fmt_num(p["avg_words"], lang), fmt_int(p["media"], lang), fmt_pct(p["initiation_share"], lang),
                fmt_duration(responses[p["name"]]["median_s"], lang) if p["name"] in responses else "—",
            ]
            for p in people
        ]
        table_h = 0.021 * (len(rows) + 1)
        ax = fig.add_axes((0.07, y - table_h, 0.86, table_h))
        ax.axis("off")
        table = Table(ax, bbox=(0, 0, 1, 1))
        for r, values in enumerate([tx["table_head"], *rows]):
            for c, value in enumerate(values):
                cell = table.add_cell(r, c, width=widths[c], height=1, text=value,
                                      loc="left" if c == 0 else "right", edgecolor=GRID)
                cell.set_linewidth(0.5)
                if r == 0:
                    cell.set_text_props(weight="bold", color=MUTED)
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        ax.add_table(table)
        y -= table_h + 0.008

        note = tx["reply_note"]
        if (extra := len(report["participants"]) - len(rows)) > 0:
            note += tx["more_people"].format(n=extra)
        fig.text(0.07, y, note, fontsize=7.5, color=MUTED, va="top")
        y -= 0.05
    else:
        fig.text(0.07, y - 0.02, tx["no_people"], fontsize=9.5, color=MUTED)
        y -= 0.06

    if len(tl["dates"]) >= 2:
        fig.text(0.07, y, tx["by_day"], fontsize=11, weight="bold")
        _timeline_chart(fig.add_axes((0.1, y - 0.235, 0.83, 0.215)), tl, lang)
        y -= 0.285

    fig.text(0.07, y, tx["in_short"], fontsize=11, weight="bold")
    y -= 0.026
    for line in _highlights(report, lang):
        fig.text(0.07, y, line, fontsize=9)
        y -= 0.02
    y -= 0.01
    for code in report["warnings"]:
        fig.text(0.07, y, f"⚠ {message(code, lang)}", fontsize=9, color="#B45309")
        y -= 0.02

    fig.text(0.07, 0.03, tx["footer"], fontsize=7.5, color=MUTED)
    pdf.savefig(fig)
    plt.close(fig)


def page_participants(pdf: PdfPages, report: dict, lang: str = "ru") -> None:
    tx = TEXTS[lang]
    fig, axes = plt.subplots(4, 1, figsize=A4, gridspec_kw={"hspace": 0.5})
    fig.subplots_adjust(left=0.2, right=0.95, top=0.95, bottom=0.05)
    people = report["participants"][:12]
    names = [p["name"][:22] for p in people]

    axes[0].set_title(tx["by_person"])
    _hbars(axes[0], names, [p["messages"] for p in people], lang=lang, pad=1.3,
           texts=[f"{fmt_int(p['messages'], lang)} · {fmt_pct(p['share'], lang)}" for p in people])

    axes[1].set_title(tx["starts"].format(gap=f"{report['meta']['gap_hours']:g}"))
    _hbars(axes[1], names, [p["initiation_share"] for p in people], lang=lang, color=ACCENT_2, pad=1.35,
           texts=[tx["starts_value"].format(n=p["initiations"], pct=fmt_pct(p["initiation_share"], lang))
                  for p in people])
    axes[1].set_xlabel(tx["starts_axis"], color=MUTED)

    axes[2].set_title(tx["replies"])
    replies = report["response_times"][:12]
    if replies:
        _hbars(axes[2], [r["name"][:22] for r in replies], [r["median_s"] / 60 for r in replies], lang=lang,
               pad=1.8, texts=[tx["replies_value"].format(median=fmt_duration(r["median_s"], lang),
                                                          mean=fmt_duration(r["mean_s"], lang)) for r in replies])
        axes[2].set_xlabel(tx["minutes"], color=MUTED)
    else:
        _empty(axes[2], tx["need_two"])

    ax = axes[3]
    ax.set_title(tx["calls_by_person"])
    callers = report["calls"]["by_participant"][:12]
    if callers:
        y = np.arange(len(callers))[::-1]
        done = np.array([c["completed"] for c in callers])
        ax.barh(y, done, color=ACCENT, height=0.6, label=tx["completed"])
        ax.barh(y, [c["missed"] for c in callers], left=done, color=MISSED, height=0.6, label=tx["missed"])
        _style_bars(ax, y, [c["name"][:22] for c in callers], min_slots=3)
        peak = max(c["total"] for c in callers)
        for yi, c in zip(y, callers):
            ax.text(c["total"] + peak * 0.015, yi, f"{c['total']} · {fmt_duration(c['duration_s'], lang)}",
                    va="center", fontsize=8, color=MUTED)
        ax.set_xlim(0, peak * 1.35)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(frameon=False, loc="lower right", fontsize=8)
    else:
        _empty(ax, tx["no_calls_short"])

    pdf.savefig(fig)
    plt.close(fig)


def page_activity(pdf: PdfPages, report: dict, lang: str = "ru") -> None:
    tx = TEXTS[lang]
    activity = report["activity"]
    fig = plt.figure(figsize=A4)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.1, 1, 1], hspace=0.45,
                            left=0.1, right=0.93, top=0.95, bottom=0.06)

    ax = fig.add_subplot(grid[0])
    ax.set_title(tx["heatmap"])
    cmap = LinearSegmentedColormap.from_list("chatpulse", ["#F3F4F6", ACCENT])
    image = ax.imshow(np.array(activity["matrix"]), aspect="auto", cmap=cmap)
    ax.set_yticks(range(7), tx["weekdays"])
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02).outline.set_visible(False)

    ax = fig.add_subplot(grid[1])
    ax.set_title(tx["by_hour"])
    ax.bar(range(24), activity["by_hour"], color=ACCENT, width=0.75)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}:00" for h in range(0, 24, 2)], fontsize=7.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    ax = fig.add_subplot(grid[2])
    ax.set_title(tx["by_weekday"])
    ax.bar(tx["weekdays"], activity["by_weekday"], color=ACCENT_2, width=0.6)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    pdf.savefig(fig)
    plt.close(fig)


def page_words(pdf: PdfPages, report: dict, lang: str = "ru") -> None:
    tx = TEXTS[lang]
    fig, (ax_words, ax_emoji) = plt.subplots(
        2, 1, figsize=A4, gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.2})
    fig.subplots_adjust(left=0.36, right=0.93, top=0.95, bottom=0.05)

    words = report["top_words"][:25]
    ax_words.set_title(tx["words"])
    if words:
        _hbars(ax_words, [w["word"] for w in words], [w["count"] for w in words], lang=lang, min_slots=10)
    else:
        _empty(ax_words, tx["no_words"])

    emoji = report["top_emoji"][:12]
    ax_emoji.set_title(tx["emoji"])
    if emoji:
        _hbars(ax_emoji, [emoji_name(e["emoji"])[:40] for e in emoji], [e["count"] for e in emoji],
               lang=lang, color=ACCENT_2, min_slots=6)
    else:
        _empty(ax_emoji, tx["no_emoji"])

    pdf.savefig(fig)
    plt.close(fig)


PAGES = [page_overview, page_participants, page_activity, page_words]


def render_pdf(report: dict, path: Path, lang: str = "ru") -> None:
    with PdfPages(path, metadata={"Title": TEXTS[lang]["pdf_title"]}) as pdf:
        # без сообщений остальные страницы были бы пустыми — оставляем только обзор
        for page in PAGES if report["summary"]["messages"] else PAGES[:1]:
            page(pdf, report, lang)


# --- точка входа --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="report_cli.py",
        description="Анализ экспорта чата WhatsApp (.txt или .zip) с PDF-отчётом.",
    )
    parser.add_argument("chat", type=Path, help="путь к экспорту: .txt или .zip")
    parser.add_argument("--out", type=Path, help="куда сохранить PDF (по умолчанию <имя чата>_report.pdf)")
    parser.add_argument("--json", type=Path, help="сохранить отчёт ещё и в JSON — тот же формат, что отдаёт API")
    parser.add_argument("--no-pdf", action="store_true", help="только сводка в терминале (и JSON, если указан)")
    parser.add_argument("--gap-hours", type=float, default=DEFAULT_GAP_HOURS,
                        help=f"пауза, после которой начинается новый разговор (по умолчанию {DEFAULT_GAP_HOURS:g})")
    parser.add_argument("--top-words", type=int, default=50, help="сколько слов в топе (по умолчанию 50)")
    parser.add_argument("--lang", choices=LANGS, default="ru", help="язык сводки и PDF (по умолчанию ru)")
    args = parser.parse_args(argv)
    tx = TEXTS[args.lang]

    try:
        data = args.chat.read_bytes()
    except OSError as exc:
        print(tx["read_error"].format(path=args.chat, reason=exc.strerror), file=sys.stderr)
        return 1
    try:
        report = analyze_file(data, args.chat.name, gap_hours=args.gap_hours, top_words_n=args.top_words)
    except ChatParseError as exc:
        print(tx["error"].format(message=exc.text(args.lang)), file=sys.stderr)
        return 1

    print_summary(report, args.lang)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {args.json}")
    if not args.no_pdf:
        out = args.out or Path(f"{args.chat.stem}_report.pdf")
        render_pdf(report, out, args.lang)
        print(f"\nPDF: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
