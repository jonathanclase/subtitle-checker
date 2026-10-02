import difflib, statistics
from .evaluation_result import evaluation_result, segment_evaluation_result, block_match

MIN_RUN = 4     # Shorter runs of matching words ("i", "the", "you") may be coincidences
def compare(subtitles:list, transcript:list, this_segment:segment_evaluation_result, min_run:int=MIN_RUN) -> None:
    """Matches a clip's transcript against the subtitles and fills in this_segment's match results."""
    sub_words = [s.text for s in subtitles]
    heard_words = [t.text for t in transcript]
    this_segment.transcript_word_count = len(heard_words)
    matcher = difflib.SequenceMatcher(a=sub_words, b=heard_words, autojunk=False)

    offsets = []
    matched = 0
    for block in matcher.get_matching_blocks():
        if block.size < min_run:
            continue
        matched += block.size
        block_offsets = []
        for k in range(block.size):
            i = block.a + k     # Position in subtitles
            j = block.b + k     # Position in transcript
            # Only a cue's first word has an exact subtitle time; the rest share it
            if i == 0 or subtitles[i].secs_timestamp != subtitles[i - 1].secs_timestamp:
                block_offsets.append(transcript[j].secs_timestamp - subtitles[i].secs_timestamp)
        offsets.extend(block_offsets)

        text = " ".join(sub_words[block.a : block.a + block.size])
        this_segment.blocks.append(block_match(
            text=text,
            size=block.size,
            transcript_timestamp=transcript[block.b].secs_timestamp,
            subtitle_timestamp=subtitles[block.a].secs_timestamp,
            offset=statistics.median(block_offsets) if block_offsets else None))
        this_segment.longest_block = max(this_segment.longest_block, block.size)

    this_segment.matched_word_count = matched
    if heard_words:
        this_segment.percent_matched = matched / len(heard_words)
    if offsets:
        this_segment.segment_offset = statistics.median(offsets)

def aggregate(result:evaluation_result) -> None:
    """Fills in result.summary from every segment in result.segments.

    Updates the existing summary rather than replacing it, so the subtitle count set by
    index_subtitle() is kept.
    """
    summary = result.summary

    percents = [s.percent_matched for s in result.segments]
    if percents:
        summary.average_percent_matched = statistics.median(percents)

    summary.total_transcript_word_count = sum(s.transcript_word_count for s in result.segments)
    summary.total_matched_word_count = sum(s.matched_word_count for s in result.segments)
    summary.max_longest_block = max((s.longest_block for s in result.segments), default=0)

    # Totalled rather than averaged, so segments with more speech count for more
    if summary.total_transcript_word_count:
        summary.weighted_average_percent_matched = summary.total_matched_word_count / summary.total_transcript_word_count

    # Segments where no matched run included a cue start have no offset, so they're left out
    offsets = [s.segment_offset for s in result.segments if s.segment_offset is not None]
    if offsets:
        summary.average_segment_offset = statistics.median(offsets)
    # How much the offsets differ from each other; stdev needs at least two to compare
    if len(offsets) >= 2:
        summary.offset_stdev = statistics.stdev(offsets)

    # Segments where Whisper heard nothing have no probability, so they're left out
    probabilities = [s.segment_probability for s in result.segments if s.segment_probability is not None]
    if probabilities:
        summary.average_segment_probability = statistics.mean(probabilities)

    summary.total_duration = sum(s.duration for s in result.segments if s.duration is not None)

    speech_fractions = [s.speech_fraction for s in result.segments if s.speech_fraction is not None]
    if speech_fractions:
        summary.average_speech_fraction = statistics.mean(speech_fractions)

    logprobs = [s.mean_avg_logprob for s in result.segments if s.mean_avg_logprob is not None]
    if logprobs:
        summary.average_avg_logprob = statistics.mean(logprobs)

    no_speech_probs = [s.max_no_speech_prob for s in result.segments if s.max_no_speech_prob is not None]
    if no_speech_probs:
        summary.max_no_speech_prob = max(no_speech_probs)

    summary.retried_segment_count = sum(1 for s in result.segments if s.retried)

def green(text) -> str:
    """Green text"""
    return f"\033[0;37;42m{text}\033[0m"

def yellow(text) -> str:
    """Yellow text for a warning"""
    return f"\033[0;30;43m{text}\033[0m"

def red(text) -> str:
    """Red text"""
    return f"\033[0;37;41m{text}\033[0m"

def summarize(result:evaluation_result) -> None:
    """Judges the aggregated results and writes result.summary's narrative and conclusion.

    Run after aggregate(). The narrative explains the evidence and the conclusion gives the verdict,
    both coloured for the terminal.
    """
    MATCH_THRESHOLD = 0.8           # Weighted words-found % at or above 80%
    POSSIBLE_MATCH_THRESHOLD = 0.6  # Yellow zone for weighted words-found % at or above 60%
    SYNC_TOLERANCE = 1.0            # Offsets within this many seconds count as in sync
    CONFIDENCE_THRESHOLD = 0.8      # Mean word probability above this means Whisper was sure of what it heard
    LOGPROB_THRESHOLD = -0.3        # Mean avg_logprob above this means noise wasn't getting in Whisper's way
    OFFSET_STDEV_THRESHOLD = 2.0    # Segment offsets spread wider than this many seconds indicate an inconsistent sync issue

    weighted_average_percent_matched = result.summary.weighted_average_percent_matched
    average_segment_offset = result.summary.average_segment_offset
    average_noise_level = result.summary.average_avg_logprob
    average_segment_probability = result.summary.average_segment_probability
    offset_stdev = result.summary.offset_stdev

    confident = average_segment_probability is not None and average_segment_probability > CONFIDENCE_THRESHOLD
    quiet = average_noise_level is not None and average_noise_level > LOGPROB_THRESHOLD

    consistent = offset_stdev is None or offset_stdev <= OFFSET_STDEV_THRESHOLD
    if offset_stdev is None:
        spread_note = ""
    else:
        spread_note = f" The offsets vary by only {green(f'±{offset_stdev:.2f}s')} between samples, indicating the shift is consistent throughout."

    narrative = []  # Every line except the conclusion, joined into result.summary.narrative at the end

    # None when Whisper heard no words at all, so there's nothing to judge by
    if weighted_average_percent_matched is None:
        result.summary.narrative = red("No speech was transcribed from the samples.")
        result.summary.conclusion = f"{yellow('Inconclusive')}. Check that the video has an audible dialogue track."
        return

    if weighted_average_percent_matched >= MATCH_THRESHOLD:
        narrative.append(f"The subtitle matched {green(f'{weighted_average_percent_matched:.2%}')} of the sample transcripts, which indicates a likely match of the words.")
        # Offset is heard time - subtitle time, so positive means the speech comes after its subtitle
        if average_segment_offset is None:
            narrative.append(f"The offset {yellow('could not be measured')}: no matched run of words included the start of a subtitle.")
            conclusion = f"{green('Match')}, sync unknown."
        elif abs(average_segment_offset) < SYNC_TOLERANCE and consistent:
            narrative.append(f"The speech typically is within {green(f'{average_segment_offset:+.2f}s')} of the subtitle timing, indicating it is likely in sync.")
            conclusion = f"{green('Match')}, in sync."
        elif not consistent:
            narrative.append(f"The speech offsets relative to the subtitles show a high standard deviation of {red(f'{offset_stdev:.2f}s')}, indicating a significant sync issue.")
            conclusion = f"{red('Significant sync issues')}. The subtitles are likely not for this version of the video."
        else:
            direction = "after" if average_segment_offset > 0 else "before"
            action = "delayed" if average_segment_offset > 0 else "brought forward"
            narrative.append(f"The speech typically comes {yellow(f'{abs(average_segment_offset):.2f}s {direction}')} its subtitle, "
                  f"so the subtitles should be {action} by that much.{spread_note}")
            conclusion = f"{yellow('Match, out of sync')} by {average_segment_offset:+.2f}s."

    elif weighted_average_percent_matched >= POSSIBLE_MATCH_THRESHOLD:
        narrative.append(f"The subtitle matched {yellow(f'{weighted_average_percent_matched:.2%}')} of the sample transcripts, which indicates a possible match of the words.")
        # Offset is heard time - subtitle time, so positive means the speech comes after its subtitle
        if average_segment_offset is None:
            narrative.append(f"The offset {yellow('could not be measured')}: no matched run of words included the start of a subtitle.")
            conclusion = f"{yellow('Likely match')}, sync unknown."
        elif abs(average_segment_offset) < SYNC_TOLERANCE and consistent:
            narrative.append(f"The speech typically is within {yellow(f'{average_segment_offset:+.2f}s')} of the subtitle timing, indicating it is likely in sync.")
            conclusion = f"{yellow('Likely match')}, in sync."
        elif not consistent:
            narrative.append(f"The speech offsets relative to the subtitles show a high standard deviation of {red(f'{offset_stdev:.2f}s')}, indicating a significant sync issue.")
            conclusion = f"{red('Significant sync issues')}. The subtitles are likely not for this version of the video."
        else:
            direction = "after" if average_segment_offset > 0 else "before"
            action = "delayed" if average_segment_offset > 0 else "brought forward"
            narrative.append(f"The speech typically comes {yellow(f'{abs(average_segment_offset):.2f}s {direction}')} its subtitle, "
                  f"so the subtitles should be {action} by that much.{spread_note}")
            conclusion = f"{yellow('Weaker match and out of sync')} by {average_segment_offset:+.2f}s."
    else:
        narrative.append(f"The subtitle matched {red(f'{weighted_average_percent_matched:.2%}')}, which indicates the subtitles are not likely a match.")
        if confident:
            narrative.append(f"The transcription confidence was {green(f'{average_segment_probability:.2%}')}, indicating high confidence in what was transcribed.")
        elif average_segment_probability is not None:
            narrative.append(f"The transcription confidence was {red(f'{average_segment_probability:.2%}')}, indicating low confidence in what was transcribed.")

        if quiet:
            narrative.append(f"The noise level of the samples was {green(f'{average_noise_level:.3}')}, indicating noise was not likely an issue.")
        elif average_noise_level is not None:
            narrative.append(f"The noise level of the samples was {red(f'{average_noise_level:.3}')}, indicating noise was likely an issue.")

        # Whisper heard the audio clearly and still didn't find the subtitles, so they're the problem
        if confident and quiet:
            conclusion = f"{red('No match')}. The subtitles are likely not for this video."
        else:
            conclusion = f"{yellow('Inconclusive')}. The audio from the clips couldn't be adequately transcribed to perform a comparison."

    result.summary.narrative = " ".join(narrative)
    result.summary.conclusion = conclusion
