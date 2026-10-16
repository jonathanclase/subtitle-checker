import json, os, pytest
from subtitlechecker import get_clips
from subtitlechecker.get_clips import get_video_info, calculate_clip_times, find_audio_stream, create_clips
from subtitlechecker.fileobject import fileobject
from subtitlechecker.segment import segment
from conftest import fake_run

VIDEO = fileobject("/videos/movie.mkv")

def ffprobe_info(seconds:float, streams:list) -> str:
    return json.dumps({"streams": streams, "format": {"duration": str(seconds)}})

def test_get_video_info(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return fake_run(ffprobe_info(1000, [{"avg_frame_rate": "24000/1001"}]))
    monkeypatch.setattr(get_clips.subprocess, "run", run)

    video_length, fps = get_video_info(VIDEO)

    assert video_length == 1000.0
    assert fps == pytest.approx(23.976, abs=0.001)
    assert calls[0][0] == "ffprobe" and calls[0][-1] == VIDEO.path

@pytest.mark.parametrize("streams, expected", [
    ([{"avg_frame_rate": "25"}], 25.0),
    ([{"avg_frame_rate": "0/0"}], 0.0),
    ([], 0.0),
])
def test_get_video_info_frame_rate_edge_cases(monkeypatch, streams, expected):
    monkeypatch.setattr(get_clips.subprocess, "run", lambda command, **kwargs: fake_run(ffprobe_info(1000, streams)))
    assert get_video_info(VIDEO)[1] == expected

def test_calculate_clip_times_spreads_clips_between_margins():
    clips = calculate_clip_times(1000.0, clip_count=5)

    # Starts run from 300s to 1000 - 300 - 75 = 625s
    assert [c.clip_start for c in clips] == [
        "00:05:00.000", "00:06:21.250", "00:07:42.500", "00:09:03.750", "00:10:25.000"]
    assert all(c.audio_clip is None for c in clips)

def test_calculate_clip_times_rejects_fewer_than_two_clips():
    with pytest.raises(ValueError, match="at least two"):
        calculate_clip_times(1000.0, clip_count=1)

def test_calculate_clip_times_rejects_short_video():
    with pytest.raises(ValueError, match="too short"):
        calculate_clip_times(600.0)

@pytest.mark.parametrize("streams, expected", [
    ([{"index": 1, "tags": {"language": "fre"}}, {"index": 2, "tags": {"language": "eng"}}], 2),
    ([{"index": 1, "tags": {"language": "fre"}}, {"index": 3}], 1),
])
def test_find_audio_stream(monkeypatch, streams, expected):
    monkeypatch.setattr(get_clips.subprocess, "run",
                        lambda command, **kwargs: fake_run(json.dumps({"streams": streams})))
    assert find_audio_stream(VIDEO) == expected

def test_find_audio_stream_without_audio(monkeypatch):
    monkeypatch.setattr(get_clips.subprocess, "run", lambda command, **kwargs: fake_run("{}"))

    with pytest.raises(ValueError, match="No audio tracks"):
        find_audio_stream(VIDEO)

def test_create_clips_cuts_one_clip_per_segment(monkeypatch, tmp_path):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return fake_run()
    monkeypatch.setattr(get_clips, "find_audio_stream", lambda video_file: 2)
    monkeypatch.setattr(get_clips.subprocess, "run", run)
    clips = [segment("00:05:00.000"), segment("00:06:00.000")]

    create_clips(VIDEO, clips, str(tmp_path), duration=10)

    first_path = os.path.join(str(tmp_path), "movie_clip_01.wav")
    assert calls[0] == ["ffmpeg", "-v", "error", "-y", "-ss", "00:05:00.000", "-i", VIDEO.path,
                        "-t", "10.000", "-map", "0:2", "-ac", "1", "-ar", "16000", first_path]
    assert calls[1][5] == "00:06:00.000"
    assert clips[0].audio_clip.path == first_path
    assert clips[1].audio_clip.name == "movie_clip_02.wav"

def test_create_clips_applies_audio_filter(monkeypatch, tmp_path):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return fake_run()
    monkeypatch.setattr(get_clips, "find_audio_stream", lambda video_file: 0)
    monkeypatch.setattr(get_clips.subprocess, "run", run)

    create_clips(VIDEO, [segment("00:05:00.000")], str(tmp_path), audio_filter="highpass=f=200")

    af = calls[0].index("-af")
    assert calls[0][af + 1] == "highpass=f=200"

def test_create_clips_raises_when_ffmpeg_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(get_clips, "find_audio_stream", lambda video_file: 0)
    monkeypatch.setattr(get_clips.subprocess, "run", lambda command, **kwargs: fake_run(returncode=1, stderr="boom"))

    with pytest.raises(RuntimeError, match="(?s)clip 1.*boom"):
        create_clips(VIDEO, [segment("00:05:00.000")], str(tmp_path))
