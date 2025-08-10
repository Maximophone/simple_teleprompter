#!/usr/bin/env python3
# teleprompter.py
#
# Usage examples:
#   python teleprompter.py mytext.md
#   python teleprompter.py mytext.md --wpm 150 --height 160 --font "Segoe UI" --size 28
#   python teleprompter.py --text "Line 1\n\nLine 2" --spw 0.4
#
# Break syntax in Markdown/text:
#   Insert "[break:X]" anywhere (own paragraph or inline) to pause for X seconds.
#   Example:
#     "First part. [break:3] Second part." → shows a 3s break between parts.
#
# Keys:
#   Space/P  pause/resume       Right/Enter/Down  next paragraph
#   Left/Up  previous           +/- (or keypad)   font bigger/smaller
#   0        reset font size    T                 toggle borderless (no title bar)
#   R        restart            Esc               quit
#
# Notes:
# - Uses only the Python standard library (tkinter).
# - Window is topmost, placed at the top of the primary screen by default.
# - Time per paragraph = max(min_sec, words * seconds_per_word). You can set wpm instead.

import argparse
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog

BREAK_TOKEN_RE = re.compile(r"\[break:(\d+(?:\.\d+)?)\]", re.IGNORECASE)

def read_text(args):
    if args.text is not None:
        return args.text
    if args.file:
        with open(args.file, "r", encoding=args.encoding) as f:
            return f.read()
    # If nothing provided, prompt for a file
    path = filedialog.askopenfilename(
        title="Select Markdown/Text file",
        filetypes=[("Markdown/Text", "*.md *.markdown *.txt"), ("All files", "*.*")]
    )
    if not path:
        print("No input provided.", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding=args.encoding) as f:
        return f.read()

def split_paragraphs(md_text):
    # Normalize newlines and split on one or more blank lines
    text = md_text.replace("\r\n", "\n").replace("\r", "\n")
    # Keep paragraphs that contain any non-whitespace
    parts = [p.strip() for p in re.split(r"\n\s*\n+", text)]
    return [p for p in parts if p]

def expand_breaks(paragraphs):
    """Expand paragraphs by splitting on [break:X] tokens.

    Returns (expanded_paragraphs, duration_overrides_ms) where overrides aligns
    with expanded_paragraphs, containing an int duration in ms for breaks, or
    None for normal text paragraphs.
    """
    expanded = []
    overrides = []
    for para in paragraphs:
        last_end = 0
        had_token = False
        for match in BREAK_TOKEN_RE.finditer(para):
            had_token = True
            before = para[last_end:match.start()]
            if before and before.strip():
                expanded.append(before.strip())
                overrides.append(None)
            sec = float(match.group(1))
            expanded.append(f"Break ({sec:g} s)")
            overrides.append(int(sec * 1000))
            last_end = match.end()
        # Remainder
        rest = para[last_end:]
        if had_token:
            if rest and rest.strip():
                expanded.append(rest.strip())
                overrides.append(None)
        else:
            expanded.append(para)
            overrides.append(None)
    return expanded, overrides

class Teleprompter:
    def __init__(self, root, paragraphs, opts, duration_overrides_ms=None):
        self.root = root
        self.paragraphs = paragraphs
        self.opts = opts
        self.duration_overrides_ms = (
            list(duration_overrides_ms) if duration_overrides_ms is not None else [None] * len(paragraphs)
        )
        self.idx = 0
        self.paused = False
        self.timer_id = None
        self.borderless = bool(opts.borderless)
        self.drag_offset = (0, 0)
        self.font_family = opts.font
        self.font_size = opts.size
        self.base_size = opts.size

        # Window setup
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        width = opts.width if opts.width else max(300, int(sw * 0.96))
        height = opts.height if opts.height else 160
        x = opts.x if opts.x is not None else max(0, (sw - width) // 2)
        y = opts.y if opts.y is not None else 0

        root.title("Teleprompter")
        root.configure(bg=opts.bg)
        root.wm_attributes("-topmost", True)
        if self.borderless:
            root.overrideredirect(True)
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.minsize(300, 80)

        # UI - main text area (use Text to allow per-word highlighting)
        self.text = tk.Text(
            root,
            font=(self.font_family, self.font_size),
            fg=opts.fg,
            bg=opts.bg,
            wrap="word",
            padx=opts.pad,
            pady=opts.pad,
            borderwidth=0,
            highlightthickness=0,
        )
        self.text.pack(fill="both", expand=True)
        self.text.configure(state="disabled")
        # Tags for highlighting
        self.text.tag_configure("spoken", foreground="yellow")
        # Tag for centering the displayed paragraph
        self.text.tag_configure("align_center", justify="center")

        self.status = tk.Label(
            root,
            text="",
            font=(self.font_family, max(10, self.font_size - 10)),
            fg=opts.fg,
            bg=opts.bg,
            anchor="e",
            padx=opts.pad,
        )
        self.status.place(relx=1.0, rely=1.0, anchor="se")

        # Bindings
        root.bind("<space>", self.toggle_pause)
        root.bind("p", self.toggle_pause)
        root.bind("P", self.toggle_pause)
        for key in ("<Right>", "<Return>", "<Down>"):
            root.bind(key, self.next_manual)
        for key in ("<Left>", "<Up>"):
            root.bind(key, self.prev_manual)
        root.bind("<Escape>", lambda e: root.destroy())
        for key in ("+", "=", "<KP_Add>"):
            root.bind(key, self.font_bigger)
        for key in ("-", "_", "<KP_Subtract>"):
            root.bind(key, self.font_smaller)
        root.bind("0", self.font_reset)
        root.bind("t", self.toggle_borderless)
        root.bind("T", self.toggle_borderless)
        root.bind("r", self.restart)
        root.bind("R", self.restart)
        root.bind("<Configure>", self.on_configure)

        # Allow dragging when borderless
        root.bind("<ButtonPress-1>", self.begin_drag)
        root.bind("<B1-Motion>", self.do_drag)

        # Word highlighting state
        self.word_timer_id = None
        self.word_spans = []  # list[(start_offset, end_offset)] in chars
        self.current_word_index = -1

        # Start
        if opts.start_delay_ms > 0:
            self.set_status(f"Starting in {opts.start_delay_ms/1000:.1f}s…")
            root.after(opts.start_delay_ms, self.start_show)
        else:
            self.start_show()

    def words_in(self, s):
        # Simple word count: split on whitespace
        return len(s.split())

    def paragraph_duration_ms(self, text):
        spw = self.opts.spw
        if self.opts.wpm:
            spw = 60.0 / float(self.opts.wpm)
        dur = max(self.opts.min_sec, self.words_in(text) * spw)
        if self.opts.max_sec is not None:
            dur = min(dur, self.opts.max_sec)
        return int(dur * 1000)

    def set_status(self, msg):
        self.status.config(text=msg)

    def show_current(self, start_timer=True):
        if not self.paragraphs:
            self._set_text("(No paragraphs)")
            self.set_status("")
            return
        p = self.paragraphs[self.idx]
        self._render_paragraph(p)
        self.set_status(f"{self.idx + 1}/{len(self.paragraphs)}")
        self.cancel_timer()
        if start_timer and not self.paused:
            override = None
            if 0 <= self.idx < len(self.duration_overrides_ms):
                override = self.duration_overrides_ms[self.idx]
            total_ms = override if override is not None else self.paragraph_duration_ms(p)
            is_break = self._is_break_paragraph(p, override)
            if is_break:
                self.timer_id = self.root.after(total_ms, self.auto_next)
            else:
                # Drive the paragraph duration from the word-highlighting schedule,
                # and call auto_next immediately after the last word is highlighted.
                self._start_word_highlighting(total_ms)

    def auto_next(self):
        if self.idx < len(self.paragraphs) - 1:
            self.idx += 1
            self.show_current(start_timer=True)
        else:
            self.cancel_timer()
            self.set_status("Done")

    def next_manual(self, _evt=None):
        self.cancel_timer()
        if self.idx < len(self.paragraphs) - 1:
            self.idx += 1
        self.show_current(start_timer=not self.paused)

    def prev_manual(self, _evt=None):
        self.cancel_timer()
        if self.idx > 0:
            self.idx -= 1
        self.show_current(start_timer=not self.paused)

    def toggle_pause(self, _evt=None):
        self.paused = not self.paused
        if self.paused:
            self.cancel_timer()
            self.set_status(f"Paused {self.idx + 1}/{len(self.paragraphs)}")
        else:
            self.show_current(start_timer=True)

    def cancel_timer(self):
        if self.timer_id is not None:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None
        if self.word_timer_id is not None:
            try:
                self.root.after_cancel(self.word_timer_id)
            except Exception:
                pass
            self.word_timer_id = None

    def font_bigger(self, _evt=None):
        self.font_size = min(self.font_size + 2, 200)
        self.text.config(font=(self.font_family, self.font_size))

    def font_smaller(self, _evt=None):
        self.font_size = max(self.font_size - 2, 6)
        self.text.config(font=(self.font_family, self.font_size))

    def font_reset(self, _evt=None):
        self.font_size = self.base_size
        self.text.config(font=(self.font_family, self.font_size))

    def toggle_borderless(self, _evt=None):
        self.borderless = not self.borderless
        # On some platforms, toggling needs a brief withdraw/deiconify
        geom = self.root.geometry()
        self.root.overrideredirect(self.borderless)
        self.root.withdraw()
        self.root.after(50, lambda: (self.root.deiconify(), self.root.geometry(geom)))

    def on_configure(self, _evt):
        # Text widget wraps automatically by word; nothing needed here.
        pass

    def _set_text(self, content):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.tag_remove("spoken", "1.0", tk.END)
        self.text.tag_add("align_center", "1.0", tk.END)
        self.text.configure(state="disabled")

    def _render_paragraph(self, text):
        # Prepare text and reset word highlighting state
        self.word_spans = []
        self.current_word_index = -1
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", text)
        self.text.tag_remove("spoken", "1.0", tk.END)
        self.text.tag_add("align_center", "1.0", tk.END)
        self.text.configure(state="disabled")
        # Build word spans for non-break paragraphs
        override = self.duration_overrides_ms[self.idx] if 0 <= self.idx < len(self.duration_overrides_ms) else None
        if not self._is_break_paragraph(text, override):
            for m in re.finditer(r"\S+", text):
                self.word_spans.append((m.start(), m.end()))

    def _is_break_paragraph(self, text, override):
        # Treat generated Break paragraphs (from [break:x]) as breaks
        return (override is not None) and text.strip().lower().startswith("break (")

    def _start_word_highlighting(self, total_ms):
        if not self.word_spans:
            # No words detected; just advance after the duration to keep timing
            self.timer_id = self.root.after(max(0, int(total_ms)), self.auto_next)
            return
        words_count = len(self.word_spans)
        if total_ms <= 0:
            # No time to highlight; jump to end immediately
            self._highlight_up_to(words_count - 1)
            self.auto_next()
            return
        # Highlight first word immediately
        self._highlight_up_to(0)
        if words_count == 1:
            # Single-word paragraph: keep it highlighted for total_ms, then advance
            self.word_timer_id = self.root.after(int(total_ms), self.auto_next)
            return
        # We want the last word to remain visible for one word-interval at the end.
        # Compute integer timings that sum exactly to total_ms.
        # Split total_ms into (words_count - 1) transition intervals and a final hold interval.
        # Last hold approximates one per-word duration.
        per_word_floor = int(total_ms // words_count)
        extra = int(total_ms % words_count)
        last_hold_ms = per_word_floor + (1 if extra > 0 else 0)
        remaining_ms = int(total_ms - last_hold_ms)
        transitions = words_count - 1
        base_transition = int(remaining_ms // transitions)
        remainder_transition = int(remaining_ms % transitions)
        self._word_intervals_ms = [base_transition + (1 if i < remainder_transition else 0) for i in range(transitions)]
        self._next_interval_idx = 0

        def schedule_next():
            if self.paused:
                return
            if self._next_interval_idx >= len(self._word_intervals_ms):
                # Finished last transition; hold on the last word, then advance
                self.word_timer_id = None
                self.timer_id = self.root.after(max(1, int(last_hold_ms)), self.auto_next)
                return
            delay = self._word_intervals_ms[self._next_interval_idx]

            def tick():
                if self.paused:
                    return
                next_index = self.current_word_index + 1
                if next_index < len(self.word_spans):
                    self._highlight_up_to(next_index)
                    try:
                        start, _ = self.word_spans[next_index]
                        self.text.see(f"1.0+{start}c")
                    except Exception:
                        pass
                    self._next_interval_idx += 1
                    schedule_next()
                else:
                    # Safety: if we reached beyond, finalize
                    self.word_timer_id = None
                    self.timer_id = self.root.after(1, self.auto_next)

            self.word_timer_id = self.root.after(max(1, int(delay)), tick)

        schedule_next()

    def _highlight_up_to(self, word_index):
        if not self.word_spans:
            return
        self.current_word_index = max(0, min(word_index, len(self.word_spans) - 1))
        # Apply tag to range covering words [0, current_word_index]
        start_char = self.word_spans[0][0]
        end_char = self.word_spans[self.current_word_index][1]
        self.text.configure(state="normal")
        self.text.tag_add("spoken", f"1.0+{start_char}c", f"1.0+{end_char}c")
        self.text.configure(state="disabled")

    def begin_drag(self, evt):
        if not self.borderless:
            return
        self.drag_offset = (evt.x_root - self.root.winfo_x(), evt.y_root - self.root.winfo_y())

    def do_drag(self, evt):
        if not self.borderless:
            return
        x = evt.x_root - self.drag_offset[0]
        y = evt.y_root - self.drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def start_show(self):
        self.paused = False
        self.show_current(start_timer=True)

    def restart(self, _evt=None):
        self.cancel_timer()
        self.idx = 0
        self.paused = False
        self.show_current(start_timer=True)

def parse_args():
    ap = argparse.ArgumentParser(description="Simple teleprompter from Markdown paragraphs.")
    ap.add_argument("file", nargs="?", help="Path to Markdown/Text file")
    ap.add_argument("--text", help="Inline text (overrides --file)")
    ap.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8)")
    # Timing
    ap.add_argument("--spw", type=float, default=0.0,
                    help="Seconds per word (e.g., 0.4 ≈ 150 wpm). If 0, uses --wpm.")
    ap.add_argument("--wpm", type=float, default=150.0, help="Words per minute (default: 150)")
    ap.add_argument("--min-sec", type=float, default=2.0, help="Minimum seconds per paragraph (default: 2)")
    ap.add_argument("--max-sec", type=float, default=None, help="Optional maximum seconds per paragraph")
    ap.add_argument("--start-delay-ms", type=int, default=500, help="Delay before starting (ms, default: 500)")
    # Window / style
    ap.add_argument("--width", type=int, help="Window width in pixels (default: ~96%% of screen)")
    ap.add_argument("--height", type=int, help="Window height in pixels (default: 160)")
    ap.add_argument("--x", type=int, help="Window X position (default: centered at top)")
    ap.add_argument("--y", type=int, help="Window Y position (default: 0)")
    ap.add_argument("--font", default="Helvetica", help='Font family (default: "Helvetica")')
    ap.add_argument("--size", type=int, default=28, help="Font size (default: 28)")
    ap.add_argument("--fg", default="#ffffff", help="Text color (default: white)")
    ap.add_argument("--bg", default="#000000", help="Background color (default: black)")
    ap.add_argument("--pad", type=int, default=14, help="Padding inside window (px, default: 14)")
    ap.add_argument("--borderless", action="store_true", help="Start without title bar (drag with mouse)")
    args = ap.parse_args()
    # Resolve timing choice
    if args.spw and args.spw < 0:
        ap.error("--spw must be >= 0")
    if args.wpm and args.wpm <= 0:
        ap.error("--wpm must be > 0")
    # If spw is 0 (default), compute from wpm
    if not args.spw:
        args.spw = 60.0 / float(args.wpm)
    return args

def main():
    args = parse_args()
    # Tk must be initialized before file dialogs on some platforms
    root = tk.Tk()
    # If no file/text provided, the dialog needs a root window; hide it until we configure geometry
    root.withdraw()
    text = read_text(args)
    paras = split_paragraphs(text)
    paras, overrides = expand_breaks(paras)
    if not paras:
        print("No non-empty paragraphs found (split on blank lines).", file=sys.stderr)
        sys.exit(1)
    root.deiconify()
    Teleprompter(root, paras, args, overrides)
    root.mainloop()

if __name__ == "__main__":
    main()
