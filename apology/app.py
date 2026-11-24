"""
The application: lock screen -> unlock sequence -> the story.

Controls
  Enter        submit password
  Esc          quit
  F11          fullscreen on/off
  M            mute / unmute music          (after unlocking)
  Right arrow  next scene                    (after unlocking)
  R            watch again                   (after unlocking)
"""
import math
import sys

import numpy as np
import pygame

from . import config as C
from . import particles as P
from . import story as S
from . import text as T
from .audio import Music
from .lock import Padlock
from .math3d import (Camera, clamp01, ease_in_out, ease_out_back, lerp, rot_x, rot_y,
                     smoothstep)

LOCK, UNLOCKING, STORY = "lock", "unlocking", "story"
STORY_OFFSET = np.array([0.0, 0.45, 0.0])   # lifts formations above the captions
LOCK_OFFSET = np.array([0.0, -0.22, 0.0])
LOCK_SCALE = 0.66


# ================================================================ backdrop
def _radial(w, h, cx, cy, rx, ry, power=2.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return np.clip(1 - d, 0, 1) ** power


class Backdrop:
    def __init__(self, w, h):
        self.w, self.h = w, h
        k = h / 720.0
        g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        top = np.array(C.NAVY_DEEP, np.float32)
        bot = np.array(C.NAVY, np.float32)
        img = top * (1 - g) + bot * g
        img = np.broadcast_to(img, (h, w, 3)).copy()
        img += _radial(w, h, w * 0.5, h * 0.45, w * 0.55, h * 0.75, 1.8)[..., None] * np.array(C.MIDNIGHT) * 0.9
        img += _radial(w, h, w * 0.18, h * 0.2, w * 0.35, h * 0.4, 2.5)[..., None] * np.array([20, 40, 95])
        img += _radial(w, h, w * 0.85, h * 0.85, w * 0.4, h * 0.45, 2.5)[..., None] * np.array([40, 34, 20])
        rng = np.random.default_rng(5)
        img += rng.normal(0, 1.2, (h, w, 1))                     # dither: no banding
        vig = self._vignette(w, h)
        img *= vig[..., None]
        self.surface = pygame.surfarray.make_surface(np.clip(img, 0, 255).astype(np.uint8).transpose(1, 0, 2))
        v = (np.clip(vig * 1.12, 0, 1) * 255).astype(np.uint8)
        self.vignette = pygame.surfarray.make_surface(np.repeat(v.T[..., None], 3, axis=2))

        # slow drifting light clouds
        self.clouds = []
        for col, r, lvl in ((C.ROYAL_BLUE, 420, 0.16), ((30, 60, 150), 520, 0.14), (C.GOLD_DEEP, 300, 0.07)):
            r = int(r * k)
            a = _radial(2 * r, 2 * r, r, r, r, r, 2.4)
            rgb = (a[..., None] * np.array(col) * lvl).astype(np.uint8)
            self.clouds.append(pygame.surfarray.make_surface(rgb.transpose(1, 0, 2)))

    @staticmethod
    def _vignette(w, h):
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w * 0.62)) ** 2 + ((yy - h / 2) / (h * 0.68)) ** 2)
        return np.clip(1.08 - 0.55 * d ** 2.2, 0.15, 1.0)

    def draw(self, screen, now):
        screen.blit(self.surface, (0, 0))
        w, h = self.w, self.h
        for i, cl in enumerate(self.clouds):
            r = cl.get_width() / 2
            x = w * (0.5 + 0.32 * math.sin(now * 0.05 + i * 2.1)) - r
            y = h * (0.5 + 0.22 * math.cos(now * 0.04 + i * 1.3)) - r
            screen.blit(cl, (x, y), special_flags=pygame.BLEND_RGB_ADD)


# ================================================================ the app
class App:
    def __init__(self, screen):
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.k = self.H / 720.0          # UI scale, so 1080p renders sharper, not smaller
        T.SCALE = self.k
        self.cam = Camera(self.W, self.H, fov_deg=40, distance=7.0)
        self.backdrop = Backdrop(self.W, self.H)
        self.bank = P.SpriteBank()
        self.stars = P.Starfield()
        self.lock = Padlock()
        self.field = P.ParticleField()
        self.music = Music()
        self.music.play(C.LOCK_SCREEN_VOLUME)

        self.now = 0.0
        self.state = LOCK
        self.typed = ""
        self.attempts = 0
        self.shake_t = -10.0
        self.error_t = -10.0
        self.enter_t = 0.0
        self.unlock_t = 0.0
        self.letterbox = 0.0
        self.flash = 0.0
        self.fullscreen = C.START_FULLSCREEN

        # static lock screen text
        title = C.LOCK_TITLE
        self.ui_title = T.render_tracked(T.font("display", 26), title.upper(), C.SILVER, 6)
        self.ui_sub = T.font("italic", 30).render(C.LOCK_SUBTITLE, True, C.ICE_BLUE)
        self.ui_place = T.font("italic", 26).render("enter the password", True, C.SILVER_DIM)
        self.ui_enter = T.render_tracked(T.font("display", 13), "PRESS ENTER", C.SILVER_DIM, 6)
        self.ui_error = T.font("italic", 26).render("Not quite. Take your time.", True, C.ICE_BLUE)
        self.ui_hint = (T.font("italic", 24).render(f"hint: {C.LOCK_HINT}", True, C.GOLD)
                        if C.LOCK_HINT else None)
        self.track_label = None
        if self.music.is_about_you:
            self.track_label = T.render_tracked(T.font("display", 13), C.TRACK_TITLE.upper(), C.SILVER_DIM, 5)

        self.scene_i = -1
        self.scene_t0 = 0.0
        self.captions = []
        self.sway = 0.0
        self.sway_target = 0.0
        self.exposure = 1.0
        self.exposure_target = 1.0
        pygame.key.start_text_input()

    # ------------------------------------------------------------ events
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            if ev.key == pygame.K_F11:
                self.toggle_fullscreen()
                return True
        if self.state == LOCK:
            if ev.type == pygame.TEXTINPUT:
                if len(self.typed) < 32:
                    self.typed += ev.text
                    self.enter_t = self.now
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_BACKSPACE:
                    self.typed = self.typed[:-1]
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.submit()
        elif self.state == STORY and ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_m:
                self.music.toggle_mute()
            elif ev.key == pygame.K_RIGHT and S.SCENES[self.scene_i]["dur"] is not None:
                self.start_scene(self.scene_i + 1)
            elif ev.key == pygame.K_r:
                self.start_scene(0, replay=True)
        return True

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
        except pygame.error:
            pass

    def submit(self):
        guess = self.typed
        pw = C.PASSWORD
        if not C.PASSWORD_CASE_SENSITIVE:
            guess, pw = guess.lower(), pw.lower()
        if guess == pw:
            self.state = UNLOCKING
            self.unlock_t = self.now
            pygame.key.stop_text_input()
        else:
            self.attempts += 1
            self.shake_t = self.now
            self.error_t = self.now
            self.typed = ""

    # ------------------------------------------------------------ story
    def start_scene(self, i, replay=False):
        i = min(i, len(S.SCENES) - 1)
        sc = S.SCENES[i]
        self.scene_i = i
        self.scene_t0 = self.now
        if replay:
            self.field.set_shape(P.sphere(self.field.n), self.now, stagger=0.8, spin=0.2)
            self.field.burst(2.0)
        if sc["shape"] is not None:
            self.field.set_shape(sc["shape"](), self.now,
                                 stagger=sc.get("stagger", 1.2), spin=sc.get("spin", 0.0),
                                 pulse=sc.get("pulse", 0.0), turbulence=sc.get("turbulence", 0.0),
                                 stiffness=sc.get("stiffness", 4.0))
        else:
            f = self.field
            f.spin = sc.get("spin", f.spin)
            f.pulse = sc.get("pulse", f.pulse)
            f.turbulence = sc.get("turbulence", 0.0)
            f.stiffness = sc.get("stiffness", f.stiffness)
        self.field.orbit_speed = sc.get("orbit", 0.0)
        self.sway_target = sc.get("sway", 0.25)
        self.exposure_target = sc.get("exposure", 1.0)
        caps = list(sc["captions"])
        if sc["dur"] is None:
            caps += S.finale_captions()
        self.captions = []
        for lines, st, dur, *pos in caps:
            y = pos[0] if pos else (0.80 if any(sty == "hero" for _, sty in lines) else 0.83)
            self.captions.append(T.Caption(lines, st, dur, y=y, gap=4 if len(lines) > 2 else 10))

    def begin_story(self):
        M = self.lock.model(0.32, 0.22, 0.0)
        pts, cols = self.lock.sample_points(self.field.n, M, LOCK_SCALE * 1.06, LOCK_OFFSET,
                                            lift=0.5, swivel=-1.35)
        self.field.place(pts - STORY_OFFSET, cols)
        self.field.burst(3.4)
        self.state = STORY
        self.flash = 1.0
        self.music.fade_to(C.STORY_VOLUME)
        self.start_scene(0)
        # first formation gathers a little later, after the burst has bloomed
        self.field.t_change = self.now + 0.6

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.now += dt
        self.music.update(dt)
        self.stars.update(dt)
        if self.state == UNLOCKING and self.now - self.unlock_t >= 2.35:
            self.begin_story()
        if self.state == STORY:
            sc = S.SCENES[self.scene_i]
            if sc["dur"] is not None and self.now - self.scene_t0 >= sc["dur"]:
                self.start_scene(self.scene_i + 1)
            self.field.update(dt, self.now)
            self.letterbox = lerp(self.letterbox, 1.0, min(1, dt * 1.2))
        self.sway = lerp(self.sway, self.sway_target, min(1, dt * 0.5))
        self.exposure = lerp(self.exposure, self.exposure_target, min(1, dt * 0.8))
        self.flash = max(0.0, self.flash - dt * 1.4)

    # ------------------------------------------------------------ drawing
    def view_matrix(self):
        t = self.now
        return rot_y(self.sway * math.sin(t * 0.23)) @ rot_x(0.07 * math.sin(t * 0.17))

    def draw(self):
        scr = self.screen
        self.backdrop.draw(scr, self.now)
        star_view = rot_y(0.05 * math.sin(self.now * 0.05)) @ rot_x(0.03 * math.sin(self.now * 0.07))
        self.stars.draw(self.bank, scr, self.cam, self.now, star_view)

        if self.state in (LOCK, UNLOCKING):
            self.draw_lock_scene()
        else:
            self.draw_story()

        scr.blit(self.backdrop.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if self.flash > 0:
            scr.fill(tuple(int(c * self.flash ** 3 * 0.12) for c in C.GOLD_BRIGHT),
                     special_flags=pygame.BLEND_RGB_ADD)
        if self.letterbox > 0.001:
            bh = int(self.H * 0.075 * ease_in_out(self.letterbox))
            pygame.draw.rect(scr, (0, 0, 0), (0, 0, self.W, bh))
            pygame.draw.rect(scr, (0, 0, 0), (0, self.H - bh, self.W, bh))

    def draw_lock_scene(self):
        t = self.now
        W, H = self.W, self.H
        shake = math.exp(-(t - self.shake_t) * 5.0) * math.sin((t - self.shake_t) * 48.0)
        yaw = 0.42 * math.sin(t * 0.45) + 0.08
        pitch = 0.22 + 0.04 * math.sin(t * 0.31)
        roll = 0.12 * shake
        bob = 0.05 * math.sin(t * 1.1)
        lift = swivel = glow = 0.0
        scale = LOCK_SCALE
        ui_alpha = 1.0
        alpha = 255

        if self.state == UNLOCKING:
            u = t - self.unlock_t
            # settle to face the viewer
            k = smoothstep(0.0, 0.7, u)
            yaw = lerp(yaw, 0.32, k)
            pitch = lerp(pitch, 0.22, k)
            bob = lerp(bob, 0.0, k)
            lift = 0.5 * ease_out_back((u - 0.35) / 0.45, 2.2) if u > 0.35 else 0.0
            swivel = -1.35 * ease_in_out((u - 0.9) / 0.7) if u > 0.9 else 0.0
            glow = smoothstep(1.2, 2.3, u) * 0.55
            scale = LOCK_SCALE * (1 + 0.06 * smoothstep(1.4, 2.3, u))
            ui_alpha = 1 - smoothstep(0.0, 0.8, u)

        offset = LOCK_OFFSET + np.array([0.0, bob, 0.0])
        self.lock.draw(self.screen, self.cam, yaw, pitch, roll, scale, offset,
                       lift=lift, swivel=swivel, glow=glow, alpha=alpha,
                       region=int(820 * self.k))

        if ui_alpha <= 0.01:
            return
        a = int(255 * ui_alpha)
        scr = self.screen
        k = self.k

        def s(v):
            return int(round(v * k))

        for surf, y in ((self.ui_title, s(62)), (self.ui_sub, s(104))):
            surf.set_alpha(a)
            scr.blit(surf, ((W - surf.get_width()) // 2, y))

        # ornament
        cx = W // 2
        gold = tuple(int(c * ui_alpha) for c in C.GOLD)
        oy = s(150)
        pygame.draw.aaline(scr, gold, (cx - s(120), oy), (cx - s(14), oy))
        pygame.draw.aaline(scr, gold, (cx + s(14), oy), (cx + s(120), oy))
        pygame.draw.polygon(scr, gold, [(cx, oy - s(5)), (cx + s(5), oy), (cx, oy + s(5)), (cx - s(5), oy)])

        # input field
        dx = int(s(14) * math.exp(-(t - self.shake_t) * 5.0) * math.sin((t - self.shake_t) * 48.0))
        bw, bh = s(430), s(58)
        box = pygame.Rect(cx - bw // 2 + dx, int(H * 0.79) - bh // 2, bw, bh)
        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 18, 44, int(190 * ui_alpha)), panel.get_rect(), border_radius=bh // 2)
        scr.blit(panel, box.topleft)
        pulse = 0.65 + 0.35 * math.sin(t * 2.2)
        border = tuple(int(c * ui_alpha * (0.75 + 0.25 * pulse)) for c in C.GOLD)
        pygame.draw.rect(scr, border, box, width=max(2, s(2)), border_radius=bh // 2)
        inner = box.inflate(-s(8), -s(8))
        pygame.draw.rect(scr, tuple(int(c * ui_alpha * 0.35) for c in C.SILVER), inner, width=1, border_radius=inner.height // 2)

        if self.typed:
            n = len(self.typed)
            gap = s(22)
            x0 = box.centerx - (n - 1) * gap / 2
            for i in range(n):
                pygame.draw.circle(scr, tuple(int(c * ui_alpha) for c in C.GOLD_BRIGHT),
                                   (int(x0 + i * gap), box.centery), s(5))
            caret_x = int(x0 + (n - 1) * gap + s(16))
        else:
            self.ui_place.set_alpha(int(a * 0.8))
            scr.blit(self.ui_place, (box.centerx - self.ui_place.get_width() // 2,
                                     box.centery - self.ui_place.get_height() // 2 - s(2)))
            caret_x = box.centerx - self.ui_place.get_width() // 2 - s(12)
        if self.state == LOCK and ((t - self.enter_t) % 1.1) < 0.6:
            pygame.draw.line(scr, C.GOLD_BRIGHT, (caret_x, box.centery - s(14)), (caret_x, box.centery + s(14)), max(2, s(2)))

        y = box.bottom + s(20)
        self.ui_enter.set_alpha(int(a * 0.85))
        scr.blit(self.ui_enter, (cx - self.ui_enter.get_width() // 2, y))
        err_a = clamp01(1 - (t - self.error_t - 2.2) / 0.8) if t - self.error_t < 3.0 else 0
        if err_a > 0:
            self.ui_error.set_alpha(int(255 * err_a * ui_alpha))
            scr.blit(self.ui_error, (cx - self.ui_error.get_width() // 2, box.top - s(44)))
        if self.ui_hint and self.attempts >= C.SHOW_HINT_AFTER_ATTEMPTS:
            self.ui_hint.set_alpha(int(220 * ui_alpha))
            scr.blit(self.ui_hint, (cx - self.ui_hint.get_width() // 2, y + s(26)))

    def draw_story(self):
        view = self.view_matrix()
        pts = self.field.render_points(self.now, view) + STORY_OFFSET
        self.bank.draw(self.screen, self.cam, pts, self.field.col, size_scale=1.0, fade=self.exposure)
        lt = self.now - self.scene_t0
        for c in self.captions:
            c.draw(self.screen, lt)
        if self.track_label is not None:
            st = self.now - self.unlock_t
            a = smoothstep(3.0, 5.0, st) * (1 - smoothstep(12.0, 15.0, st))
            if a > 0:
                self.track_label.set_alpha(int(200 * a))
                k = self.k
                y = self.H - int(self.H * 0.075) - self.track_label.get_height() - int(14 * k)
                ly = y + self.track_label.get_height() // 2
                pygame.draw.line(self.screen, C.GOLD_DEEP, (int(36 * k), ly), (int(60 * k), ly), 1)
                self.screen.blit(self.track_label, (int(70 * k), y))


# ================================================================ main loop
def run():
    pygame.init()
    pygame.display.set_caption("For you")
    flags = pygame.SCALED
    try:
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT), flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    app = App(screen)
    if C.START_FULLSCREEN:
        pygame.display.toggle_fullscreen()
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(C.FPS) / 1000.0
        for ev in pygame.event.get():
            if not app.handle(ev):
                running = False
        app.update(min(dt, 1 / 20))
        app.draw()
        pygame.display.flip()
    pygame.quit()
    sys.exit(0)
