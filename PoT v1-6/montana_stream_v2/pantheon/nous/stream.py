"""
STREAM: Real-Time Thought Chronology
====================================

Each thought is a timestamp with microsecond precision.
Not batch. Not post-hoc. Stream.

"Thinking happens IN time, not AFTER."

"""

import time
import json
import hashlib
from pathlib import Path
from typing import Optional, TextIO
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class Pulse:
    """
    A single thought impulse.
    Minimal structure. Maximum time precision.
    """
    t: float          # Unix timestamp
    iso: str          # ISO 8601 with milliseconds
    δ: float          # Delta from previous thought (seconds)
    m: str            # Message — the thought itself
    c: Optional[str] = None  # Context — what it relates to

    def __str__(self) -> str:
        ctx = f" [{self.c}]" if self.c else ""
        return f"{self.iso} +{self.δ:.3f}s{ctx}: {self.m}"

    def to_line(self) -> str:
        """Compact string for logging"""
        return json.dumps({
            "iso": self.iso,
            "δ_ms": round(self.δ * 1000, 2),
            "ctx": self.c,
            "thought": self.m
        }, ensure_ascii=False)


class ThoughtStream:
    """
    Real-time thought stream.

    Each pulse() call captures:
    - Exact time (microseconds)
    - Delta from previous thought
    - The thought itself

    Writing happens immediately, no buffering.
    """

    def __init__(self, stream_id: str, output_dir: Path):
        self.stream_id = stream_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = output_dir / f"{stream_id}.jsonl"
        self.md_path = output_dir / f"{stream_id}.md"

        self._last_t: float = 0
        self._count: int = 0
        self._start_t: float = 0
        self._file: Optional[TextIO] = None

    def __enter__(self):
        import datetime

        self._start_t = time.time()
        self._last_t = self._start_t
        self._file = open(self.log_path, 'a', encoding='utf-8')

        dt = datetime.datetime.fromtimestamp(self._start_t)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(dt.microsecond/1000):03d}"

        # Session header
        header = {
            "type": "session_start",
            "stream_id": self.stream_id,
            "t": self._start_t,
            "iso": iso
        }
        self._file.write(json.dumps(header, ensure_ascii=False) + "\n")
        self._file.flush()

        return self

    def __exit__(self, *args):
        if self._file:
            end_t = time.time()
            footer = {
                "type": "session_end",
                "t": end_t,
                "duration": end_t - self._start_t,
                "pulse_count": self._count
            }
            self._file.write(json.dumps(footer, ensure_ascii=False) + "\n")
            self._file.close()

        # Generate markdown after closing
        self._generate_markdown()

    def pulse(self, thought: str, context: Optional[str] = None) -> Pulse:
        """
        Record a thought NOW.

        Time is captured at the moment of call, not after.
        """
        import datetime

        now = time.time()
        δ = now - self._last_t

        # ISO 8601 with milliseconds: 2025-12-30T03:22:20.123
        dt = datetime.datetime.fromtimestamp(now)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(dt.microsecond/1000):03d}"

        p = Pulse(
            t=now,
            iso=iso,
            δ=δ,
            m=thought,
            c=context
        )

        if self._file:
            self._file.write(p.to_line() + "\n")
            self._file.flush()  # Immediate write!

        self._last_t = now
        self._count += 1

        return p

    def p(self, thought: str, context: Optional[str] = None) -> Pulse:
        """Short alias for pulse()"""
        return self.pulse(thought, context)

    def _generate_markdown(self):
        """Convert JSONL to readable Markdown"""
        if not self.log_path.exists():
            return

        lines = []

        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                except:
                    continue

                if data.get("type") == "session_start":
                    lines.append(f"# Thought Stream: {data.get('stream_id')}")
                    lines.append("")
                    lines.append(f"Started: {data.get('iso')}")
                    lines.append("")

                elif data.get("type") == "session_end":
                    lines.append("")
                    lines.append(f"---")
                    lines.append(f"Duration: {data.get('duration', 0):.3f}s | Thoughts: {data.get('pulse_count', 0)}")

                elif "thought" in data:
                    iso = data.get('iso', '')
                    δ_ms = data.get('δ_ms', 0)
                    ctx = data.get('ctx') or ''
                    thought = data.get('thought', '')

                    # Format: [time] +Δms [context] thought
                    ctx_str = f"[{ctx}] " if ctx else ""
                    lines.append(f"`{iso}` +{δ_ms:.1f}ms {ctx_str}{thought}")

        self.md_path.write_text("\n".join(lines), encoding='utf-8')


@contextmanager
def stream(stream_id: str, output_dir: Path = Path("./thought_streams")):
    """
    Context manager for convenient usage.

    Example:
        with stream("montana_review") as s:
            s.p("Opening whitepaper")
            s.p("Reading abstract", "S0")
            s.p("Time as resource — interesting", "S1")
            ...
    """
    ts = ThoughtStream(stream_id, output_dir)
    with ts:
        yield ts
