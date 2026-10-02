import pysrt
import chardet, re
from .helper import normalize_words, clean_subtitle_text, timestamp_to_seconds
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
    """Replaces cue numbers written as "None", which some tools produce, with real numbers so pysrt can parse them."""
    lines = text.split('\n')
    sub_num = 1
    for i, line in enumerate(lines):
        if line.strip() == "None":
            lines[i] = str(sub_num)
            sub_num += 1
    return '\n'.join(lines)

def index_subtitle(subtitle_file:fileobject, result:evaluation_result) -> list:
    """Reads an .srt file into timed words, and records the word count on result.summary.

    The file is cleaned up in memory and never modified.

    Args:
        subtitle_file (fileobject): The .srt file to read
        result (evaluation_result): The result to record the subtitle word count on

    Returns:
        list[text_time_index]: Every word in the subtitles, timed to the start of its cue
    """
    with open(subtitle_file.path, 'rb') as f:
        srt_content = normalize_nones(normalize_line_endings(decode_subtitle(f.read())))
    subs = pysrt.SubRipFile.from_string(srt_content, error_handling=pysrt.SubRipFile.ERROR_PASS)

    subtitles = []
    for sub in subs:
        cue_start = timestamp_to_seconds(str(sub.start))
        for token in clean_subtitle_text(sub.text_without_tags).split():
            for word in normalize_words(token):
                subtitles.append(text_time_index(cue_start, word))

    result.summary.total_subtitle_word_count = len(subtitles)
    return subtitles
