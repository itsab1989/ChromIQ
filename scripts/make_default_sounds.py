#!/usr/bin/env python3
"""Generate ChromIQ's default measurement-sound pack (#131, Phase 1).

Every sound this script writes is synthesised from scratch — simple sine tones,
glides, damped resonances and filtered noise with short fades — so the pack
stays free of licensing questions and ships in the app. Users can drop their own
.wav files into a Sounds folder (Preferences → Paths) to extend or replace any
of these; the Sounds preferences dropdowns are built from whichever files are
present.

**``task-complete/applause.wav`` is NOT written here.** It is a CC0 recording of
a real crowd (see ``assets/sounds/CREDITS.md``): applause was the one sound that
resisted synthesis — hundreds of hand claps plus room acoustics — and every
generated attempt read as fireworks or static rather than clapping. This script
must never overwrite it, which is why no applause block exists below; running
the script leaves that file untouched.

Layout written under assets/sounds/:
    measurement-events/   tick, click, ding, chime, thump, bump, bell,
                          ding-hi, failure, buzz, error, alarm
    slow-down/            slowdown, slowdown-soft, slowdown-chime
    task-complete/        drumroll, trumpet, fanfare, chime-long
                          (applause is the CC0 recording — not generated)

Every file is 44.1 kHz, mono, 16-bit PCM, peak-normalised with a couple of
milliseconds of fade at each end so nothing clicks.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44_100
ROOT = Path(__file__).resolve().parents[1] / "assets" / "sounds"


# ----------------------------------------------------------------------------
# small synthesis helpers
# ----------------------------------------------------------------------------
def _t(dur: float) -> np.ndarray:
    return np.linspace(0.0, dur, int(SR * dur), endpoint=False)


def _env(n: int, attack: float = 0.005, release: float = 0.05) -> np.ndarray:
    """A simple attack/release envelope of length n samples."""
    env = np.ones(n)
    a = min(int(SR * attack), n // 2)
    r = min(int(SR * release), n - a)
    if a:
        env[:a] = np.linspace(0.0, 1.0, a)
    if r:
        env[n - r:] = np.linspace(1.0, 0.0, r)
    return env


def _sine(freq: float, dur: float, attack: float = 0.005,
          release: float = 0.05) -> np.ndarray:
    t = _t(dur)
    y = np.sin(2 * np.pi * freq * t)
    return y * _env(len(y), attack, release)


def _decay(freq: float, dur: float, tau: float,
           partials=(1.0,)) -> np.ndarray:
    """A struck-tone: exponential decay, optional inharmonic partials."""
    t = _t(dur)
    y = np.zeros_like(t)
    for i, amp in enumerate(partials, start=1):
        y += amp * np.sin(2 * np.pi * freq * i * t)
    y *= np.exp(-t / tau)
    return y * _env(len(y), 0.002, 0.01)


def _glide(f0: float, f1: float, dur: float) -> np.ndarray:
    """A pitch glide from f0 to f1 (linear in frequency)."""
    t = _t(dur)
    freq = np.linspace(f0, f1, len(t))
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * _env(len(t), 0.005, 0.06)


def _noise(dur: float, env: np.ndarray | None = None) -> np.ndarray:
    n = int(SR * dur)
    y = np.random.default_rng(7).standard_normal(n)
    return y * (env if env is not None else _env(n, 0.005, 0.05))


def _click(dur: float = 0.01, freq: float = 2200.0) -> np.ndarray:
    """A short percussive click: a fast-decaying high sine."""
    return _decay(freq, dur, tau=dur / 3)


def _lowpass(y: np.ndarray, cutoff: float) -> np.ndarray:
    """One-pole low-pass, as an FIR convolution (no SciPy needed).

    Plain white noise reads as hiss — real percussion is noise with most of its
    energy below a few hundred Hz. Rolling the top off is what turns a noise
    burst into something that sounds struck rather than static (#131, Knut).
    """
    tau = 1.0 / (2 * np.pi * max(cutoff, 1.0))
    k = np.exp(-np.arange(int(SR * tau * 6) + 1) / (tau * SR))
    return np.convolve(y, k / k.sum(), mode="full")[:len(y)]


def _bandpass(y: np.ndarray, low: float, high: float) -> np.ndarray:
    """Keep the band between *low* and *high* (difference of two low-passes)."""
    return _lowpass(y, high) - _lowpass(y, low)


def _rand(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def _stroke(dur: float, pitch: float, tone: float, seed: int) -> np.ndarray:
    """One drum stroke: a low-passed noise burst (the stick on the head) plus a
    damped sine at *pitch* (the membrane's body), decaying within *dur*."""
    t = _t(dur)
    body = np.sin(2 * np.pi * pitch * t) * np.exp(-t / (dur * 0.28))
    head = _lowpass(_rand(len(t), seed), tone) * np.exp(-t / (dur * 0.16))
    head /= max(float(np.max(np.abs(head))), 1e-9)
    return 0.55 * body + 0.75 * head


def _room(y: np.ndarray, decay: float = 0.13, wet: float = 0.34,
          seed: int = 21) -> np.ndarray:
    """Put *y* in a small room: convolve with a decaying-noise impulse response.

    Without it, a crowd of individual claps reads as firecrackers — separate
    sharp pops with silence between them. Reverberation is what fuses them into
    one continuous texture, which is what applause actually sounds like (Basti's
    ear, #131). FFT convolution so the script stays fast.
    """
    k = int(SR * decay)
    ir = _rand(k, seed) * np.exp(-np.arange(k) / (SR * decay / 3.5))
    ir[0] += 3.0                                   # the direct (dry) sound
    n = len(y) + k
    out = np.fft.irfft(np.fft.rfft(y, n) * np.fft.rfft(ir, n))[:len(y)]
    out /= max(float(np.max(np.abs(out))), 1e-9)
    dry = y / max(float(np.max(np.abs(y))), 1e-9)
    return (1.0 - wet) * dry + wet * out


def _sprinkle(hits: list[tuple[float, np.ndarray]], total: float) -> np.ndarray:
    """Place ``(start_seconds, sound)`` pairs onto one *total*-second buffer."""
    out = np.zeros(int(SR * total) + 1)
    for start, snd in hits:
        i = int(SR * start)
        j = min(i + len(snd), len(out))
        if j > i:
            out[i:j] += snd[:j - i]
    return out


def _seq(*parts: np.ndarray, gap: float = 0.0) -> np.ndarray:
    """Concatenate note arrays with an optional silent gap between them."""
    g = np.zeros(int(SR * gap))
    out: list[np.ndarray] = []
    for i, p in enumerate(parts):
        if i:
            out.append(g)
        out.append(p)
    return np.concatenate(out) if out else np.zeros(0)


def _mix(*parts: np.ndarray) -> np.ndarray:
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def _write(subdir: str, name: str, y: np.ndarray, gain: float = 0.89) -> None:
    peak = float(np.max(np.abs(y))) or 1.0
    y = (y / peak) * gain
    data = (np.clip(y, -1.0, 1.0) * 32767).astype("<i2")
    d = ROOT / subdir
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"  {subdir}/{name}.wav  ({len(data)/SR*1000:.0f} ms)")


# Just-intonation-ish note frequencies
C5, D5, E5, F5, G5, A5, B5, C6 = 523, 587, 659, 698, 784, 880, 988, 1047


def build() -> None:
    print("measurement-events:")
    _write("measurement-events", "tick", _click(0.008, 2600))
    _write("measurement-events", "click", _click(0.012, 1500))
    _write("measurement-events", "ding", _decay(1318, 0.18, 0.05))
    _write("measurement-events", "chime", _decay(1568, 0.22, 0.07, partials=(1.0, 0.3)))
    # out-of-tolerance: low, soft thud
    _write("measurement-events", "thump", _decay(92, 0.12, 0.04))
    _write("measurement-events", "bump", _decay(140, 0.14, 0.05, partials=(1.0, 0.4)))
    # strip OK: pleasant bell / rising two-note
    _write("measurement-events", "bell",
           _decay(880, 0.35, 0.12, partials=(1.0, 0.6, 0.25)))
    _write("measurement-events", "ding-hi", _decay(2093, 0.16, 0.05))
    # strip failed: descending buzz
    _write("measurement-events", "failure",
           _glide(440, 180, 0.28) * 0.9 + _glide(443, 181, 0.28) * 0.5)
    _write("measurement-events", "buzz",
           np.sign(_sine(150, 0.22)) * _env(int(SR * 0.22), 0.005, 0.08) * 0.7)
    # instrument error: harsh two-tone alarm
    _write("measurement-events", "error",
           _mix(_glide(330, 120, 0.35), np.sign(_sine(120, 0.35)) * 0.3))
    _write("measurement-events", "alarm",
           _seq(_sine(740, 0.12), _sine(590, 0.12), _sine(740, 0.12), gap=0.02))

    print("slow-down:")
    # calm, unmistakable "ease off" — gentle descending notes
    _write("slow-down", "slowdown", _seq(_decay(A5, 0.22, 0.10),
                                         _decay(F5, 0.30, 0.14), gap=0.04))
    _write("slow-down", "slowdown-soft", _glide(A5, E5, 0.5))
    _write("slow-down", "slowdown-chime",
           _seq(_decay(G5, 0.18, 0.08), _decay(E5, 0.18, 0.08),
                _decay(C5, 0.30, 0.14), gap=0.03))

    print("task-complete:")
    # drumroll: individual snare strokes, accelerating and swelling into a final
    # accented hit. Built stroke by stroke — a plain noise swell just sounded
    # like hiss (Knut, #131).
    roll_len, hits, pos, i = 1.05, [], 0.0, 0
    while pos < roll_len:
        frac = pos / roll_len
        rate = 13.0 + 26.0 * frac                 # strokes per second, speeding up
        amp = (0.30 + 0.70 * frac ** 1.4) * (1.0 if i % 2 == 0 else 0.72)
        hits.append((pos, _stroke(0.075, 190.0, 1400.0, seed=100 + i) * amp))
        pos += 1.0 / rate
        i += 1
    final = _mix(_stroke(0.45, 96.0, 900.0, seed=7) * 1.35,      # low tom accent
                 _lowpass(_rand(int(SR * 0.45), 8), 5200.0)
                 * np.exp(-_t(0.45) / 0.16) * 0.55)              # cymbal shimmer
    hits.append((roll_len, final))
    _write("task-complete", "drumroll", _sprinkle(hits, roll_len + 0.45))
    # trumpet: ascending major triad, bright
    _write("task-complete", "trumpet",
           _seq(_decay(C5, 0.18, 0.12, partials=(1.0, 0.5, 0.35, 0.2)),
                _decay(E5, 0.18, 0.12, partials=(1.0, 0.5, 0.35, 0.2)),
                _decay(G5, 0.35, 0.20, partials=(1.0, 0.5, 0.35, 0.2)), gap=0.01))
    # applause is NOT generated — task-complete/applause.wav is a CC0 recording
    # of a real crowd (assets/sounds/CREDITS.md). Two rounds of synthesis were
    # tried and rejected by ear: a noise swell sounded like static, and a crowd
    # of filtered-noise bursts sounded like fireworks. The giveaway was measuring
    # the real recording afterwards — it has MORE silence between events (17.5%)
    # and sharper peaks than the "improved" dense version (5.8%), so the fault
    # was never the arrangement but the clap timbre itself. Filtered noise is a
    # "tss"; a hand clap is an air-cavity burst with resonant modes. Leave the
    # recording alone.
    # fanfare: quick rising flourish resolving up an octave
    _write("task-complete", "fanfare",
           _seq(_decay(G5, 0.12, 0.06), _decay(C6, 0.12, 0.06),
                _decay(E5, 0.12, 0.06), _decay(G5, 0.30, 0.18),
                _decay(C6, 0.45, 0.22), gap=0.01))
    _write("task-complete", "chime-long",
           _seq(_decay(C5, 0.2, 0.12), _decay(E5, 0.2, 0.12),
                _decay(G5, 0.2, 0.12), _decay(C6, 0.5, 0.28), gap=0.02))

    print(f"\nWrote default sound pack to {ROOT}")


if __name__ == "__main__":
    build()
