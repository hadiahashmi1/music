"""Typography: elegant serif captions with soft glow, shadow and focus-pull fades."""
import pygame

from . import config as C
from .math3d import clamp01, ease_in_out

_FONT_FILES = {
    "display": "Cinzel.ttf",
    "serif": "CormorantGaramond.ttf",
    "italic": "CormorantGaramond-Italic.ttf",
}
_FALLBACK = {
    "display": "trajan,optima,palatinolinotype,georgia,dejavuserif",
    "serif": "garamond,baskerville,georgia,palatinolinotype,timesnewroman,dejavuserif",
    "italic": "garamond,baskerville,georgia,palatinolinotype,timesnewroman,dejavuserif",
}
_cache = {}


def font(kind, size):
    key = (kind, size)
    if key not in _cache:
        path = C.FONTS / _FONT_FILES[kind]
        f = None
        if path.exists():
            try:
                f = pygame.font.Font(str(path), size)
                if kind != "display":
                    try:                       # variable font: ask for a medium weight
                        f.set_variation_by_name("Medium")  # pygame-ce >= 2.5
                    except Exception:
                        pass
            except Exception:
                f = None
        if f is None:
            f = pygame.font.SysFont(_FALLBACK[kind], size, italic=(kind == "italic"))
        _cache[key] = f
    return _cache[key]


def render_tracked(fnt, text, color, tracking=0):
    """Render text with extra letter spacing (tracking, in pixels)."""
    if not tracking:
        return fnt.render(text, True, color)
    glyphs = [fnt.render(ch, True, color) for ch in text]
    w = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
    h = fnt.get_height()
    surf = pygame.Surface((max(1, w), h), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        surf.blit(g, (x, 0))
        x += g.get_width() + tracking
    return surf


STYLES = {
    #  name      font kind   size colour        tracking  glow colour
    "hero":   ("display", 58, C.GOLD_BRIGHT, 12, C.GOLD),
    "title":  ("display", 30, C.SILVER, 7, C.ROYAL_BLUE),
    "lead":   ("serif", 44, C.WHITE_WARM, 0, C.ROYAL_BLUE),
    "italic": ("italic", 36, C.ICE_BLUE, 0, C.ROYAL_BLUE),
    "gold":   ("italic", 38, C.GOLD_BRIGHT, 0, C.GOLD_DEEP),
    "small":  ("display", 15, C.SILVER_DIM, 6, None),
}


def blur(surf, factor=6):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


class Caption:
    """A block of styled lines that fades in with a focus pull and drifts up."""

    def __init__(self, lines, start, dur, y=0.83, fade_in=1.6, fade_out=1.2, gap=10):
        self.start, self.dur, self.y = start, dur, y
        self.fade_in, self.fade_out = fade_in, fade_out
        rendered = []
        for text, style in lines:
            kind, size, col, track, glow = STYLES[style]
            rendered.append((render_tracked(font(kind, size), text, col, track), glow))
        pad = 40
        w = max(s.get_width() for s, _ in rendered) + pad * 2
        h = sum(s.get_height() for s, _ in rendered) + gap * (len(rendered) - 1) + pad * 2
        self.sharp = pygame.Surface((w, h), pygame.SRCALPHA)
        glow_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        y = pad
        for s, glow in rendered:
            x = (w - s.get_width()) // 2
            self.sharp.blit(s, (x, y))
            if glow:
                tinted = pygame.Surface(s.get_size(), pygame.SRCALPHA)
                tinted.fill(glow + (255,))
                tinted.blit(s, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                glow_layer.blit(tinted, (x, y))
            y += s.get_height() + gap
        # shadow for legibility over bright particles
        shadow = self.sharp.copy()
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
        self.shadow = blur(shadow, 5)
        self.glow = blur(glow_layer, 7)
        self.soft = blur(self.sharp, 4)

    def alpha(self, t):
        lt = t - self.start
        if lt < 0 or lt > self.dur:
            return 0.0
        a_in = ease_in_out(lt / self.fade_in)
        a_out = ease_in_out((self.dur - lt) / self.fade_out)
        return min(a_in, a_out), lt

    def draw(self, screen, t, master=1.0):
        res = self.alpha(t)
        if not res:
            return
        a, lt = res
        a *= master
        if a <= 0.004:
            return
        focus = clamp01(lt / (self.fade_in * 1.1))
        rise = (1 - ease_in_out(lt / (self.fade_in * 1.6))) * 14
        sw, sh = screen.get_size()
        x = (sw - self.sharp.get_width()) // 2
        y = int(sh * self.y - self.sharp.get_height() / 2 + rise)
        self.shadow.set_alpha(int(200 * a))
        screen.blit(self.shadow, (x, y + 2))
        self.glow.set_alpha(int(150 * a))
        screen.blit(self.glow, (x, y))
        self.soft.set_alpha(int(255 * a * (1 - focus)))
        screen.blit(self.soft, (x, y))
        self.sharp.set_alpha(int(255 * a * (0.25 + 0.75 * focus)))
        screen.blit(self.sharp, (x, y))
