import pytest
from subtitlechecker import transcribe as tr
from subtitlechecker.fileobject import fileobject
from subtitlechecker.evaluation_result import chunk
from conftest import words, whisper_word, whisper_segment, whisper_info

@pytest.fixture(autouse=True)
def clear_model_cache():
    tr.load_model.cache_clear()
    yield
    tr.load_model.cache_clear()

@pytest.mark.parametrize("cuda_devices, expected", [(1, ("cuda", "float16")), (0, ("cpu", "int8"))])
def test_pick_device(monkeypatch, cuda_devices, expected):
    monkeypatch.setattr(tr.ctranslate2, "get_cuda_device_count", lambda: cuda_devices)
    assert tr.pick_device() == expected

def test_load_model_loads_each_model_once(monkeypatch):
    built = []
    class FakeModel:
        def __init__(self, model, device, compute_type):
            built.append((model, device, compute_type))
    monkeypatch.setattr(tr, "WhisperModel", FakeModel)
    monkeypatch.setattr(tr, "pick_device", lambda: ("cpu", "int8"))

    first = tr.load_model("small.en")
    assert tr.load_model("small.en") is first
    tr.load_model("base.en")

    assert built == [("small.en", "cpu", "int8"), ("base.en", "cpu", "int8")]

def test_transcribe_returns_list_and_info(monkeypatch):
    info = whisper_info()
    calls = []
    class FakeModel:
        def transcribe(self, path, **kwargs):
            calls.append((path, kwargs))
            return (s for s in ["seg1", "seg2"]), info
    loaded = []
    def load_model(name):
        loaded.append(name)
        return FakeModel()
    monkeypatch.setattr(tr, "load_model", load_model)

    segs, returned_info = tr.transcribe(fileobject("/clips/a.wav"), vad_threshold=0.3, model="tiny.en")

    assert segs == ["seg1", "seg2"]
    assert returned_info is info
    assert loaded == ["tiny.en"]
    assert calls == [("/clips/a.wav", {"language": "en", "word_timestamps": True,
                                       "vad_filter": True, "vad_parameters": {"threshold": 0.3}})]

def test_index_transcript():
    segs = [
        whisper_segment(" Hello, world. ", 1.0, 3.0,
                        [whisper_word(" Hello,", 1.0, 0.9), whisper_word(" world.", 1.5, 0.7)],
                        avg_logprob=-0.2, no_speech_prob=0.1, compression_ratio=1.5, temperature=0.0),
        whisper_segment(" Okay", 5.0, 6.0, [whisper_word(" Okay", 5.0, 0.6)],
                        avg_logprob=-0.5, no_speech_prob=0.4, compression_ratio=2.0, temperature=0.2),
    ]
    transcript, this_segment = tr.index_transcript("00:01:00.000", segs, whisper_info(75.0, 30.0))

    # Word times are the clip start plus Whisper's time within the clip
    assert transcript == words((61.0, "hello"), (61.5, "world"), (65.0, "okay"))
    assert this_segment.language == "en"
    assert this_segment.language_probability == 1.0
    assert this_segment.duration == 75.0
    assert this_segment.duration_after_vad == 30.0
    assert this_segment.speech_fraction == pytest.approx(0.4)
    assert this_segment.probability == pytest.approx((0.9 + 0.7 + 0.6) / 3)
    assert this_segment.chunks == [
        chunk("Hello, world.", 61.0, 63.0, 2.0, 2, -0.2, 0.1, 1.5, 0.0),
        chunk("Okay", 65.0, 66.0, 1.0, 1, -0.5, 0.4, 2.0, 0.2),
    ]
    # Weighted by word count: (-0.2 * 2 + -0.5 * 1) / 3
    assert this_segment.mean_avg_logprob == pytest.approx(-0.3)
    assert this_segment.max_no_speech_prob == 0.4
    assert this_segment.max_compression_ratio == 2.0
    assert this_segment.retried is True

def test_index_transcript_with_nothing_heard():
    transcript, this_segment = tr.index_transcript("00:01:00.000", [], whisper_info(0.0, 0.0))

    assert transcript == []
    assert this_segment.speech_fraction is None
    assert this_segment.probability is None
    assert this_segment.chunks == []
    assert this_segment.mean_avg_logprob is None
    assert this_segment.max_no_speech_prob is None
    assert this_segment.retried is False

def test_index_transcript_segment_without_words():
    transcript, this_segment = tr.index_transcript("00:00:00.000", [whisper_segment(" ", 0.0, 1.0, None, no_speech_prob=0.8)],
                                                   whisper_info())

    assert transcript == []
    assert this_segment.chunks[0].word_count == 0
    assert this_segment.probability is None
    # No words to weight by, so there's no average
    assert this_segment.mean_avg_logprob is None
    assert this_segment.max_no_speech_prob == 0.8
