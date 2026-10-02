import os, sys, tempfile, time
from .fileobject import fileobject
from .evaluation_result import evaluation_result, segment_evaluation_result
from . import transcribe, read_subtitles, get_clips, evaluate_match


def main(video:str, subtitle:str) -> None:
    video = fileobject(video)
    subtitle = fileobject(subtitle)
    print(f"Video: {video.name} | Subtitle: {subtitle.name}")
    result = evaluation_result()
    subtitles = read_subtitles.index_subtitle(subtitle, result)

    clips = get_clips.calculate_clip_times(video)

    # The clips are only needed until they're transcribed, so they're deleted with the directory
    with tempfile.TemporaryDirectory(prefix="subtitlechecker_") as clip_dir:
        get_clips.create_clips(video, clips, clip_dir)

        for clip in clips:
            segs, info = transcribe.transcribe(clip.audio_clip)
            this_segment = segment_evaluation_result()
            this_segment.segment_start_timestamp = clip.clip_start
            indexed_clip_transcript = transcribe.index_transcript(clip.clip_start, segs, info, this_segment)
            evaluate_match.compare(subtitles, indexed_clip_transcript, this_segment)
            result.segments.append(this_segment)

    evaluate_match.aggregate(result)
    evaluate_match.summarize(result)

    print(f"{result.summary.narrative}")
    print()
    print(f"Overall conclusion: {result.summary.conclusion}")

    result_path = os.path.join(video.directory, video.stem + ".comparison.json")
    with open(result_path, "w", encoding="utf-8") as output:
        output.write(str(result))

    print()
    print(f"Saved full results to {result_path}.")


def validate_arguments(args:list) -> bool:
    """Checks that the arguments are an existing video file followed by an existing subtitle file.

    Prints each problem it finds, so the user knows what to fix.

    Args:
        args (list): The command-line arguments, without the script name

    Returns:
        bool: True if both files exist and have an allowed extension
    """
    VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".ts")
    SUBTITLE_EXTENSIONS = (".srt",) #TODO: Allow additional types

    if len(args) != 2:
        print(f"Expected 2 arguments, got {len(args)}.")
        return False

    valid = True
    for path, label, extensions in ((args[0], "Video", VIDEO_EXTENSIONS),
                                    (args[1], "Subtitle", SUBTITLE_EXTENSIONS)):
        if not os.path.isfile(path):
            print(f"{label} file not found: {path}")
            valid = False
        # Checked even when the file is missing, so both problems are reported at once
        if not path.lower().endswith(extensions):
            print(f"{label} file must end in {', '.join(extensions)}: {path}")
            valid = False
    return valid


def cli() -> None:
    """Entry point for the `subtitlechecker` command."""
    args = sys.argv[1:]

    if not validate_arguments(args):
        print()
        print("Usage: subtitlechecker <video> <subtitles>")
        print("  <video>      The video to check, e.g. a .mkv or .mp4 file")
        print("  <subtitles>  The .srt subtitle file to check it against")
        print("Paths containing spaces must be quoted.")
        sys.exit(1)

    started = time.monotonic()
    main(args[0], args[1])
    minutes, seconds = divmod(round(time.monotonic() - started), 60)
    print(f"Finished in {minutes}m {seconds:02}s.")


if __name__ == "__main__":
    cli()
