"""
Background music.

Order of preference:
  1. A file in assets/music/ whose name matches "About You" / "1975"
  2. Any other audio file in assets/music/
  3. Any audio file in the project root (e.g. the piano track already there)
  4. A soft ambient pad synthesised on the fly - so there is always music.
"""
import math

import numpy as np
import pygame

from . import config as C

AUDIO_EXT = {".mp3", ".ogg", ".wav", ".flac", ".opus"}
RATE = 44100


def find_track():
    def audio_files(folder):
        if not folder.exists():
            return []
        return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXT)

    in_music = audio_files(C.MUSIC_DIR)
    for p in in_music:
        name = p.stem.lower().replace("-", " ")
        if any(k in name for k in C.PREFERRED_TRACK_KEYWORDS):
            return p, True
    if in_music:
        return in_music[0], False
    in_root = audio_files(C.ROOT)
    if in_root:
        return in_root[0], False
    return None, False


def _synth_pad(seconds=32.0):
    """A warm, slow four-chord pad (D maj9 - B m9 - G maj7 - A sus)."""
    chords = [
        [146.83, 220.00, 277.18, 329.63, 369.99],   # Dmaj9
        [123.47, 185.00, 220.00, 277.18, 293.66],   # Bm9
        [98.00, 196.00, 246.94, 293.66, 369.99],    # Gmaj7
        [110.00, 164.81, 220.00, 293.66, 329.63],   # Asus
    ]
    n = int(RATE * seconds)
    t = np.arange(n) / RATE
    seg = seconds / len(chords)
    out = np.zeros((n, 2))
    for i, chord in enumerate(chords):
        centre = (i + 0.5) * seg
        # long overlapping raised-cosine envelopes, wrapping for a seamless loop
        d = (t - centre + seconds / 2) % seconds - seconds / 2
        env = np.clip(np.cos(np.clip(d / (seg * 1.05), -1, 1) * math.pi / 2), 0, 1) ** 1.5
        for j, f in enumerate(chord):
            for det, pan in ((-0.12, 0.25), (0.12, 0.75)):
                ph = 2 * math.pi * (f + det) * t + j
                w = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
                amp = 0.055 / (1 + j * 0.35)
                out[:, 0] += w * env * amp * (1 - pan)
                out[:, 1] += w * env * amp * pan
    # slow shimmer on top
    bell = np.zeros(n)
    for k, f in enumerate([739.99, 880.0, 1108.73, 987.77, 1318.51, 1108.73, 880.0, 739.99]):
        st = k * seconds / 8
        d = (t - st) % seconds
        bell += np.sin(2 * math.pi * f * t) * np.exp(-d * 1.4) * (d < 4) * 0.035
    out[:, 0] += bell * 0.6
    out[:, 1] += bell * 0.4
    # gentle tremolo / breathing
    out *= (0.85 + 0.15 * np.sin(2 * math.pi * t / 8))[:, None]
    out /= max(1e-6, np.abs(out).max()) / 0.6
    return (out * 32767).astype(np.int16)


class Music:
    def __init__(self):
        self.ok = True
        self.kind = None
        self.path = None
        self.is_about_you = False
        self.volume = 0.0
        self.target = 0.0
        self.muted = False
        self.sound = None
        self.channel = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 1024)
        except pygame.error as e:
            print(f"[music] audio unavailable: {e}")
            self.ok = False
            return
        path, is_ay = find_track()
        if path is not None:
            try:
                pygame.mixer.music.load(str(path))
                self.kind, self.path, self.is_about_you = "stream", path, is_ay
                print(f"[music] playing: {path.name}")
                if not is_ay:
                    print("[music] tip: put your copy of 'About You' (The 1975) in assets/music/ "
                          "and it will be used automatically.")
            except pygame.error as e:
                print(f"[music] could not load {path.name}: {e}")
        if self.kind is None:
            print("[music] no audio file found - using the built-in ambient pad.")
            arr = _synth_pad()
            if pygame.mixer.get_init()[2] == 1:
                arr = arr.mean(axis=1).astype(np.int16)
            self.sound = pygame.sndarray.make_sound(arr)
            self.kind = "synth"

    def play(self, volume):
        if not self.ok:
            return
        self.target = volume
        if self.kind == "stream":
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(loops=-1, fade_ms=2500)
        else:
            self.sound.set_volume(0.0)
            self.channel = self.sound.play(loops=-1, fade_ms=2500)

    def fade_to(self, volume):
        self.target = volume

    def toggle_mute(self):
        self.muted = not self.muted

    def update(self, dt):
        if not self.ok:
            return
        goal = 0.0 if self.muted else self.target
        self.volume += (goal - self.volume) * min(1.0, dt * 0.9)
        if self.kind == "stream":
            pygame.mixer.music.set_volume(self.volume)
        elif self.sound is not None:
            self.sound.set_volume(self.volume)
