from functools import lru_cache
from faster_whisper import WhisperModel
import ctranslate2
from .text_time_index import text_time_index
from .fileobject import fileobject
from .helper import add_times, normalize_words
from .evaluation_result import clip_transcription, chunk

def pick_device() -> tuple[str, str]:
    """Picks the GPU if CTranslate2 can see one, otherwise the CPU.

    Returns:
        tuple[str, str]: The device ("cuda" or "cpu") and the compute type suited to it
    """
    if ctranslate2.get_cuda_device_count() > 0:
        return "cuda", "float16"
    # int8 roughly halves memory use and speeds up CPU inference, with little loss in accuracy
    return "cpu", "int8"

@lru_cache(maxsize=None)
def load_model(model:str) -> WhisperModel:
    """Loads a faster-whisper model onto the best available device, once per model name.

    Later calls with the same name return the already-loaded model, so each clip doesn't reload it.

    Args:
        model (str): The faster-whisper model name, downloaded on first use

    Returns:
        WhisperModel: The loaded model
    """
    device, compute_type = pick_device()
    return WhisperModel(model, device=device, compute_type=compute_type)

def transcribe(clip:fileobject, vad_threshold:float=0.5, model:str="small.en") -> tuple:
    """Transcribes an English audio clip with word timestamps, skipping non-speech.

    Args:
        clip (fileobject): The audio clip to transcribe
        vad_threshold (float): How sure the voice-activity filter must be that audio is speech, 0.0 - 1.0
        model (str): The faster-whisper model name, downloaded on first use

    Returns:
        tuple: Whisper's list of segments, and its info about the clip
    """
    segs, info = load_model(model).transcribe(
        clip.path, language="en", word_timestamps=True,
        vad_filter=True, vad_parameters={"threshold": vad_threshold})

    # use list() to transform the generator into a usable result, such as for pickling
    return list(segs), info

def index_transcript(start:str, segs:object, info:object) -> tuple[list, clip_transcription]:
    """Turns a clip's transcript into timed words, and records Whisper's details about the clip.

    The clip_transcription holds the mean word probability, the language and duration fields from info,
    and one chunk per Whisper segment along with the noise indicators taken from them.

    Returns:
        tuple: The timed words, and the clip_transcription
    """
    prob = []
    transcript = []
    clip = clip_transcription()

    clip.language = info.language
    clip.language_probability = info.language_probability
    clip.duration = info.duration
    clip.duration_after_vad = info.duration_after_vad
    if info.duration > 0:
        clip.speech_fraction = info.duration_after_vad / info.duration

    for s in segs:
        words = s.words or []
        for word in words:
            for clean_word in normalize_words(word.word):
                transcript.append(text_time_index(add_times(start, word.start), clean_word))
            prob.append(word.probability)

        clip.chunks.append(chunk(
            text=s.text.strip(),
            start=add_times(start, s.start),
            end=add_times(start, s.end),
            duration=s.end - s.start,
            word_count=len(words),
            avg_logprob=s.avg_logprob,
            no_speech_prob=s.no_speech_prob,
            compression_ratio=s.compression_ratio,
            temperature=s.temperature))

    # a clip where Whisper heard nothing has no probabilities to average
    if prob:
        clip.probability = sum(prob)/len(prob)

    chunks = clip.chunks
    if chunks:
        # Weighted by word count, so a one-word chunk can't outweigh a long sentence
        total_words = sum(c.word_count for c in chunks)
        if total_words:
            clip.mean_avg_logprob = sum(c.avg_logprob * c.word_count for c in chunks) / total_words
        clip.max_no_speech_prob = max(c.no_speech_prob for c in chunks)
        clip.max_compression_ratio = max(c.compression_ratio for c in chunks)
        clip.retried = any(c.temperature > 0 for c in chunks)
    return transcript, clip
