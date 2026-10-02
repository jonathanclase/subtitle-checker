import json
from dataclasses import asdict, dataclass, field

@dataclass
class chunk():
    # Details about individual whisper transcription segments
    text:str
    start:float                             # Seconds into the video
    end:float
    duration:float                          # end - start, in seconds
    word_count:int
    avg_logprob:float                       # Whisper's average confidence; clear speech is usually above -0.3
    no_speech_prob:float                    # Whisper's estimate that the chunk isn't speech at all
    compression_ratio:float                 # Above ~2.4 means repetitive text, typical of Whisper inventing words over noise
    temperature:float                       # 0.0 unless Whisper's first attempt failed its quality checks and it retried

@dataclass
class block_match():
    text:str                                # The matching words, space-separated
    size:int                                # Number of words in the block
    transcript_timestamp:float              # Seconds into the video where the first word was heard
    subtitle_timestamp:float                # Start of the subtitle cue holding the first word, in seconds
    offset:float | None = None              # Median heard - subtitled time over the cue starts in the block; None if it has none

@dataclass
class segment_evaluation_result():
    segment_start_timestamp:str | None = None
    segment_probability:float | None = None
    segment_offset:float | None = None      # Median offset over every matched cue start
    transcript_word_count:int = 0
    matched_word_count:int = 0              # Words in blocks of at least MIN_RUN words
    percent_matched:float = 0.0             # matched_word_count / transcript_word_count, 0.0 - 1.0
    longest_block:int = 0                   # Size of the largest block, in words
    # From Whisper's info. With language="en" forced in transcribe(), these are always "en" and 1.0
    language:str | None = None
    language_probability:float | None = None
    duration:float | None = None            # Length of the clip, in seconds
    duration_after_vad:float | None = None  # Seconds left after the voice-activity filter removed non-speech
    speech_fraction:float | None = None     # duration_after_vad / duration
    # Noise indicators, taken from the chunks
    mean_avg_logprob:float | None = None    # Chunks' avg_logprob, averaged and weighted by word count
    max_no_speech_prob:float | None = None
    max_compression_ratio:float | None = None
    retried:bool = False                    # True if any chunk had temperature > 0
    blocks:list[block_match] = field(default_factory=list)
    chunks:list[chunk] = field(default_factory=list)

@dataclass
class evaluation_result_summary():
    narrative: str | None = None
    conclusion: str | None = None
    average_percent_matched:float | None = None
    weighted_average_percent_matched:float | None = None  # Matched words / transcript words, totalled over every segment
    total_subtitle_word_count:int = 0                   # Words in the whole subtitle file
    total_transcript_word_count:int = 0
    total_matched_word_count:int = 0
    max_longest_block:int = 0                           # The largest block in any segment, in words
    average_segment_offset: float | None = None
    offset_stdev:float | None = None                    # Spread of the segments' offsets, in seconds; None with fewer than two
    average_segment_probability:float | None = None     # Mean of the segments' word probabilities
    total_duration:float = 0.0                          # Seconds of audio transcribed, over every segment
    average_speech_fraction:float | None = None         # Mean of the segments' speech_fraction
    average_avg_logprob:float | None = None             # Mean of the segments' mean_avg_logprob
    max_no_speech_prob:float | None = None              # The highest no_speech_prob in any segment
    retried_segment_count:int = 0                       # Segments where Whisper retried at least one chunk

@dataclass
class evaluation_result():
    # Created up front so index_subtitle() can record the subtitle count before summarize() fills in the rest
    summary:evaluation_result_summary = field(default_factory=evaluation_result_summary)
    segments:list[segment_evaluation_result] = field(default_factory=list)

    def __str__(self):
        # asdict() converts the nested dataclasses and lists into plain dicts and lists that json can print
        return json.dumps(asdict(self), indent=2)
