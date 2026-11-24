"""
Render the whole animation to an MP4 that plays on iPhone (H.264 + AAC).

    python tools/render_video.py                 -> For_Gwen.mp4 in the project folder
    python tools/render_video.py out.mp4 --fps 30

The lock screen plays out on its own: the password is typed in (shown as dots),
the lock opens and the story runs to the final frame, then fades to black.
Needs ffmpeg on the PATH and a song in assets/music/.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from apology import config as C  # noqa: E402
from apology import story as S  # noqa: E402
from apology.audio import find_track  # noqa: E402

TYPE_START = 2.6       # seconds of lock screen before typing starts
TYPE_STEP = 0.16       # seconds per character
ENTER_PAUSE = 0.9      # pause after the last character before "Enter"
FINALE_HOLD = 21.0     # how long the final scene is shown
FADE_OUT = 3.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(ROOT / "For_Gwen.mp4"))
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    track, _ = find_track()
    if track is None:
        sys.exit("No song found in assets/music/.")

    # a video can't be replayed with a key press - drop that hint
    original = S.finale_captions
    S.finale_captions = lambda: [c for c in original() if c[0][0][1] != "small"]

    pygame.init()
    screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    from apology.app import App, STORY
    app = App(screen)

    fps = args.fps
    dt = 1.0 / fps
    pw = C.PASSWORD
    enter_at = TYPE_START + len(pw) * TYPE_STEP + ENTER_PAUSE

    silent = ROOT / ".render_tmp.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{C.WIDTH}x{C.HEIGHT}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-level", "4.1", str(silent)],
        stdin=subprocess.PIPE)

    frame = 0
    typed = 0
    entered = False
    finale_t0 = None
    end_t = None
    unlock_at = None
    black = pygame.Surface(screen.get_size())
    while True:
        t = frame * dt
        while typed < len(pw) and t >= TYPE_START + typed * TYPE_STEP:
            app.handle(pygame.event.Event(pygame.TEXTINPUT, text=pw[typed]))
            typed += 1
        if not entered and t >= enter_at:
            app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
            entered = True
            unlock_at = t
        app.update(dt)
        app.draw()
        if app.state == STORY and S.SCENES[app.scene_i]["dur"] is None and finale_t0 is None:
            finale_t0 = t
            end_t = t + FINALE_HOLD
        if end_t is not None and t > end_t - FADE_OUT:
            black.set_alpha(int(255 * min(1.0, (t - (end_t - FADE_OUT)) / FADE_OUT)))
            screen.blit(black, (0, 0))
        ff.stdin.write(pygame.image.tobytes(screen, "RGB"))
        frame += 1
        if frame % (fps * 10) == 0:
            print(f"  rendered {t:5.1f}s")
        if end_t is not None and t >= end_t:
            break
    ff.stdin.close()
    ff.wait()
    total = frame * dt

    # music: quieter on the lock screen, swelling once it opens, fading out at the end
    u = unlock_at + 2.35
    vol = f"if(lt(t,{u:.2f}),0.5,min(1,0.5+(t-{u:.2f})*0.25))"
    afilter = (f"volume='{vol}':eval=frame,afade=t=in:st=0:d=2.5,"
               f"afade=t=out:st={total - FADE_OUT - 0.5:.2f}:d={FADE_OUT + 0.5:.2f}")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(track),
         "-filter:a", afilter, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart",
         args.out], check=True)
    silent.unlink(missing_ok=True)
    print(f"Done: {args.out}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
