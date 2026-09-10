"""У каждого текста есть оба перевода, и подстановки в них одинаковые."""

from string import Formatter

import pytest

from analyzer_core.messages import LANGS, MESSAGES, message


def fields(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


@pytest.mark.parametrize("code", sorted(MESSAGES))
def test_every_message_has_all_languages(code):
    texts = MESSAGES[code]
    assert set(texts) == set(LANGS)
    assert fields(texts["ru"]) == fields(texts["en"])


def test_unknown_language_falls_back_to_russian():
    assert message("empty_file", "de") == message("empty_file", "ru")


def test_placeholders_are_filled():
    assert message("upload_too_large", "en", limit=200).startswith("The file is larger than 200 MB")
