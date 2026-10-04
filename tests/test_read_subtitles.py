from subtitlechecker import read_subtitles
from subtitlechecker.read_subtitles import decode_subtitle, normalize_line_endings, normalize_nones, index_subtitle
from subtitlechecker.fileobject import fileobject
from subtitlechecker.evaluation_result import evaluation_result
from conftest import words

def test_decode_subtitle_utf8():
    text = "Café au lait, s'il vous plaît. Où est la gare? Très bien, merci beaucoup.\n" * 5
    assert decode_subtitle(text.encode("utf-8")) == text

def test_decode_subtitle_falls_back_to_latin1(monkeypatch):
    monkeypatch.setattr(read_subtitles.chardet, "detect", lambda raw: {"encoding": None})
    assert decode_subtitle("café".encode("latin-1")) == "café"

def test_decode_subtitle_replaces_undecodable_bytes(monkeypatch):
    monkeypatch.setattr(read_subtitles.chardet, "detect", lambda raw: {"encoding": "utf-8"})
    assert decode_subtitle(b"abc\xff") == "abc�"

def test_normalize_line_endings():
    assert normalize_line_endings("a\r\nb\r\r\nc\rd\ne") == "a\nb\nc\nd\ne"

def test_normalize_nones_numbers_cues_in_order():
    text = "None\n00:00:01,000 --> 00:00:02,000\nNone here\n\n None \nnext"
    assert normalize_nones(text) == "1\n00:00:01,000 --> 00:00:02,000\nNone here\n\n2\nnext"

def test_index_subtitle(tmp_path):
    srt = tmp_path / "movie.srt"
    srt.write_bytes(
        b"None\r\n00:00:01,000 --> 00:00:02,500\r\n<i>Hello, world!</i>\r\n\r\n"
        b"None\r\n00:00:10,000 --> 00:00:12,000\r\n[music] Don't\r\nstop - now\r\n\r\n")
    result = evaluation_result()

    subtitles = index_subtitle(fileobject(str(srt)), result)

    assert subtitles == words((1.0, "hello"), (1.0, "world"), (10.0, "don't"), (10.0, "stop"), (10.0, "now"))
    assert result.summary.total_subtitle_word_count == 5
