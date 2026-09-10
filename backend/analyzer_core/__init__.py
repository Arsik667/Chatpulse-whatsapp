"""analyzer_core — вся логика ChatPulse без веба.

От этого пакета зависят и FastAPI (app/main.py), и консольный report_cli.py,
поэтому здесь только чистые функции: байты файла на входе, данные на выходе.
"""

from .parser import ChatParseError, ParsedChat, load_chat, parse_chat, read_export

__all__ = ["ChatParseError", "ParsedChat", "load_chat", "parse_chat", "read_export"]
