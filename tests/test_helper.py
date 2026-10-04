import pytest
from subtitlechecker.helper import normalize_words, clean_subtitle_text, timestamp_to_seconds, add_times

@pytest.mark.parametrize("text, expected", [
    ("Hello, World!", ["hello", "world"]),
    ("I’m here", ["i'm", "here"]),                      # Curly apostrophe
    ("Rock & roll 100%", ["rock", "and", "roll", "100", "percent"]),
    ("well-known", ["well", "known"]),
    ("No--wait", ["no", "wait"]),
    ("either/or", ["either", "or"]),
    ("'hello' don't", ["hello", "don't"]),              # Quote apostrophes trimmed, inner one kept
    ("Wait…", ["wait"]),                                # NFKC turns "…" into "..."
    ("ＨＥＬＬＯ", ["hello"]),                           # Full-width letters
    ("", []),
    ("?! ...", []),
])
def test_normalize_words(text, expected):
    assert normalize_words(text) == expected

def test_clean_subtitle_text_joins_lines_and_strips_brackets():
    assert clean_subtitle_text("[music] Hello\r\nthere (laughs)\nfriend") == "Hello there friend"

def test_clean_subtitle_text_collapses_whitespace():
    assert clean_subtitle_text("  a   b\t c  ") == "a b c"

@pytest.mark.parametrize("timestamp, expected", [
    ("01:02:03.500", 3723.5),
    ("00:00:01,250", 1.25),         # .srt comma form
    ("00:01:00", 60.0),             # No milliseconds
])
def test_timestamp_to_seconds(timestamp, expected):
    assert timestamp_to_seconds(timestamp) == pytest.approx(expected)

@pytest.mark.parametrize("start, seconds, expected", [
    ("00:01:00.000", 2.5, 62.5),
    ("00:01:00,000", -10, 50.0),
])
def test_add_times(start, seconds, expected):
    assert add_times(start, seconds) == pytest.approx(expected)
