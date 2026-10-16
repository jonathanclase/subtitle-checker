import os, tempfile, time
from argparse import ArgumentParser, ArgumentTypeError
from .fileobject import fileobject
from .evaluation_result import evaluation_result, segment_evaluation_result
from . import transcribe, read_subtitles, get_clips, evaluate_match


def main(video:str, subtitles:list, verbose:bool=False) -> None:
    video = fileobject(video)
    print(f"Transcribing clips from {video.name}")

    video_length, fps = get_clips.get_video_info(video)
    clips = get_clips.calculate_clip_times(video_length)

    indexed_clips = []      # (clip start, transcript words, clip_transcription) per clip
    # The clips are only needed until they're transcribed, so they're deleted with the directory
    with tempfile.TemporaryDirectory(prefix="subtitlechecker_") as clip_dir:
        get_clips.create_clips(video, clips, clip_dir)

        for clip in clips:
            segs, info = transcribe.transcribe(clip.audio_clip)
            indexed_clips.append((clip.clip_start, *transcribe.index_transcript(clip.clip_start, segs, info)))

    for s in subtitles:
        result = evaluation_result()
        subtitle = fileobject(s)
        print(f"Subtitle: {subtitle.name}")
        # An unreadable subtitle shouldn't throw away the transcription the others still need
        try:
            subtitles_index = read_subtitles.index_subtitle(subtitle, result, fps)
        except ValueError as e:
            print(f"\t- Skipped: {e}")
            continue
        for clip_start, transcript, clip in indexed_clips:
            # A fresh segment per subtitle for compare() to fill in; the clip is shared between them
            this_segment = segment_evaluation_result(clip_start_timestamp=clip_start, clip=clip)
            evaluate_match.compare(subtitles_index, transcript, this_segment)
            result.segments.append(this_segment)

        evaluate_match.aggregate(result)
        evaluate_match.summarize(result)

        print(f"\t- {result.summary.narrative}")
        print(f"\t- Overall conclusion: {result.summary.conclusion}")

        if verbose:
            result_path = os.path.join(subtitle.directory, subtitle.stem + ".comparison.json")
            with open(result_path, "w", encoding="utf-8") as output:
                output.write(str(result))

            print(f"\t- Saved full results to {result_path}.")


def check_arg(extensions:tuple, kind="file"):
    """Builds an argparse type function that accepts only existing files with one of the given extensions.

    Args:
        extensions (tuple): The allowed extensions, lowercase and including the dot, e.g. (".srt",)
        kind (str): What the file is, used in the error message, e.g. "video"

    Returns:
        function: A checker to pass as add_argument's type
    """
    def check(s):
        """Returns path s unchanged if it's valid, otherwise raises ArgumentTypeError so argparse reports it."""
        if not os.path.isfile(s): raise ArgumentTypeError(f"File not found: {s}")
        if not s.lower().endswith(extensions): raise ArgumentTypeError(f"File {s} not recognized as a {kind} file: {extensions}")
        return s
    return check


def cli() -> None:
    """Entry point for the `subtitlechecker` command."""

    VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".ts")
    SUBTITLE_EXTENSIONS = (".srt", ".ass", ".vtt", ".sub")

    argparser = ArgumentParser()
    argparser.add_argument('-v', '--video', required=True, type=check_arg(VIDEO_EXTENSIONS, "video"), help="The video to check, e.g. a .mkv or .mp4 file (Required)")
    argparser.add_argument('-s', '--subtitle', required=True, type=check_arg(SUBTITLE_EXTENSIONS, "subtitle"), action="append", help="The subtitle file or files to check it against. (At least one required)")
    argparser.add_argument('--verbose', required=False, action="store_true", help="Save the detailed results to a .json file")

    args = argparser.parse_args()

    started = time.monotonic()
    main(args.video, args.subtitle, args.verbose)
    minutes, seconds = divmod(round(time.monotonic() - started), 60)
    print()
    print(f"Finished in {minutes}m {seconds:02}s.")


if __name__ == "__main__":
    cli()
