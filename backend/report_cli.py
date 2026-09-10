"""ChatPulse из терминала: анализ экспорта WhatsApp без фронтенда и Docker.

    python report_cli.py chat.txt --out report.pdf
    python report_cli.py "WhatsApp Chat.zip" --json report.json --no-pdf

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
from matplotlib.dates import AutoDateLocator, DateFormatter  # noqa: E402
from matplotlib.table import Table  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from analyzer_core import DEFAULT_GAP_HOURS, ChatParseError, analyze_file  # noqa: E402

ACCENT = "#4F46E5"
ACCENT_2 = "#10B981"
MISSED = "#F59E0B"
MUTED = "#6B7280"
GRID = "#E5E7EB"
A4 = (8.27, 11.69)
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
PLATFORMS = {"android": "Android", "ios": "iOS"}

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


# --- форматирование ---------------------------------------------------------------

def fmt_int(n: float) -> str:
    return f"{int(n):,}".replace(",", " ")


def fmt_duration(seconds: float | None) -> str:
    """45 с · 3 мин · 1 ч 5 мин · 2 дн 3 ч"""
    if seconds is None:
        return "—"
    s = int(round(seconds))
    if s < 60:
        return f"{s} с"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} мин" + (f" {s} с" if s and m < 10 else "")
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} ч" + (f" {m} мин" if m else "")
    d, h = divmod(h, 24)
    return f"{d} дн" + (f" {h} ч" if h else "")


def fmt_date(iso: str, with_time: bool = False) -> str:
    return datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y")


def emoji_name(emoji: str) -> str:
    """Шрифты matplotlib не рисуют цветные эмодзи, поэтому в PDF подписываем их именами."""
    if len(emoji) == 2 and all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in emoji):
        return "flag " + "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in emoji)
    skip = {0x200D, 0xFE0F, *range(0x1F3FB, 0x1F400)}  # ZWJ, вариация, тон кожи
    names = [unicodedata.name(c, "").lower() for c in emoji if ord(c) not in skip]
    return " + ".join(n for n in names if n) or "emoji"


def period(meta: dict) -> str:
    if not meta["first_message"]:
        return "нет сообщений"
    return f"{fmt_date(meta['first_message'])} – {fmt_date(meta['last_message'])} ({meta['days']} дн.)"


# --- сводка в терминал --------------------------------------------------------------

def print_summary(report: dict) -> None:
    meta, summary = report["meta"], report["summary"]
    responses = {r["name"]: r for r in report["response_times"]}

    print(f"\nChatPulse · WhatsApp ({PLATFORMS[meta['platform']]}) · {period(meta)}\n")
    print(
        f"Сообщений {fmt_int(summary['messages'])} · слов {fmt_int(summary['words'])} · "
        f"медиа {fmt_int(summary['media'])} · ссылок {fmt_int(summary['links'])} · "
        f"в среднем {summary['avg_words_per_message']} слова на сообщение"
    )

    if report["participants"]:
        print(f"\n{'Участник':<22}{'Сообщ.':>9}{'Доля':>8}{'Начинал':>9}{'Ответ, медиана':>16}")
        for p in report["participants"]:
            reply = responses.get(p["name"])
            print(
                f"{p['name'][:21]:<22}{fmt_int(p['messages']):>9}{p['share']:>7}%"
                f"{p['initiation_share']:>8}%{fmt_duration(reply and reply['median_s']):>16}"
            )

    calls = report["calls"]
    if calls["total"]:
        print(
            f"\nЗвонки: {calls['total']} (пропущено {calls['missed']}), "
            f"общая длительность {fmt_duration(calls['total_duration_s'])}, "
            f"в среднем {fmt_duration(calls['avg_duration_s'])}"
        )
    else:
        print("\nЗвонков в экспорте нет.")

    timeline = report["timeline"]
    if timeline["most_active_day"]:
        peak = timeline["most_active_day"]
        print(f"Самый активный день: {fmt_date(peak['date'])} — {fmt_int(peak['count'])} сообщ.")
    for i, s in enumerate(timeline["longest_silences"], 1):
        print(
            f"  тишина #{i}: {fmt_duration(s['duration_s'])} "
            f"({fmt_date(s['start'], True)} → {fmt_date(s['end'], True)}, первым написал(а) {s['broken_by']})"
        )

    if report["top_words"]:
        print("Топ-слова:", ", ".join(f"{w['word']} ({w['count']})" for w in report["top_words"][:10]))
    if report["top_emoji"]:
        print("Топ-эмодзи:", "  ".join(f"{e['emoji']} {e['count']}" for e in report["top_emoji"][:10]))
    for warning in report["warnings"]:
        print(f"⚠ {warning}")


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


def _hbars(ax, labels, values, *, color=ACCENT, texts=None, pad=1.2, min_slots=3) -> None:
    """Горизонтальные столбцы сверху вниз, подписи значений справа."""
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.6)
    _style_bars(ax, y, labels, min_slots)
    peak = max(values)
    for yi, v, t in zip(y, values, texts or [fmt_int(v) for v in values]):
        ax.text(v + peak * 0.015, yi, t, va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, peak * pad or 1)


def _timeline_chart(ax, tl: dict) -> None:
    days = np.array(tl["dates"], dtype="datetime64[D]")
    counts = np.array(tl["counts"], dtype=float)
    top = counts.max()

    ax.plot(days, counts, color=ACCENT, alpha=0.35, linewidth=0.8, label="за день")
    if len(counts) >= 14:
        # Скользящее среднее: неделя, а для многолетних чатов — месяц. Делим на
        # реальное число дней в окне, чтобы у краёв линия не проваливалась к нулю.
        size = 7 if len(counts) <= 365 else 30
        window = np.ones(size)
        smooth = np.convolve(counts, window, "same") / np.convolve(np.ones_like(counts), window, "same")
        ax.plot(days, smooth, color=ACCENT, linewidth=1.8, label=f"среднее за {size} дней")

    for i, s in enumerate(tl["longest_silences"], 1):
        start, end = np.datetime64(s["start"]), np.datetime64(s["end"])
        ax.axvspan(start, end, color=MISSED, alpha=0.22, linewidth=0)
        ax.text(start + (end - start) / 2, top * 1.1, str(i), ha="center", color="#B45309", fontsize=8)

    peak = tl["most_active_day"]
    px = np.datetime64(peak["date"])
    on_right = (px - days[0]) > (days[-1] - days[0]) * 0.7
    ax.scatter([px], [peak["count"]], color=ACCENT, s=14, zorder=3)
    ax.annotate(f"пик: {fmt_int(peak['count'])} · {fmt_date(peak['date'])}", xy=(px, peak["count"]),
                xytext=(-8 if on_right else 8, 0), textcoords="offset points",
                ha="right" if on_right else "left", va="center", fontsize=8, color=MUTED)

    ax.xaxis.set_major_locator(AutoDateLocator())
    ax.xaxis.set_major_formatter(DateFormatter("%d.%m.%y"))
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_ylim(0, top * 1.22 or 1)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncols=2)


def _highlights(report: dict) -> list[str]:
    calls, tl = report["calls"], report["timeline"]
    lines = []
    if calls["total"]:
        lines.append(
            f"Звонки: {calls['total']} (голосовых {calls['voice']}, видео {calls['video']}), "
            f"пропущено {calls['missed']}"
        )
        lines.append(
            f"Длительность звонков: всего {fmt_duration(calls['total_duration_s'])}, "
            f"в среднем {fmt_duration(calls['avg_duration_s'])}, самый долгий {fmt_duration(calls['longest_s'])}"
        )
    else:
        lines.append("Звонков в экспорте нет.")
    if tl["most_active_day"]:
        peak = tl["most_active_day"]
        lines.append(f"Самый активный день: {fmt_date(peak['date'])} — {fmt_int(peak['count'])} сообщений")
    for i, s in enumerate(tl["longest_silences"], 1):
        lines.append(
            f"Тишина {i}: {fmt_duration(s['duration_s'])} — {fmt_date(s['start'], True)} → "
            f"{fmt_date(s['end'], True)}, первым написал(а) {s['broken_by']}"
        )
    return lines


def page_overview(pdf: PdfPages, report: dict) -> None:
    """Первая страница — одностраничная выжимка: цифры, участники, таймлайн, рекорды."""
    meta, summary, tl = report["meta"], report["summary"], report["timeline"]
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.94, "ChatPulse", fontsize=26, weight="bold", color=ACCENT)
    fig.text(0.07, 0.915, f"Отчёт по чату WhatsApp · {PLATFORMS[meta['platform']]} · {period(meta)}",
             fontsize=10, color=MUTED)

    kpis = [
        ("сообщений", fmt_int(summary["messages"])),
        ("слов", fmt_int(summary["words"])),
        ("медиа", fmt_int(summary["media"])),
        ("ссылок", fmt_int(summary["links"])),
        ("слов в сообщении", str(summary["avg_words_per_message"])),
    ]
    for i, (label, value) in enumerate(kpis):
        fig.text(0.07 + i * 0.18, 0.855, value, fontsize=18, weight="bold")
        fig.text(0.07 + i * 0.18, 0.838, label, fontsize=8.5, color=MUTED)

    y = 0.79  # «курсор» сверху вниз: высота блоков зависит от числа участников
    fig.text(0.07, y, "Участники", fontsize=11, weight="bold")
    y -= 0.012
    people = report["participants"][:10]
    if people:
        responses = {r["name"]: r for r in report["response_times"]}
        header = ["Участник", "Сообщ.", "Доля", "Слов", "Слов/сообщ.", "Медиа", "Начинал", "Ответ*"]
        widths = [0.21, 0.1, 0.08, 0.1, 0.15, 0.08, 0.11, 0.13]
        rows = [
            [
                p["name"][:24], fmt_int(p["messages"]), f"{p['share']}%", fmt_int(p["words"]),
                str(p["avg_words"]), fmt_int(p["media"]), f"{p['initiation_share']}%",
                fmt_duration(responses[p["name"]]["median_s"]) if p["name"] in responses else "—",
            ]
            for p in people
        ]
        table_h = 0.021 * (len(rows) + 1)
        ax = fig.add_axes((0.07, y - table_h, 0.86, table_h))
        ax.axis("off")
        table = Table(ax, bbox=(0, 0, 1, 1))
        for r, values in enumerate([header, *rows]):
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

        note = "* медиана времени ответа на сообщение собеседника"
        if (extra := len(report["participants"]) - len(rows)) > 0:
            note += f" · ещё участников: {extra}"
        fig.text(0.07, y, note, fontsize=7.5, color=MUTED, va="top")
        y -= 0.05
    else:
        fig.text(0.07, y - 0.02, "Нет сообщений от участников.", fontsize=9.5, color=MUTED)
        y -= 0.06

    if len(tl["dates"]) >= 2:
        fig.text(0.07, y, "Сообщения по дням", fontsize=11, weight="bold")
        _timeline_chart(fig.add_axes((0.1, y - 0.235, 0.83, 0.215)), tl)
        y -= 0.285

    fig.text(0.07, y, "Коротко", fontsize=11, weight="bold")
    y -= 0.026
    for line in _highlights(report):
        fig.text(0.07, y, line, fontsize=9)
        y -= 0.02
    y -= 0.01
    for warning in report["warnings"]:
        fig.text(0.07, y, f"⚠ {warning}", fontsize=9, color="#B45309")
        y -= 0.02

    fig.text(0.07, 0.03, "Отчёт собран локально: файл чата не сохранялся и никуда не отправлялся.",
             fontsize=7.5, color=MUTED)
    pdf.savefig(fig)
    plt.close(fig)


def page_participants(pdf: PdfPages, report: dict) -> None:
    fig, axes = plt.subplots(4, 1, figsize=A4, gridspec_kw={"hspace": 0.5})
    fig.subplots_adjust(left=0.2, right=0.95, top=0.95, bottom=0.05)
    people = report["participants"][:12]
    names = [p["name"][:22] for p in people]

    axes[0].set_title("Сообщения по участникам")
    _hbars(axes[0], names, [p["messages"] for p in people],
           texts=[f"{fmt_int(p['messages'])} · {p['share']}%" for p in people], pad=1.3)

    axes[1].set_title(f"Кто начинает разговор (первое сообщение после паузы > {report['meta']['gap_hours']:g} ч)")
    _hbars(axes[1], names, [p["initiation_share"] for p in people], color=ACCENT_2,
           texts=[f"{p['initiations']} раз · {p['initiation_share']}%" for p in people], pad=1.35)
    axes[1].set_xlabel("% разговоров", color=MUTED)

    axes[2].set_title("Время ответа на сообщение собеседника, медиана")
    replies = report["response_times"][:12]
    if replies:
        _hbars(axes[2], [r["name"][:22] for r in replies], [r["median_s"] / 60 for r in replies],
               texts=[f"{fmt_duration(r['median_s'])} · среднее {fmt_duration(r['mean_s'])}" for r in replies],
               pad=1.8)
        axes[2].set_xlabel("минуты", color=MUTED)
    else:
        _empty(axes[2], "Нужно хотя бы два участника")

    ax = axes[3]
    ax.set_title("Звонки по участникам (кто звонил)")
    callers = report["calls"]["by_participant"][:12]
    if callers:
        y = np.arange(len(callers))[::-1]
        done = np.array([c["completed"] for c in callers])
        ax.barh(y, done, color=ACCENT, height=0.6, label="состоялись")
        ax.barh(y, [c["missed"] for c in callers], left=done, color=MISSED, height=0.6, label="пропущены")
        _style_bars(ax, y, [c["name"][:22] for c in callers], min_slots=3)
        peak = max(c["total"] for c in callers)
        for yi, c in zip(y, callers):
            ax.text(c["total"] + peak * 0.015, yi, f"{c['total']} · {fmt_duration(c['duration_s'])}",
                    va="center", fontsize=8, color=MUTED)
        ax.set_xlim(0, peak * 1.35)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(frameon=False, loc="lower right", fontsize=8)
    else:
        _empty(ax, "Звонков в экспорте нет")

    pdf.savefig(fig)
    plt.close(fig)


def page_activity(pdf: PdfPages, report: dict) -> None:
    activity = report["activity"]
    fig = plt.figure(figsize=A4)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.1, 1, 1], hspace=0.45,
                            left=0.1, right=0.93, top=0.95, bottom=0.06)

    ax = fig.add_subplot(grid[0])
    ax.set_title("Активность: день недели × час")
    cmap = LinearSegmentedColormap.from_list("chatpulse", ["#F3F4F6", ACCENT])
    image = ax.imshow(np.array(activity["matrix"]), aspect="auto", cmap=cmap)
    ax.set_yticks(range(7), WEEKDAYS)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02).outline.set_visible(False)

    ax = fig.add_subplot(grid[1])
    ax.set_title("По часам суток")
    ax.bar(range(24), activity["by_hour"], color=ACCENT, width=0.75)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}:00" for h in range(0, 24, 2)], fontsize=7.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    ax = fig.add_subplot(grid[2])
    ax.set_title("По дням недели")
    ax.bar(WEEKDAYS, activity["by_weekday"], color=ACCENT_2, width=0.6)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    pdf.savefig(fig)
    plt.close(fig)


def page_words(pdf: PdfPages, report: dict) -> None:
    fig, (ax_words, ax_emoji) = plt.subplots(
        2, 1, figsize=A4, gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.2})
    fig.subplots_adjust(left=0.36, right=0.93, top=0.95, bottom=0.05)

    words = report["top_words"][:25]
    ax_words.set_title("Топ-слова (без стоп-слов и имён участников)")
    if words:
        _hbars(ax_words, [w["word"] for w in words], [w["count"] for w in words], min_slots=10)
    else:
        _empty(ax_words, "Текстовых сообщений нет")

    emoji = report["top_emoji"][:12]
    ax_emoji.set_title("Топ-эмодзи")
    if emoji:
        _hbars(ax_emoji, [emoji_name(e["emoji"])[:40] for e in emoji], [e["count"] for e in emoji],
               color=ACCENT_2, min_slots=6)
    else:
        _empty(ax_emoji, "Эмодзи не найдены")

    pdf.savefig(fig)
    plt.close(fig)


def render_pdf(report: dict, path: Path) -> None:
    with PdfPages(path, metadata={"Title": "ChatPulse — отчёт по чату WhatsApp"}) as pdf:
        page_overview(pdf, report)
        if report["summary"]["messages"]:  # без сообщений остальные страницы были бы пустыми
            page_participants(pdf, report)
            page_activity(pdf, report)
            page_words(pdf, report)


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
    args = parser.parse_args(argv)

    try:
        data = args.chat.read_bytes()
    except OSError as exc:
        print(f"Не удалось прочитать {args.chat}: {exc.strerror}", file=sys.stderr)
        return 1
    try:
        report = analyze_file(data, args.chat.name, gap_hours=args.gap_hours, top_words_n=args.top_words)
    except ChatParseError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print_summary(report)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {args.json}")
    if not args.no_pdf:
        out = args.out or Path(f"{args.chat.stem}_report.pdf")
        render_pdf(report, out)
        print(f"\nPDF: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
