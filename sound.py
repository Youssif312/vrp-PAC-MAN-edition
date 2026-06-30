import os
import sys
import random
import pygame

from constants import SOUND_NAMES

_SR = 22050
_MIXER_READY = False

try:
    pygame.mixer.pre_init(_SR, -16, 1, 1024)
    pygame.mixer.init(_SR, -16, 1, 1024)
    _MIXER_READY = True
except Exception as _e:
    print(f"[sound] mixer init failed: {_e}")

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

_SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


class SoundManager:
    def __init__(self):
        self._sounds  = {}
        self._enabled = _MIXER_READY
        if not _MIXER_READY:
            return
        for name in SOUND_NAMES:
            snd = self._try_load_file(name) or self._synth_fallback(name)
            if snd is not None:
                self._sounds[name] = snd
        print(f"[sound] {len(self._sounds)}/{len(SOUND_NAMES)} sounds loaded")

    # ── File loading ───────────────────────────────────────────────────────────

    def _try_load_file(self, name):
        for ext in (".wav", ".mp3", ".ogg"):
            path = os.path.join(_SOUND_DIR, name + ext)
            if os.path.isfile(path):
                try:
                    s = pygame.mixer.Sound(path)
                    print(f"[sound] loaded {name}{ext}")
                    return s
                except Exception as e:
                    print(f"[sound] failed to load {path}: {e}")
        return None

    # ── Synthesised fallback ───────────────────────────────────────────────────

    def _synth_fallback(self, name):
        if not _HAS_NUMPY:
            return None
        try:
            def tone(freq, dur, vol=0.3, decay=8):
                n = int(_SR * dur)
                t = np.linspace(0, dur, n, endpoint=False)
                w = np.sign(np.sin(2 * np.pi * freq * t)) * np.exp(-decay * t) * vol
                return (np.clip(w, -1, 1) * 32767).astype(np.int16)

            tones = {
                "waka":     np.concatenate([tone(440, .045), tone(330, .045)]),
                "click":    tone(880, .03, decay=25),
                "depot":    np.concatenate([tone(523, .06, decay=10), tone(659, .06, decay=10)]),
                "solve":    np.concatenate([tone(200 + i * 60, .025, decay=5) for i in range(8)]),
                "victory":  np.concatenate([tone(f, .12, decay=4) for f in [523, 659, 784, 1047]]),
                "clear":    np.concatenate([tone(400 - i * 45, .04, decay=6) for i in range(7)]),
                "randomize":np.concatenate([tone(random.randint(300, 900), .018, decay=15) for _ in range(6)]),
            }
            arr = tones.get(name)
            return pygame.mixer.Sound(buffer=arr.tobytes()) if arr is not None else None
        except Exception as e:
            print(f"[sound] synth failed for {name}: {e}")
            return None

    # ── Public API ─────────────────────────────────────────────────────────────

    def play(self, name: str):
        if not self._enabled:
            return
        s = self._sounds.get(name)
        if s:
            s.play()

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        return self._enabled
