"""analyzer_core — вся логика ChatPulse без веба.

От этого пакета зависят и FastAPI (app/main.py), и консольный report_cli.py,
поэтому здесь только чистые функции: байты файла на входе, данные на выходе.
"""

from .messages import DEFAULT_LANG, LANGS, message
from .metrics import DEFAULT_GAP_HOURS, analyze
from .parser import ChatParseError, ParsedChat, load_chat, parse_chat, read_export


def analyze_file(data: bytes, filename: str = "", **options) -> dict:
    """Байты .txt/.zip → готовый отчёт. Единая точка входа для API и CLI."""
    return analyze(load_chat(data, filename), **options)


__all__ = [
    "DEFAULT_GAP_HOURS",
    "DEFAULT_LANG",
    "LANGS",
    "ChatParseError",
    "ParsedChat",
    "analyze",
    "analyze_file",
    "load_chat",
    "message",
    "parse_chat",
    "read_export",
]
