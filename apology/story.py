"""
The script.  Each scene is a 3D formation plus the words that appear with it.
Change the lines freely - timings are in seconds.

Caption styles: "lead", "italic", "gold", "title", "hero", "small"
"""
from . import config as C
from . import particles as P
from . import text as T

N = C.PARTICLE_COUNT


def _sorry(n):
    return P.text_shape(n, "I'm sorry.", T.font("italic", 190), width=6.4,
                        palette=(P.GOLD, P.GOLD, P.GOLD_HI), y=0.15)


# shape factory (None = keep the previous formation), duration, motion,
# captions [(lines, start, dur)]
SCENES = [
    dict(
        shape=lambda: P.sphere(N), dur=9.0, spin=0.22, stagger=1.6, sway=0.25,
        captions=[([("Before anything else —", "lead"),
                    ("this isn't an excuse. It's an apology.", "italic")], 1.6, 7.0)],
    ),
    dict(
        shape=lambda: P.rings(N), dur=9.5, spin=0.18, stagger=1.2, sway=0.2,
        captions=[([("You asked me not to.", "lead"),
                    ("You trusted me to listen.", "italic")], 1.2, 7.8)],
    ),
    dict(
        shape=lambda: P.dust(N), dur=8.0, spin=0.05, stagger=0.3, turbulence=1.6,
        stiffness=1.4, sway=0.1,
        captions=[([("And I did it anyway.", "lead")], 1.0, 6.6)],
    ),
    dict(
        shape=lambda: P.heart(N), dur=11.0, pulse=0.035, stagger=2.0, sway=0.38,
        captions=[([("It hurt someone who means the world to you —", "lead"),
                    ("and in hurting them, I hurt you too.", "italic")], 2.2, 8.4)],
    ),
    dict(
        shape=lambda: P.broken_heart(N, 0.5), dur=10.5, stagger=0.35, stiffness=6.0, sway=0.3,
        captions=[([("I can't undo it.", "lead"),
                    ("And I won't pretend it was small.", "italic")], 1.4, 8.6)],
    ),
    dict(
        shape=lambda: P.broken_heart(N, 1.15), dur=11.5, stagger=1.0, stiffness=1.6,
        turbulence=0.12, sway=0.32,
        captions=[([("I keep going back to the moment you said no,", "lead"),
                    ("and how that should have been enough.", "italic")], 1.2, 9.6)],
    ),
    dict(
        shape=lambda: _sorry(N), dur=10.5, stagger=1.4, stiffness=4.5, sway=0.16, exposure=0.62,
        captions=[([("Truly — with no “but” after it.", "italic")], 3.0, 7.0)],
    ),
    dict(
        shape=lambda: P.kintsugi_heart(N), dur=13.0, stagger=2.2, stiffness=3.2, sway=0.4,
        pulse=0.02,
        captions=[([("In Japan, broken pottery is mended with gold.", "lead"),
                    ("The cracks aren't hidden — they become part of its story.", "italic")], 2.4, 10.2)],
    ),
    dict(
        shape=None, dur=11.5, pulse=0.035, sway=0.45,
        captions=[([("I'm not asking you to forget.", "lead"),
                    ("Only for the chance to show you — slowly, in what I do.", "italic")], 0.6, 10.2)],
    ),
    dict(
        shape=lambda: P.halo_heart(N), dur=10.0, stagger=1.5, pulse=0.03, sway=0.35, orbit=0.22,
        captions=[([("NO GAMES ANYMORE.", "hero"),
                    ("That's the promise. That's the key.", "gold")], 1.6, 8.0)],
    ),
    dict(  # finale - holds until you leave
        shape=None, dur=None, pulse=0.035, sway=0.5, orbit=0.22,
        captions=[([("Take all the time you need.", "lead"),
                    ("I'll be here — and I'll be better.", "italic")], 1.0, 11.0)],
    ),
]


def finale_captions():
    caps = []
    t = 12.5
    if C.FRIEND_NAME or C.SIGNATURE:
        lines = []
        if C.FRIEND_NAME:
            lines.append((f"For {C.FRIEND_NAME},", "italic"))
        lines.append(("I'm sorry.", "gold"))
        if C.SIGNATURE:
            lines.append((C.SIGNATURE, "italic"))
        caps.append((lines, t, 1e9))
    else:
        caps.append(([("I'm sorry.", "gold")], t, 1e9))
    caps.append(([("R  —  WATCH AGAIN", "small")], t + 4.0, 1e9))
    return caps
