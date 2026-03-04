from layout_switcher import WordBuffer, choose_direction_from_word, convert_layout_word


def test_convert_en_to_ru_basic():
    assert convert_layout_word("ghbdtn", "en_to_ru") == "привет"


def test_convert_ru_to_en_basic():
    assert convert_layout_word("руддщ", "ru_to_en") == "hello"


def test_convert_preserves_case():
    assert convert_layout_word("Ghbdtn", "en_to_ru") == "Привет"


def test_convert_keeps_non_mapped_chars():
    assert convert_layout_word("ghbdtn123!", "en_to_ru") == "привет123!"


def test_word_buffer_add_and_backspace():
    buf = WordBuffer(max_len=64)
    buf.add_char("h")
    buf.add_char("i")
    assert buf.word() == "hi"
    buf.backspace()
    assert buf.word() == "h"


def test_word_buffer_clear():
    buf = WordBuffer(max_len=64)
    buf.add_char("h")
    buf.add_char("i")
    buf.clear()
    assert buf.word() == ""


def test_word_buffer_len_limit_resets():
    buf = WordBuffer(max_len=3)
    buf.add_char("a")
    buf.add_char("b")
    buf.add_char("c")
    buf.add_char("d")
    assert buf.word() == ""


def test_choose_direction_prefers_cyrillic():
    assert choose_direction_from_word("руддщ") == "ru_to_en"


def test_choose_direction_defaults_to_en_to_ru():
    assert choose_direction_from_word("hello") == "en_to_ru"
