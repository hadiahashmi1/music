"""
Everything you might want to personalise lives in this file.

Edit the words, the password, or the colours here - the rest of the
project reads from it.
"""
from pathlib import Path

# --------------------------------------------------------------------------
#  Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
MUSIC_DIR = ASSETS / "music"

# --------------------------------------------------------------------------
#  The lock
# --------------------------------------------------------------------------
PASSWORD = "nogamesanymore"      # no spaces
PASSWORD_CASE_SENSITIVE = False  # "NoGamesAnymore" also opens it

LOCK_TITLE = "I owe you something."
LOCK_SUBTITLE = "It's locked. The key is a promise."
LOCK_HINT = "the promise, in one word, no spaces"   # set to "" to hide the hint
SHOW_HINT_AFTER_ATTEMPTS = 2                      # hint fades in after N wrong tries

# Optional: their name. Leave empty to keep it anonymous.
FRIEND_NAME = ""
# How you sign the last frame. Leave empty to show nothing.
SIGNATURE = ""

# --------------------------------------------------------------------------
#  Music
# --------------------------------------------------------------------------
# Drop your own copy of "About You" by The 1975 into assets/music/
# (mp3 / ogg / wav / flac). Any file whose name contains one of these words
# is picked first.
PREFERRED_TRACK_KEYWORDS = ("about you", "about_you", "aboutyou", "1975")
TRACK_TITLE = "About You  —  The 1975"
LOCK_SCREEN_VOLUME = 0.35
STORY_VOLUME = 0.85

# --------------------------------------------------------------------------
#  Display
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 60
START_FULLSCREEN = False
PARTICLE_COUNT = 2400

# --------------------------------------------------------------------------
#  Palette  (blue, silver, gold)
# --------------------------------------------------------------------------
NAVY_DEEP = (3, 7, 20)
NAVY = (8, 20, 48)
MIDNIGHT = (14, 34, 78)
ROYAL_BLUE = (52, 104, 214)
ICE_BLUE = (150, 196, 255)
SILVER = (205, 214, 228)
SILVER_DIM = (130, 142, 162)
GOLD = (232, 187, 92)
GOLD_BRIGHT = (255, 222, 150)
GOLD_DEEP = (168, 120, 44)
WHITE_WARM = (255, 246, 228)
