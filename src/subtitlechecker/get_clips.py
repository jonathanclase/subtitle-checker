import subprocess, json, os
from .fileobject import fileobject
from .segment import segment

CLIP_DURATION = 75.0
CLIP_COUNT = 5

def calculate_clip_times(video_file:fileobject, clip_count:int=CLIP_COUNT) -> list[segment]:
    """Spreads the clips evenly across the video and sets each one's `clip_start`.

    Every clip starts at least EDGE_MARGIN_S seconds in, and ends at least EDGE_MARGIN_S seconds
    before the end of the video. The first and last clips sit at those limits.

    Args:
        video_file (fileobject): The video file to probe
        clip_count (int): The number of clips for which to calculate timestamps, at least two

    Returns:
        list[segment]: A list of segments, with the start time of each populated

    Raises:
        ValueError: If clip_count is less than two, or the video is too short to fit a clip between the margins
        subprocess.CalledProcessError: If ffprobe fails
    """
    EDGE_MARGIN_S = 300.0

    # The first and last clips sit at the margins, so there must be at least two
    if clip_count < 2:
        raise ValueError(f"The number of clips must be at least two, got {clip_count}")

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", video_file.path],
        capture_output=True, text=True, check=True)
    video_length = float(json.loads(result.stdout)["format"]["duration"])

    first_start = EDGE_MARGIN_S
    last_start = video_length - EDGE_MARGIN_S - CLIP_DURATION
    if last_start < first_start:
        raise ValueError(f"'{video_file.path}' is {video_length:.0f}s long, too short for {CLIP_DURATION:.0f}s clips "
                         f"{EDGE_MARGIN_S:.0f}s from each end")

    step = (last_start - first_start) / (clip_count - 1)

    clips = []
    for i in range(clip_count):
        start = first_start + i * step
        # "HH:MM:SS.mmm", the format create_clips() hands to ffmpeg
        hours, remainder = divmod(round(start * 1000), 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, ms = divmod(remainder, 1000)
        clips.append(segment(f"{hours:02}:{minutes:02}:{seconds:02}.{ms:03}"))

    return clips


def find_audio_stream(video_file:fileobject) -> int:
    """Finds the stream index of the first English audio track, or the first audio track if none is tagged English.

    Args:
        video_file (fileobject): The video file to probe

    Returns:
        int: The absolute stream index, for use with `-map 0:<index>`

    Raises:
        ValueError: If the video has no audio tracks
        subprocess.CalledProcessError: If ffprobe fails
    """
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index:stream_tags=language", "-of", "json", video_file.path],
        capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No audio tracks found in '{video_file.path}'")

    for stream in streams:
        if stream.get("tags", {}).get("language") == "eng":
            return stream["index"]
    return streams[0]["index"]

def create_clips(video_file:fileobject, clips:list[segment], clip_dir:str, duration:float=CLIP_DURATION, audio_filter:str|None=None) -> None:
    """Cuts a mono 16 kHz .wav audio clip from the video for each segment.

    Clips are saved to clip_dir as "<video stem>_clip_01.wav", "<video stem>_clip_02.wav", etc.,
    overwriting any existing files with the same name. Each segment's `audio_clip` is set
    to its clip.

    Args:
        video_file (fileobject): The video file to cut clips from
        clips (list[segment]): The segments to clip, each starting at its clip_start
        clip_dir (str): The directory to save the clips in
        duration (float): The length of each clip, in seconds
        audio_filter (str | None): An ffmpeg audio filter to clean up the clips, such as
            "highpass=f=200,lowpass=f=3500,afftdn", or None for unfiltered audio

    Raises:
        ValueError: If the video has no audio tracks
        RuntimeError: If ffmpeg fails to create a clip
    """
    stream_index = find_audio_stream(video_file)

    for i, seg in enumerate(clips, start=1):
        clip_path = os.path.join(clip_dir, f"{video_file.stem}_clip_{i:02}.wav")

        command = ["ffmpeg", "-v", "error", "-y",
                   "-ss", seg.clip_start, "-i", video_file.path, "-t", f"{duration:.3f}",
                   "-map", f"0:{stream_index}"]
        if audio_filter:
            command += ["-af", audio_filter]
        command += ["-ac", "1", "-ar", "16000", clip_path]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on clip {i} (starting {seg.clip_start}):\n{result.stderr}")

        seg.audio_clip = fileobject(clip_path)
