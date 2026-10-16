import pytest
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

    subtitles = index_subtitle(fileobject(str(srt)), result, 24.0)

    assert subtitles == words((1.0, "hello"), (1.0, "world"), (10.0, "don't"), (10.0, "stop"), (10.0, "now"))
    assert result.summary.total_subtitle_word_count == 5

def test_index_subtitle_ass_skips_comments_and_tags(tmp_path):
    ass = tmp_path / "movie.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,{\\i1}Hello{\\i0}\\Nthere\n"
        "Comment: 0,0:00:04.00,0:00:05.00,Default,,0,0,0,,translator note\n", encoding="utf-8")

    assert index_subtitle(fileobject(str(ass)), evaluation_result(), 24.0) == words((1.5, "hello"), (1.5, "there"))

def test_index_subtitle_vtt(tmp_path):
    vtt = tmp_path / "movie.vtt"
    vtt.write_text("WEBVTT\n\n00:00:02.000 --> 00:00:03.000\nHi there\n", encoding="utf-8")

    assert index_subtitle(fileobject(str(vtt)), evaluation_result(), 24.0) == words((2.0, "hi"), (2.0, "there"))

def test_index_subtitle_microdvd_uses_declared_frame_rate(tmp_path):
    sub = tmp_path / "movie.sub"
    sub.write_text("{1}{1}25\n{50}{75}Hello\n", encoding="utf-8")

    # The video's 24 fps is ignored, and the declaration isn't read as a subtitle
    assert index_subtitle(fileobject(str(sub)), evaluation_result(), 24.0) == words((2.0, "hello"),)

@pytest.mark.parametrize("video_fps, expected_start", [(25.0, 4.0), (0.0, 100 / 23.976)])
def test_index_subtitle_microdvd_falls_back_to_video_frame_rate(tmp_path, video_fps, expected_start):
    sub = tmp_path / "movie.sub"
    sub.write_text("{100}{125}Hello\n", encoding="utf-8")

    subtitles = index_subtitle(fileobject(str(sub)), evaluation_result(), video_fps)

    assert subtitles[0].text == "hello"
    assert subtitles[0].secs_timestamp == pytest.approx(expected_start, abs=0.001)

def test_index_subtitle_rejects_vobsub(tmp_path):
    sub = tmp_path / "movie.sub"
    # VobSub .sub files are MPEG program streams of images, starting with a pack header
    sub.write_bytes(b"\x00\x00\x01\xba\x44\x00\x04\x00\x04\x01" + bytes(range(256)) * 4)

    with pytest.raises(ValueError, match="VobSub"):
        index_subtitle(fileobject(str(sub)), evaluation_result(), 24.0)

def test_index_subtitle_rejects_unknown_format(tmp_path):
    srt = tmp_path / "notes.srt"
    srt.write_text("Just some notes, not subtitles.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="recognized subtitle format"):
        index_subtitle(fileobject(str(srt)), evaluation_result(), 24.0)
