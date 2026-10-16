import json, pytest
from argparse import ArgumentTypeError
from subtitlechecker import main as main_module, get_clips, transcribe
from subtitlechecker.main import check_arg, cli
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

def test_check_arg_accepts_existing_file(files):
    assert check_arg((".mkv",), "video")(files[0]) == files[0]

def test_check_arg_extension_is_case_insensitive(tmp_path):
    video = tmp_path / "MOVIE.MKV"
    video.write_bytes(b"")
    assert check_arg((".mkv",), "video")(str(video)) == str(video)

def test_check_arg_missing_file(tmp_path):
    with pytest.raises(ArgumentTypeError, match="File not found"):
        check_arg((".srt",), "subtitle")(str(tmp_path / "missing.srt"))

def test_check_arg_bad_extension(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("")
    with pytest.raises(ArgumentTypeError, match="not recognized as a video file"):
        check_arg((".mkv",), "video")(str(notes))

@pytest.mark.parametrize("flags", [[], ["-v"], ["-s"]])
def test_cli_requires_video_and_subtitle(monkeypatch, capsys, files, flags):
    # Real files, so argparse reaches the missing flag rather than rejecting a file first
    paths = {"-v": files[0], "-s": files[1]}
    args = [arg for flag in flags for arg in (flag, paths[flag])]
    monkeypatch.setattr("sys.argv", ["subtitlechecker", *args])
    monkeypatch.setattr(main_module, "main", lambda video, subtitles, verbose: pytest.fail("main should not run"))

    with pytest.raises(SystemExit) as exit_info:
        cli()

    # argparse exits with 2 on a usage error
    assert exit_info.value.code == 2
    assert "required" in capsys.readouterr().err

def test_cli_rejects_invalid_file(monkeypatch, capsys, tmp_path, files):
    monkeypatch.setattr("sys.argv", ["subtitlechecker", "-v", files[0], "-s", str(tmp_path / "missing.srt")])
    monkeypatch.setattr(main_module, "main", lambda video, subtitles, verbose: pytest.fail("main should not run"))

    with pytest.raises(SystemExit) as exit_info:
        cli()

    assert exit_info.value.code == 2
    assert "File not found" in capsys.readouterr().err

def test_cli_runs_main(monkeypatch, capsys, files):
    calls = []
    monkeypatch.setattr("sys.argv", ["subtitlechecker", "-v", files[0], "-s", files[1]])
    monkeypatch.setattr(main_module, "main", lambda video, subtitles, verbose: calls.append((video, subtitles, verbose)))

    cli()

    # Without --verbose, the full results aren't saved
    assert calls == [(files[0], [files[1]], False)]
    assert "Finished in 0m 00s." in capsys.readouterr().out

def test_cli_passes_verbose(monkeypatch, files):
    calls = []
    monkeypatch.setattr("sys.argv", ["subtitlechecker", "-v", files[0], "-s", files[1], "--verbose"])
    monkeypatch.setattr(main_module, "main", lambda video, subtitles, verbose: calls.append(verbose))

    cli()

    assert calls == [True]

def test_cli_collects_every_subtitle(monkeypatch, tmp_path, files):
    other = tmp_path / "other.srt"
    other.write_text("")
    calls = []
    monkeypatch.setattr("sys.argv", ["subtitlechecker", "-v", files[0], "-s", files[1], "-s", str(other)])
    monkeypatch.setattr(main_module, "main", lambda video, subtitles, verbose: calls.append(subtitles))

    cli()

    assert calls == [[files[1], str(other)]]

@pytest.fixture
def fake_pipeline(monkeypatch):
    """Replaces clip cutting and Whisper with one clip that hears the subtitle's five words."""
    def create_clips(video_file, clips, clip_dir):
        for i, seg in enumerate(clips, start=1):
            seg.audio_clip = fileobject(f"{clip_dir}/clip_{i:02}.wav")
    # Each word is heard 0.2s after its subtitle
    heard = [whisper_word(f" {w}", 1.2 + i * 0.3) for i, w in enumerate(["One", "two", "three", "four", "five"])]
    monkeypatch.setattr(get_clips, "calculate_clip_times", lambda video_file: [segment("00:00:00.000")])
    monkeypatch.setattr(get_clips, "create_clips", create_clips)
    monkeypatch.setattr(transcribe, "transcribe",
                        lambda clip: ([whisper_segment(" One two three four five", 1.2, 3.0, heard)], whisper_info()))

def test_main_skips_comparison_file_by_default(capsys, tmp_path, files, fake_pipeline):
    main_module.main(files[0], [files[1]])

    assert not (tmp_path / "movie.comparison.json").exists()
    out = capsys.readouterr().out
    assert "\t- Overall conclusion:" in out
    assert "Saved full results" not in out

def test_main_writes_comparison_when_verbose(capsys, tmp_path, files, fake_pipeline):
    main_module.main(files[0], [files[1]], verbose=True)

    saved = json.loads((tmp_path / "movie.comparison.json").read_text(encoding="utf-8"))
    assert len(saved["segments"]) == 1
    assert saved["segments"][0]["clip_start_timestamp"] == "00:00:00.000"
    assert saved["summary"]["total_subtitle_word_count"] == 5
    assert saved["summary"]["weighted_average_percent_matched"] == 1.0
    assert saved["summary"]["average_segment_offset"] == pytest.approx(0.2)
    out = capsys.readouterr().out
    assert "Transcribing clips from movie.mkv" in out
    assert "Subtitle: movie.srt" in out
    assert "\t- Overall conclusion:" in out and "in sync" in out
    assert "\t- Saved full results to" in out and "movie.comparison.json" in out
