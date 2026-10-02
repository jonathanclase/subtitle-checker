import re, unicodedata

def normalize_words(text:str) -> list[str]:
    """Lowercases text and strips punctuation so subtitle and transcript words can be compared.

    Args:
        text (str): The text to normalize

    Returns:
        list[str]: The individual words
    """
    # NFKC turns look-alike characters into their plain forms, e.g. "…" -> "..." and full-width letters -> normal ones
    text = unicodedata.normalize("NFKC", text).lower()

    # Curly and other look-alike apostrophes become a straight one, so "I’m" matches "I'm"
    for apostrophe in "’‘ʼ`´":
        text = text.replace(apostrophe, "'")

    # Symbols that are spoken as words
    text = text.replace("&", " and ").replace("%", " percent ")

    # Dashes and slashes separate words: "well-known" -> "well known", "No--wait" -> "no wait"
    text = re.sub(r"[-‐‑‒–—―/]+", " ", text)

    # Everything else except apostrophes is removed
    text = re.sub(r"[^\w\s']", " ", text)

    words = []
    for token in text.split():
        # Apostrophes used as quote marks ('hello') are trimmed; ones inside words (don't) are kept
        token = token.strip("'")
        if token:
            words.append(token)
    return words

def clean_subtitle_text(text:str) -> str:
    """Joins a subtitle's lines and strips bracketed text such as [music] or (laughs)."""
    # Line breaks become spaces so words on either side don't merge together
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', text)
    # Collapse the leftover runs of whitespace
    return ' '.join(text.split())

def timestamp_to_seconds(timestamp:str) -> float:
    """Converts an "HH:MM:SS.mmm" timestamp to seconds.

    Args:
        timestamp (str): The timestamp to convert

    Returns:
        float: The timestamp in seconds
    """
    # .srt files use a comma before the milliseconds; float() needs a decimal point
    hours, minutes, secs = timestamp.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(secs)

def add_times(start:str, seconds:float) -> float:
    """Adds a number of seconds to a timestamp.

    Args:
        start (str): An "HH:MM:SS,mmm" timestamp, as in .srt files. "HH:MM:SS.mmm" and "HH:MM:SS" also work
        seconds (float): The seconds to add (negative to subtract)

    Returns:
        float: The total, in seconds
    """
    return timestamp_to_seconds(start) + float(seconds)
