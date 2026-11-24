# For You — a 3D apology

A short real-time 3D animation in Python, in blue, silver and gold, with music playing
behind it. It opens on a locked padlock. Typing the password unlocks it: the shackle
lifts and swings open, and the lock breaks into thousands of particles of light. The
particles then form a series of scenes while the apology plays out on screen:

sphere → orbits → scattered dust → heart → heart breaking → *"I'm sorry."* written in gold →
the heart mended with gold (kintsugi) → **NO GAMES ANYMORE.** → a final heart with an orbiting gold ring.

Running time is about two minutes. The last scene stays on screen until the window is closed.

**Password:** `nogamesanymore` (no spaces, any capitalisation)

---

## Run it in PyCharm

1. **File → Open…** and choose this folder.
2. Set a Python interpreter (3.9 or newer): **Settings → Project → Python Interpreter → Add Interpreter → Virtualenv**.
3. Open `requirements.txt` and click **Install requirements** when PyCharm offers it,
   or run this in PyCharm's terminal:
   ```
   pip install -r requirements.txt
   ```
4. Pick the **Apology** run configuration in the top-right corner and press ▶.
   You can also right-click `main.py` and choose **Run 'main'**.

## Add "About You" by The 1975

The song is copyrighted, so it isn't included here. Put your own copy (mp3/ogg/wav/flac) in
`assets/music/`. Any file name containing "about you" or "1975" is picked up automatically,
and its title shows briefly in the corner after the lock opens.

Until you add it, the program plays the piano track already in this folder. If there is no
audio file at all, it plays a soft pad it generates itself. Music always plays.

## Controls

| Key | What it does |
| --- | --- |
| Type + **Enter** | Unlock |
| **F11** | Fullscreen (recommended) |
| **M** | Mute / unmute |
| **→** | Next scene |
| **R** | Watch again (after the end) |
| **Esc** | Quit |

## Make it yours

Edit `apology/config.py` to change:
- the password, the title and the hint (the hint appears after two wrong tries)
- `FRIEND_NAME` and `SIGNATURE` (both shown on the last frame)
- colours, resolution and the number of particles

Edit `apology/story.py` to change the text of each scene and how long each one lasts.

## How it's built

- `apology/lock.py`: a padlock built entirely in code (a rounded-box body and a tube-swept shackle),
  rendered by a small software rasteriser. It has image-based metal shading (studio
  reflections, specular highlights, Fresnel rim) and is supersampled 2× for smooth edges.
- `apology/particles.py`: a particle system driven by springs that morphs between 3D shapes (heart
  surfaces, sampled text, kintsugi seam, orbiting halo), drawn with additive glow sprites.
- `apology/text.py`: captions fade in with a soft focus pull. Fonts are Cinzel and Cormorant Garamond
  (SIL Open Font License, in `assets/fonts/`).
- `apology/audio.py`: finds the music file, fades the volume in and out, and generates the backup pad.
- `apology/app.py`: the lock screen, the unlock sequence, the scene timeline, the letterbox bars and the vignette.
