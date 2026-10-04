import json, pytest
from subtitlechecker import main as main_module, get_clips, transcribe
from subtitlechecker.main import validate_arguments, cli
from subtitlechecker.fileobject import fileobject
from subtitlechecker.segment import segment
from conftest import whisper_word, whisper_segment, whisper_info

@pytest.fixture
def files(tmp_path):
    video = tmp_path / "movie.mkv"
    subtitle = tmp_path / "movie.srt"
    video.write_bytes(b"")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\nOne two three four five\n\n", encoding="utf-8")
    return str(video), str(subtitle)

def test_validate_arguments_accepts_existing_files(files):
    assert validate_arguments(list(files)) is True

def test_validate_arguments_extension_is_case_insensitive(tmp_path, files):
    video = tmp_path / "MOVIE.MKV"
    video.write_bytes(b"")
    assert validate_arguments([str(video), files[1]]) is True

@pytest.mark.parametrize("args", [[], ["only_one.mkv"], ["a.mkv", "b.srt", "c"]])
def test_validate_arguments_wrong_count(capsys, args):
    assert validate_arguments(args) is False
    assert f"Expected 2 arguments, got {len(args)}." in capsys.readouterr().out

def test_validate_arguments_missing_file(capsys, tmp_path, files):
    assert validate_arguments([files[0], str(tmp_path / "missing.srt")]) is False
    assert "Subtitle file not found" in capsys.readouterr().out

def test_validate_arguments_bad_extension(capsys, tmp_path, files):
    notes = tmp_path / "notes.txt"
    notes.write_text("")
    assert validate_arguments([str(notes), files[1]]) is False
    assert "Video file must end in .mkv" in capsys.readouterr().out

def test_validate_arguments_reports_every_problem(capsys, tmp_path, files):
    assert validate_arguments([str(tmp_path / "missing.txt"), files[1]]) is False
    out = capsys.readouterr().out
    assert "Video file not found" in out
    assert "Video file must end in" in out

def test_cli_exits_on_invalid_arguments(monkeypatch, capsys):
    monkeypatch.setattr(main_module.sys, "argv", ["subtitlechecker"])
    monkeypatch.setattr(main_module, "main", lambda video, subtitle: pytest.fail("main should not run"))

    with pytest.raises(SystemExit) as exit_info:
        cli()

    assert exit_info.value.code == 1
    assert "Usage: subtitlechecker <video> <subtitles>" in capsys.readouterr().out

def test_cli_runs_main(monkeypatch, capsys, files):
    calls = []
    monkeypatch.setattr(main_module.sys, "argv", ["subtitlechecker", *files])
    monkeypatch.setattr(main_module, "main", lambda video, subtitle: calls.append((video, subtitle)))

    cli()

    assert calls == [files]
    assert "Finished in 0m 00s." in capsys.readouterr().out

def test_main_writes_comparison(monkeypatch, capsys, tmp_path, files):
    def create_clips(video_file, clips, clip_dir):
        for i, seg in enumerate(clips, start=1):
            seg.audio_clip = fileobject(f"{clip_dir}/clip_{i:02}.wav")
    # Each word is heard 0.2s after its subtitle
    heard = [whisper_word(f" {w}", 1.2 + i * 0.3) for i, w in enumerate(["One", "two", "three", "four", "five"])]
    monkeypatch.setattr(get_clips, "calculate_clip_times", lambda video_file: [segment("00:00:00.000")])
    monkeypatch.setattr(get_clips, "create_clips", create_clips)
    monkeypatch.setattr(transcribe, "transcribe",
                        lambda clip: ([whisper_segment(" One two three four five", 1.2, 3.0, heard)], whisper_info()))

    main_module.main(*files)

    saved = json.loads((tmp_path / "movie.comparison.json").read_text(encoding="utf-8"))
    assert len(saved["segments"]) == 1
    assert saved["segments"][0]["segment_start_timestamp"] == "00:00:00.000"
    assert saved["summary"]["total_subtitle_word_count"] == 5
    assert saved["summary"]["weighted_average_percent_matched"] == 1.0
    assert saved["summary"]["average_segment_offset"] == pytest.approx(0.2)
    out = capsys.readouterr().out
    assert "Video: movie.mkv | Subtitle: movie.srt" in out
    assert "Overall conclusion:" in out and "in sync" in out
    assert "movie.comparison.json" in out
