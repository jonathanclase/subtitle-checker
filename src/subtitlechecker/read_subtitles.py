from pysubs2 import SSAFile as pysub
from pysubs2.exceptions import FormatAutodetectionError, UnknownFPSError
import chardet, re
from .helper import normalize_words, clean_subtitle_text
from .fileobject import fileobject
from .text_time_index import text_time_index
from .evaluation_result import evaluation_result

def decode_subtitle(raw:bytes) -> str:
    """Decodes a subtitle file's bytes using the encoding chardet detects, or Latin-1 if it can't tell."""
    encoding = chardet.detect(raw).get('encoding') or 'latin-1'
    return raw.decode(encoding, errors='replace')

def normalize_line_endings(text:str) -> str:
    """Turns Windows (\\r\\n) and old Mac (\\r) line endings into \\n."""
    text = re.sub(r'\r+\n', '\n', text)
    return text.replace('\r', '\n')

def normalize_nones(text:str) -> str:
    """Replaces cue numbers written as "None", which some tools produce, with real numbers so .srt files parse."""
    lines = text.split('\n')
    sub_num = 1
    for i, line in enumerate(lines):
        if line.strip() == "None":
            lines[i] = str(sub_num)
            sub_num += 1
    return '\n'.join(lines)

def index_subtitle(subtitle_file:fileobject, result:evaluation_result, frames_per_sec:float) -> list:
    """Reads a subtitle file into timed words, and records the word count on result.summary.

    The file is cleaned up in memory and never modified.

    Args:
        subtitle_file (fileobject): The subtitle file to read, e.g. a .srt, .ass, .vtt, or MicroDVD .sub file
        result (evaluation_result): The result to record the subtitle word count on
        frames_per_sec (float): The video's frame rate, used for MicroDVD files that don't declare their own.
            0 if unknown

    Returns:
        list[text_time_index]: Every word in the subtitles, timed to the start of its cue

    Raises:
        ValueError: If the file isn't a recognized text subtitle format, such as an image-based VobSub .sub file
    """
    FALLBACK_FPS = 23.976

    with open(subtitle_file.path, 'rb') as f:
        sub_content = normalize_line_endings(decode_subtitle(f.read()))
    if subtitle_file.name.lower().endswith(".srt"):
        sub_content = normalize_nones(sub_content)

    try:
        subs = pysub.from_string(sub_content)
    except UnknownFPSError:
        # MicroDVD times are in frames. Only fall back to the video's rate when the file doesn't declare its own,
        # because passing fps makes pysubs2 ignore the declaration and read it as a subtitle
        subs = pysub.from_string(sub_content, fps=frames_per_sec or FALLBACK_FPS)
    except FormatAutodetectionError as e:
        if subtitle_file.name.lower().endswith(".sub"):
            raise ValueError(f"'{subtitle_file.name}' isn't a text subtitle file. It may be an image-based VobSub "
                             "file, which isn't supported") from e
        raise ValueError(f"'{subtitle_file.name}' isn't in a recognized subtitle format") from e

    subtitles = []
    for sub in subs:
        if not sub.is_text: continue
        cue_start = sub.start / 1000
        for token in clean_subtitle_text(sub.plaintext).split():
            for word in normalize_words(token):
                subtitles.append(text_time_index(cue_start, word))

    result.summary.total_subtitle_word_count = len(subtitles)
    return subtitles
