"""Тексты для людей на русском и английском: ошибки и предупреждения.

В отчёте analyze() предупреждения хранятся кодами — это данные, как номер дня
недели. Слова подставляет тот, кто отчёт показывает: API и CLI берут их отсюда,
фронтенд — из своего словаря src/i18n.js.
"""

LANGS = ("ru", "en")
DEFAULT_LANG = "ru"

MESSAGES: dict[str, dict[str, str]] = {
    # --- ошибки разбора файла (ChatParseError) ---
    "empty_file": {
        "ru": "Файл пустой.",
        "en": "The file is empty.",
    },
    "unknown_format": {
        "ru": "Не удалось распознать формат: строки не похожи на экспорт WhatsApp "
              "(ожидается «31.12.20, 23:59 - Имя: текст» или «[31.12.20, 23:59:59] Имя: текст»).",
        "en": "Unrecognized format: the lines don't look like a WhatsApp export "
              "(expected “12/31/20, 11:59 PM - Name: text” or “[12/31/20, 11:59:59 PM] Name: text”).",
    },
    "no_valid_dates": {
        "ru": "Не найдено ни одного сообщения с корректной датой.",
        "en": "No messages with a valid date were found.",
    },
    "not_a_zip": {
        "ru": "Файл называется .zip, но это не zip-архив.",
        "en": "The file is named .zip but it is not a zip archive.",
    },
    "zip_without_chat": {
        "ru": "В архиве нет .txt-файла с перепиской. Это точно экспорт WhatsApp?",
        "en": "The archive has no .txt file with the chat. Is it really a WhatsApp export?",
    },
    "chat_too_large": {
        "ru": "Файл переписки в архиве слишком большой.",
        "en": "The chat file inside the archive is too large.",
    },
    "zip_unreadable": {
        "ru": "Не удалось распаковать .zip: {reason}",
        "en": "Could not unpack the .zip: {reason}",
    },
    # --- ошибки загрузки (API) ---
    "upload_too_large": {
        "ru": "Файл больше {limit} МБ. Попробуйте экспорт без медиа — это один .txt.",
        "en": "The file is larger than {limit} MB. Try exporting without media — that's a single .txt.",
    },
    "not_multipart": {
        "ru": "Ожидается multipart/form-data с файлом в поле file.",
        "en": "Expected multipart/form-data with the file in the “file” field.",
    },
    "bad_form": {
        "ru": "Не удалось разобрать форму: {reason}",
        "en": "Could not parse the form: {reason}",
    },
    "no_file_field": {
        "ru": "В запросе нет файла в поле file.",
        "en": "The request has no file in the “file” field.",
    },
    # --- предупреждения отчёта (report["warnings"]) ---
    "no_messages": {
        "ru": "В чате нет сообщений от участников — только служебные уведомления.",
        "en": "The chat has no messages from participants — only system notifications.",
    },
    "single_participant": {
        "ru": "В чате один участник: время ответа и инициатива разговоров не считаются.",
        "en": "The chat has a single participant: response times and conversation starts are not computed.",
    },
    "no_seconds": {
        "ru": "В экспорте время без секунд (так пишет Android) — время ответа точно до минуты.",
        "en": "Timestamps in the export have no seconds (Android writes them this way), "
              "so response times are accurate to a minute.",
    },
}


def message(code: str, lang: str = DEFAULT_LANG, **params) -> str:
    """Текст по коду на нужном языке; незнакомый язык — по-русски."""
    texts = MESSAGES[code]
    return texts.get(lang, texts[DEFAULT_LANG]).format(**params)
