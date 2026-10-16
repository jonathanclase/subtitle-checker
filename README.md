# Subtitle Checker

Evaluates the match between a video file and one or more subtitles (`.srt` files) using sampling and [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Video samples are transcribed and each subtitle is compared against the transcript. For each subtitle, statistical measures are returned, including the percentage of matching words, the average offset, the standard deviation of the offset, and the overall conclusion.

---
## User Scenarios
**Director's Cut**: Mark has a set of downloaded subtitles for a theatrical cut of a film, but has a Director's cut of the film copied from a DVD. The subtitles might initially be in sync with the film's audio, but will likely fall out of sync as new scenes are played. Mark uses subtitlechecker to examine the file and sees a high match rate, but a high standard deviation. The subtitlechecker will conclude that there are significant sync issues, and that this subtitle is likely not a match.

**Mismatched Films**: Erica has a set of downloaded subtitles purportedly for the 2025 version of _Frankenstein_. Using subtitlechecker, Erica determines that the match rate of the transcribed audio is low. The subtitlechecker concludes that this is not likely a match; the checker notes that faster-whisper's transcriptions were confident, and that noise was not likely an issue. Upon further research, Erica discovers that these subtitles were actually for the 2004 version of _Frankenstein._

**Fixable Offsets**: Deepak has a set of downloaded subtitles for a film. Only one cut of the film was ever produced, and Deepak is certain that the film matches. But using the subtitlechecker, Deepak determines that the words are a match, but the speech is offset relative to the transcript. Deepak infers that the subtitles did not account for the full length of the opening credits; he uses a subtitle editor to delay the subtitles by 2.8s, per the subtitlechecker's suggestion, and finds that the film and its subtitles are now acceptably in sync.

---
## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) and its `ffprobe` component, in a location specified in your `PATH`

Whisper models are downloaded automatically the first time you run the tool, which is currently defaulted to `small.en`

---
## How it works

The video is sampled and transcribed once (steps 1-2). Steps 3-6 are then repeated for each subtitle file.

1. **Sample the audio.** A number (defaulted to five) clips of a specific duration (defaulted to 75s) are cut from the video using ffmpeg. They're spread evenly throughout the film, which buffers to try and avoid intros and credits. The first audio track with an English language metadata tag is used, if present, otherwise the first overall track is used
2. **Transcribe and index.** Each clip is transcribed with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) using the `small.en` model. Each transcript is indexed with word-level timestamps. The clips are deleted once transcribed
<br />

3. **Index subtitles.** The subtitles are indexed, with words and timestamps
4. **Match words.** The subtitle text and the transcript are normalized (case and punctuation are removed; non-verbal subtitle cues are removed, e.g. `[music]`). A `difflib` comparison is run against the indexes, and matching blocks are analyzed
5. **Analyze the match.** Statistics are compared, including the percentage of total matches, the average offset across samples, the standard deviation of sample offsets, and more
6. **Summarize.** The overall strength of the match and the degree of offset are evaluated and a narrative is prepared

   | Check | Comparison | Currently-Defined Value | 
   |---|---|---|
   | Match | Words transcribed versus words in the subtitle  ≥ MATCH_THRESHOLD | 80% |
   | Possible match | Words transcribed versus words in the subtitle ≥ POSSIBLE_MATCH_THRESHOLD | 60% |
   | In sync | Average offset < SYNC_TOLERANCE, and <br />Overall offset σ within OFFSET_STDEV_THRESHOLD | ±1s<br />±2s |
   | Confident | Average whisper probability across all segments > CONFIDENCE_THRESHOLD | 80% |
   | Quiet | The overall average of log softmax across all chunks from all segments > LOGPROB_THRESHOLD<br /> (This is a rough measure of noise) | -0.3 |

---
## Installation

#### Using `pipx` (Recommended)

```bash
pipx install git+https://github.com/jonathanclase/subtitle-checker
```

Or from a local clone:

```bash
git clone https://github.com/jonathanclase/subtitle-checker
cd subtitlechecker
pipx install .
```


**To install `pipx`:**

<table>
<th>Operating System</th><th>Run</th>
<tr><td>Windows</td><td>

```bash
py -m pip install --user pipx
pipx ensurepath
```
</td></tr>
<tr><td>macOS (with Homebrew)</td><td>

```bash
brew install pipx --user
pipx ensurepath
```
</td></tr>
<tr><td>macOS (without Homebrew)</td><td>

```bash
pip install pipx
pipx ensurepath
```
</td></tr>

<tr><td>Ubuntu/Mint/Debian</td><td>

```bash
sudo apt install pipx
pipx ensurepath
```
</td></tr>

<tr><td>Fedora/RHEL</td><td>

```bash
sudo dnf install pipx
pipx ensurepath
```
</td></tr>
</table>

*`pipx ensurepath` adds to the PATH environment variable, if necessary*

#### Using `pip`

Run:

```bash
pip install git+https://github.com/jonathanclase/subtitle-checker
```

Or from a local clone:

```bash
git clone https://github.com/jonathanclase/subtitle-checker
cd subtitlechecker
pip install .
```

#### Upgrading

Run one of the following:

```bash
pipx install --force git+https://github.com/jonathanclase/subtitle-checker
```

```bash
pip install --force-reinstall git+https://github.com/jonathanclase/subtitle-checker
```

Or from a local clone:

```bash
git clone https://github.com/jonathanclase/subtitle-checker
cd subtitlechecker
pipx install --force .
```

```bash
git clone https://github.com/jonathanclase/subtitle-checker
cd subtitlechecker
pip install --force-reinstall .
```

#### Uninstalling

Run `pipx uninstall subtitlechecker` or `pip uninstall subtitlechecker`

---
## Development

Clone the repository and install it into a virtual environment in editable mode, so code changes take effect without reinstalling:

```bash
git clone https://github.com/jonathanclase/subtitle-checker
cd SubtitleChecker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Run it with `subtitlechecker -v <video> -s <subtitle>` or `python -m subtitlechecker -v <video> -s <subtitle>` while the virtual environment is active. Repeat `-s` to compare several subtitles in one run:

```bash
python -m subtitlechecker -v "Movie (1999).mkv" -s "Movie (1999).en.srt" -s "Movie (1999).alt.en.srt"
```


## Usage

Currently:
 - Only `.srt` files are supported
 - Only English-language audio is supported

```bash
subtitlechecker -v <video> -s <subtitle> [-s <subtitle> ...]
```

| Option | Description |
|---|---|
| `-v`, `--video` | The video to check, e.g. a `.mkv` or `.mp4` file (required) |
| `-s`, `--subtitle` | A `.srt` subtitle file to check against the video. Repeat it to compare several subtitles in one run (at least one required) |
| `--verbose` | (Optional. Default *False*). Saves the full output and comparison details as `/path/to/subtitle/<subtitle name>.comparison.json`. For example, `Movie (1999).en.srt` produces `Movie (1999).en.comparison.json` |

Paths containing spaces must be quoted. Run `subtitlechecker --help` for the full list of options.

Example:

```bash
subtitlechecker -v "Movie (1999).mkv" -s "Movie (1999).en.srt" -s "Movie (1999).alt.en.srt"
```

```
Transcribing clips from Movie (1999).mkv
Subtitle: Movie (1999).en.srt
    - The subtitle matched 87.41% of the sample transcripts, which indicates a likely match of the words. The speech typically comes 2.35s after its subtitle, so the subtitles should be delayed by that much. The offsets vary by only ±0.12s between samples, indicating the shift is consistent throughout.
    - Overall conclusion: Match, out of sync by +2.35s.
Subtitle: Movie (1999).alt.en.srt
     ...

Finished in 0m 52s.
```

## Output

When the `--verbose` flag is passed, the full results and complete set of statistics for each subtitle are saved as a JSON file next to that subtitle, at `/path/to/subtitle/<subtitle name>.comparison.json`. For example, `Movie (1999).en.srt` produces `Movie (1999).en.comparison.json`. The results include:

- **`summary`**: the overall figures. These include match percentage, overall offset and its spread, transcription confidence, and noise level, along with the narrative and conclusion text.
- **`segments`**: one entry per audio clip. Each holds the clip's start time, match percentage, and offset. It also lists every matched run of words (`blocks`) and every Whisper transcription segment with its quality measures (`chunks`).


## Product Roadmap

***Goal:** To create a tool that allows for comparison of subtitles, in order to allow decisions about whether the subtitles match, can be fixed, or should be discarded in favor of new ones*

#### 🟪 ${\color{purple}\textsf{Completed}}$
- ~~Initial build~~
- ~~Add test coverage~~
- ~~Support multiple subtitle inputs against the same video~~
- ~~Add verbose flag to save/discard full results as needed~~

#### 🟩 ${\color{green}\textsf{Now}}$
- Continue testing and refining thresholds. Determine what "good," "acceptable," and "poor" comparison results should actually mean to provide the best **decision**.
   - Add minimum-word-per-clip thresholds. A scene matching 50% of two words is not informative
   - Weight segment percent matched and summary percent matched lower when noise is higher. A noisy scene with a low match percentage should be taken with a grain of salt

#### 🟦 ${\color{blue}\textsf{Next}}$
- Simplify the `summarize` logic to improve the **comparison** results
- Add support for multiple subtitle matches, e.g. musicals with repeated refrains. Currently this will falsely inflate the `offset_stdev` measure, which is used to make a **decision** about sync issues.


#### 🟧 ${\color{orange}\textsf{Later}}$
- Add support for **other types of subtitles**, using other libraries or in-memory conversions with ffmpeg.
- Add more detailed error handling for edge cases to provide better user feedback
- Review performance on other hardware profiles
- Explore support for other languages
   - Include a first pass for language detection -- don't waste time transcribing clips that the model can't handle

## License

[MIT](LICENSE)
