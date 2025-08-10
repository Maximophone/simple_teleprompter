## Simple Teleprompter (Tkinter)

A minimal, no-dependency teleprompter for Markdown or plain text. It shows one paragraph at a time, auto-advances based on your speaking speed, and highlights spoken words in real time. It also supports timed breaks inside your script via `[break:x]` markers.

### Highlights
- **Markdown-friendly**: Paragraphs are split by blank lines.
- **Auto timing**: Set words-per-minute or seconds-per-word, with optional min/max per paragraph.
- **Word highlighting**: Words are highlighted one-by-one in yellow, perfectly synced with the paragraph’s total time. The last word holds briefly before advancing.
- **Inline breaks**: Use `[break:x]` (e.g., `[break:3.5]`) to pause for x seconds between parts.
- **Window controls**: Borderless mode, adjustable font and size, resizable window.
- **Pure standard library**: Uses only `tkinter` (bundled with Python on most platforms).

## Requirements
- Python 3.8+ with `tkinter` available.
- Windows, macOS, or Linux.

## Installation
No install is necessary. Clone this repo and run the script directly.

```bash
python teleprompter.py my_script.md
```

On Windows, if you use a virtual environment:

```bash
.venv\Scripts\python.exe teleprompter.py my_script.md
```

## Usage

### Basic
```bash
python teleprompter.py path/to/file.md
```

If no `--file` or `--text` is provided, a file picker will open.

### Inline text
```bash
python teleprompter.py --text "First para.\n\nSecond para."
```

### Timing options
- **Seconds per word**: `--spw 0.4` (≈150 WPM). If `--spw` is 0, `--wpm` is used instead.
- **Words per minute**: `--wpm 150`
- **Minimum seconds per paragraph**: `--min-sec 2.0`
- **Maximum seconds per paragraph**: `--max-sec 6.0` (optional)

### Window and style options
- `--width`, `--height`, `--x`, `--y`
- `--font "Segoe UI"` (default: `Helvetica`)
- `--size 28`
- `--fg #ffffff`, `--bg #000000`
- `--pad 14`
- `--borderless` (drag window with mouse when enabled)

### All CLI options (with defaults)

```
teleprompter.py [file]
  --text TEXT                 Inline text (overrides --file)
  --encoding utf-8            File encoding
  --spw 0.0                   Seconds per word (0 → use --wpm)
  --wpm 150.0                 Words per minute
  --min-sec 2.0               Minimum seconds per paragraph
  --max-sec None              Optional maximum seconds per paragraph
  --start-delay-ms 500        Delay before starting
  --width, --height           Window size
  --x, --y                    Window position
  --font Helvetica            Font family
  --size 28                   Font size
  --fg #ffffff                Text color
  --bg #000000                Background color
  --pad 14                    Padding (px)
  --borderless                Start without title bar
```

## Word-by-word highlighting
- The current paragraph is split into words and highlighted progressively in yellow.
- The total paragraph time is divided across words so that:
  - Each transition occurs evenly.
  - The last word remains highlighted briefly (one word-interval) before moving to the next paragraph.
- Pausing stops timers; resuming restarts highlighting for the current paragraph in sync.

## Breaks with `[break:x]`
Insert `[break:x]` anywhere in your text to pause for x seconds:

```md
Opening remarks.

[break:5]

Next section starts after a 5-second pause.
```

- You can also place breaks inline: `First part. [break:2.5] Second part.`
- Break tokens are case-insensitive (e.g., `[BREAK:3]`).
- During a break, a placeholder line such as `Break (x s)` is shown and no word highlighting occurs.

## Keyboard controls
- **Space / P**: pause/resume
- **Right / Enter / Down**: next paragraph
- **Left / Up**: previous paragraph
- **+ / - / keypad +/-**: font bigger/smaller
- **0**: reset font size
- **T**: toggle borderless
- **R**: restart from beginning
- **Esc**: quit

## Tips
- Put each speaking chunk as its own paragraph (separated by a blank line). This makes timing and highlighting more natural.
- Use `--min-sec` to avoid very short flashes on tiny paragraphs (e.g., headings).
- Use `--max-sec` if you want to cap very long passages.

## Example

```md
# Welcome

Thank you all for being here today.

Our vision is simple: make great tools that stay out of your way. [break:3] Today, I will show you how.

Let’s begin.
```

Run:

```bash
python teleprompter.py welcome.md --wpm 150 --height 180 --font "Segoe UI" --size 30
```

## How it works (brief)
- The script splits input into paragraphs (blank-line delimited).
- `[break:x]` markers expand into dedicated break entries with an exact duration.
- For normal paragraphs, the time is computed from `--spw`/`--wpm` with min/max constraints.
- A `tk.Text` widget renders the paragraph; a tag advances across words at scheduled intervals that exactly sum to the paragraph duration, with a final hold on the last word.

## Development
- Entry point: `teleprompter.py`
- Pure standard library; no external dependencies.
- Tested on Windows 10. If your OS ships Python without `tkinter`, install it via your package manager.

## License
Choose a license and add it here (e.g., MIT). If omitted, all rights reserved by default.

