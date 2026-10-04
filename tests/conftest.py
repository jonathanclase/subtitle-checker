"""Shared helpers for the tests. pytest puts this directory on sys.path, so tests can import them."""
import re, subprocess
from types import SimpleNamespace
from subtitlechecker.text_time_index import text_time_index

def words(*pairs) -> list[text_time_index]:
    """Builds timed words from (seconds, text) pairs."""
    return [text_time_index(secs, text) for secs, text in pairs]

def fake_run(stdout:str="", returncode:int=0, stderr:str="") -> subprocess.CompletedProcess:
    """A finished process, as a patched subprocess.run would return it."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

def whisper_word(word:str, start:float, probability:float=0.9) -> SimpleNamespace:
    """Stands in for a faster-whisper Word."""
    return SimpleNamespace(word=word, start=start, probability=probability)

def whisper_segment(text:str, start:float, end:float, words:list | None, avg_logprob:float=-0.2,
                    no_speech_prob:float=0.1, compression_ratio:float=1.5, temperature:float=0.0) -> SimpleNamespace:
    """Stands in for a faster-whisper Segment."""
    return SimpleNamespace(text=text, start=start, end=end, words=words, avg_logprob=avg_logprob,
                           no_speech_prob=no_speech_prob, compression_ratio=compression_ratio, temperature=temperature)

def whisper_info(duration:float=75.0, duration_after_vad:float=30.0) -> SimpleNamespace:
    """Stands in for faster-whisper's TranscriptionInfo."""
    return SimpleNamespace(language="en", language_probability=1.0,
                           duration=duration, duration_after_vad=duration_after_vad)

def strip_ansi(text:str) -> str:
    """Removes the terminal colour codes, so tests can check the plain wording."""
    return re.sub(r"\033\[[\d;]*m", "", text)
