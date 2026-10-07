import pytest
from subtitlechecker.evaluate_match import compare, aggregate, green, yellow, red, summarize
from subtitlechecker.evaluation_result import evaluation_result, evaluation_result_summary, segment_evaluation_result, clip_transcription, block_match
from conftest import words, strip_ansi

# Three cues of two words each, starting at 10s, 12s and 14s
SUBTITLES = words((10.0, "a"), (10.0, "b"), (12.0, "c"), (12.0, "d"), (14.0, "e"), (14.0, "f"))

def test_segments_share_clip_but_not_blocks():
    clip = clip_transcription(duration=75.0)
    first = segment_evaluation_result(clip=clip)
    second = segment_evaluation_result(clip=clip)

    # Each subtitle's segment gets its own blocks, so one subtitle's matches can't leak into another's
    first.blocks.append(block_match(text="a b c d", size=4, transcript_timestamp=10.5, subtitle_timestamp=10.0))

    assert first.clip is second.clip
    assert second.blocks == []

def test_compare_records_block_and_offsets():
    # "b" is heard far from its cue, but only a cue's first word has an exact time, so it's ignored
    transcript = words((10.5, "a"), (50.0, "b"), (13.0, "c"), (13.1, "d"), (15.5, "e"), (15.6, "f"),
                       (20.0, "noise"), (21.0, "noise"))
    this_segment = segment_evaluation_result(clip=clip_transcription())

    compare(SUBTITLES, transcript, this_segment)

    # Cue-start offsets are 0.5, 1.0 and 1.5
    assert this_segment.blocks == [block_match(text="a b c d e f", size=6, transcript_timestamp=10.5,
                                               subtitle_timestamp=10.0, offset=1.0)]
    assert this_segment.transcript_word_count == 8
    assert this_segment.matched_word_count == 6
    assert this_segment.percent_matched == pytest.approx(0.75)
    assert this_segment.longest_block == 6
    assert this_segment.segment_offset == pytest.approx(1.0)

def test_compare_ignores_runs_shorter_than_min_run():
    transcript = words((10.0, "a"), (10.1, "b"), (12.0, "c"))
    this_segment = segment_evaluation_result(clip=clip_transcription())

    compare(SUBTITLES, transcript, this_segment, min_run=4)

    assert this_segment.blocks == []
    assert this_segment.matched_word_count == 0
    assert this_segment.percent_matched == 0.0
    assert this_segment.segment_offset is None

def test_compare_block_starting_mid_cue():
    # The run starts mid-cue at "b", so its offset comes only from the cue starts "c" and "e"
    transcript = words((11.0, "b"), (12.5, "c"), (12.6, "d"), (14.5, "e"))
    this_segment = segment_evaluation_result(clip=clip_transcription())

    compare(SUBTITLES, transcript, this_segment, min_run=2)

    assert this_segment.blocks[0].offset == pytest.approx(0.5)
    assert this_segment.blocks[0].subtitle_timestamp == 10.0

def test_compare_with_empty_transcript():
    this_segment = segment_evaluation_result(clip=clip_transcription())

    compare(SUBTITLES, [], this_segment)

    assert this_segment.transcript_word_count == 0
    assert this_segment.percent_matched == 0.0
    assert this_segment.segment_offset is None

def test_aggregate():
    result = evaluation_result()
    result.summary.total_subtitle_word_count = 123
    result.segments = [
        segment_evaluation_result(clip=clip_transcription(probability=0.9, duration=75.0, speech_fraction=0.5,
                                                          mean_avg_logprob=-0.2, max_no_speech_prob=0.1, retried=False),
                                  percent_matched=1.0, transcript_word_count=10, matched_word_count=10, longest_block=10,
                                  segment_offset=1.0),
        segment_evaluation_result(clip=clip_transcription(probability=0.7, duration=75.0, speech_fraction=1.0,
                                                          mean_avg_logprob=-0.4, max_no_speech_prob=0.3, retried=True),
                                  percent_matched=0.5, transcript_word_count=30, matched_word_count=15, longest_block=5,
                                  segment_offset=3.0),
        # Whisper heard nothing, so every optional field stays None
        segment_evaluation_result(clip=clip_transcription()),
    ]

    aggregate(result)

    summary = result.summary
    assert summary.total_subtitle_word_count == 123
    assert summary.average_percent_matched == pytest.approx(0.5)
    assert summary.total_transcript_word_count == 40
    assert summary.total_matched_word_count == 25
    assert summary.weighted_average_percent_matched == pytest.approx(25 / 40)
    assert summary.max_longest_block == 10
    assert summary.average_segment_offset == pytest.approx(2.0)
    assert summary.offset_stdev == pytest.approx(2 ** 0.5)
    assert summary.average_clip_probability == pytest.approx(0.8)
    assert summary.total_duration == pytest.approx(150.0)
    assert summary.average_speech_fraction == pytest.approx(0.75)
    assert summary.average_avg_logprob == pytest.approx(-0.3)
    assert summary.max_no_speech_prob == pytest.approx(0.3)
    assert summary.retried_segment_count == 1

def test_aggregate_single_offset_has_no_stdev():
    result = evaluation_result(segments=[segment_evaluation_result(clip=clip_transcription(), segment_offset=1.5)])

    aggregate(result)

    assert result.summary.average_segment_offset == 1.5
    assert result.summary.offset_stdev is None

def test_aggregate_without_segments():
    result = evaluation_result()

    aggregate(result)

    assert result.summary == evaluation_result_summary()

@pytest.mark.parametrize("colour, code", [(green, "0;37;42"), (yellow, "0;30;43"), (red, "0;37;41")])
def test_colours(colour, code):
    assert colour("hi") == f"\033[{code}mhi\033[0m"

def summarized(weighted=None, offset=None, stdev=None, probability=None, logprob=None) -> evaluation_result_summary:
    result = evaluation_result(summary=evaluation_result_summary(
        weighted_average_percent_matched=weighted, average_segment_offset=offset, offset_stdev=stdev,
        average_clip_probability=probability, average_avg_logprob=logprob))
    summarize(result)
    return result.summary

@pytest.mark.parametrize("kwargs, conclusion, narrative", [
    # Nothing heard
    ({}, "Inconclusive. Check that the video has an audible dialogue track.", "No speech was transcribed"),
    # Match
    ({"weighted": 0.9}, "Match, sync unknown.", "could not be measured"),
    ({"weighted": 0.9, "offset": 0.5, "stdev": 0.3}, "Match, in sync.", "likely in sync"),
    ({"weighted": 0.8, "offset": 0.0}, "Match, in sync.", "likely match of the words"),
    ({"weighted": 0.9, "offset": 0.5, "stdev": 3.0}, "Significant sync issues.", "high standard deviation of 3.00s"),
    ({"weighted": 0.9, "offset": 2.0, "stdev": 0.5}, "Match, out of sync by +2.00s.", "subtitles should be delayed"),
    ({"weighted": 0.9, "offset": -2.0}, "Match, out of sync by -2.00s.", "subtitles should be brought forward"),
    ({"weighted": 0.9, "offset": 1.0}, "Match, out of sync by +1.00s.", "1.00s after"),
    # Possible match
    ({"weighted": 0.7}, "Likely match, sync unknown.", "could not be measured"),
    ({"weighted": 0.6, "offset": 0.2}, "Likely match, in sync.", "possible match of the words"),
    ({"weighted": 0.7, "offset": 0.2, "stdev": 2.5}, "Significant sync issues.", "high standard deviation"),
    ({"weighted": 0.7, "offset": 3.0, "stdev": 0.5}, "Weaker match and out of sync by +3.00s.", "vary by only ±0.50s"),
    # No match
    ({"weighted": 0.3, "probability": 0.9, "logprob": -0.1}, "No match.", "high confidence"),
    ({"weighted": 0.3, "probability": 0.5, "logprob": -0.1}, "Inconclusive.", "low confidence"),
    ({"weighted": 0.3, "probability": 0.9, "logprob": -0.5}, "Inconclusive.", "noise was likely an issue"),
    ({"weighted": 0.59}, "Inconclusive.", "not likely a match"),
])
def test_summarize(kwargs, conclusion, narrative):
    summary = summarized(**kwargs)

    assert strip_ansi(summary.conclusion).startswith(conclusion)
    assert narrative in strip_ansi(summary.narrative)
