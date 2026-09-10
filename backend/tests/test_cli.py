"""Смоук-тесты report_cli.py: PDF и JSON создаются, «грязные» файлы не роняют отчёт."""

import json
from pathlib import Path

import pytest

import report_cli

DEMO = Path(__file__).resolve().parents[2] / "examples" / "demo_chat.txt"


def test_pdf_and_json(tmp_path, capsys):
    pdf, report_json = tmp_path / "report.pdf", tmp_path / "report.json"
    code = report_cli.main([str(DEMO), "--out", str(pdf), "--json", str(report_json)])

    assert code == 0
    assert pdf.read_bytes()[:5] == b"%PDF-"
    report = json.loads(report_json.read_text("utf-8"))
    assert report["summary"]["messages"] > 0
    assert "ChatPulse" in capsys.readouterr().out


@pytest.mark.parametrize(
    "chat",
    [
        "01.01.21, 10:00 - Иван: заметка себе\n",           # один участник, нет звонков
        "01.01.21, 10:00 - Иван создал группу «Тест»\n",    # только служебные события
    ],
)
def test_empty_states_still_render(tmp_path, chat):
    path = tmp_path / "chat.txt"
    path.write_text(chat, encoding="utf-8")
    assert report_cli.main([str(path), "--out", str(tmp_path / "out.pdf")]) == 0
    assert (tmp_path / "out.pdf").stat().st_size > 0


def test_unreadable_chat_exits_with_error(tmp_path, capsys):
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")
    assert report_cli.main([str(path), "--no-pdf"]) == 1
    assert "пустой" in capsys.readouterr().err


def test_missing_file(tmp_path, capsys):
    assert report_cli.main([str(tmp_path / "nope.txt")]) == 1
    assert "Не удалось прочитать" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, "—"), (45, "45 с"), (156, "2 мин 36 с"), (600, "10 мин"), (3900, "1 ч 5 мин"), (172830, "2 дн")],
)
def test_fmt_duration(seconds, expected):
    assert report_cli.fmt_duration(seconds) == expected


def test_emoji_names_for_pdf():
    assert report_cli.emoji_name("🇷🇺") == "flag RU"
    assert report_cli.emoji_name("👍🏽") == "thumbs up sign"
    assert report_cli.emoji_name("👨‍👩‍👧") == "man + woman + girl"
