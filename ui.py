# ============================================================
# Slimey - UI MODULE
# ------------------------------------------------------------
# Helpers for:
# - Scaled fonts
# - Buttons & panels
# - Column/row layouts
# - Text wrapping
# - Skin preview box
# - Generic toggles / cycle selectors
# ============================================================

import pygame
import time
import math
from pygame import Rect

from config import WHITE, BLACK


# ------------------------------------------------------------
# Font helpers
# ------------------------------------------------------------

def build_fonts(ui_scale: float):
    """
    Returns a dict of pygame.font.Font objects scaled from a base size.
    Keys: "tiny", "small", "normal", "large", "title"
    """
    base_size = 16

    def f(mult):
        return max(8, int(base_size * mult * ui_scale))

    # Prefer a monospaced font for a retro look.
    font_name = "Courier New"

    return {
        "tiny":   pygame.font.SysFont(font_name, f(0.75)),
        "small":  pygame.font.SysFont(font_name, f(0.9)),
        "normal": pygame.font.SysFont(font_name, f(1.2)),
        "large":  pygame.font.SysFont(font_name, f(1.7)),
        "title":  pygame.font.SysFont(font_name, f(2.6)),
    }


# ------------------------------------------------------------
# Layout helpers
# ------------------------------------------------------------

def center_column_layout(center_x, start_y, button_w, button_h, spacing, count):
    rects = []
    y = start_y
    for _ in range(count):
        rects.append(Rect(center_x - button_w // 2, y, button_w, button_h))
        y += button_h + spacing
    return rects


def row_layout(left_x, y, button_w, button_h, spacing, count):
    rects = []
    x = left_x
    for _ in range(count):
        rects.append(Rect(x, y, button_w, button_h))
        x += button_w + spacing
    return rects


def get_hovered(rects, mouse_pos):
    """Return index of hovered rect, or None."""
    mx, my = mouse_pos
    for i, r in enumerate(rects):
        if r.collidepoint(mx, my):
            return i
    return None


# ------------------------------------------------------------
# Drawing primitives
# ------------------------------------------------------------

def draw_button(surface, rect, text, font, primary=False, hovered=False, focused=False, disabled=False):
    """
    Generic rectangular button.
    This is the one imported in slime_platformer: from ui import draw_button
    """
    if disabled:
        base = (40, 40, 40)
        border = (120, 120, 120)
        text_c = (140, 140, 140)
    else:
        base = (40, 40, 40)
        border = (200, 200, 200)
        text_c = WHITE

        if primary:
            base = (60, 90, 220)
            border = (255, 255, 255)

        if hovered:
            base = (
                min(255, base[0] + 25),
                min(255, base[1] + 25),
                min(255, base[2] + 25),
            )

    if focused and not disabled:
        # Soft pulse animation for focused buttons
        t = time.time()
        pulse = 0.5 + 0.5 * math.sin(t * 4.0)
        border = (
            min(255, int(200 + 55 * pulse)),
            min(255, int(200 + 55 * pulse)),
            min(255, int(160 + 95 * pulse)),
        )

    pygame.draw.rect(surface, base, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, width=3, border_radius=10)

    if text:
        txt = font.render(text, True, text_c)
        surface.blit(txt, txt.get_rect(center=rect.center))


def draw_panel(surface, rect, ui_scale, title=None, fonts=None):
    """
    Semi-transparent panel with optional title.
    Returns the panel surface that has been blitted to `surface`.
    """
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    # Dark purple-tinted background for retro vibe
    panel.fill((10, 5, 20, 225))
    # Neon border
    pygame.draw.rect(panel, (120, 255, 200), panel.get_rect(), 2, border_radius=4)

    if title and fonts is not None:
        title_surf = fonts["normal"].render(title, True, WHITE)
        panel.blit(title_surf, title_surf.get_rect(midtop=(rect.width // 2, int(10 * ui_scale))))

    surface.blit(panel, rect.topleft)
    return panel


def center_text(surface, text, font, color, y, screen_w):
    """Draw centered text at a given y."""
    surf = font.render(text, True, color)
    surface.blit(surf, surf.get_rect(center=(screen_w // 2, y)))


# ------------------------------------------------------------
# Text wrapping
# ------------------------------------------------------------

def wrap_text(surface, text, font, color, x, y, max_width, line_spacing=0):
    """
    Render wrapped text onto surface starting at (x,y); returns final y.
    """
    words = text.split()
    if not words:
        return y

    line = ""
    for word in words:
        test = (line + " " + word).strip()
        w, _ = font.size(test)
        if w <= max_width:
            line = test
        else:
            if line:
                surf = font.render(line, True, color)
                surface.blit(surf, (x, y))
                y += surf.get_height() + line_spacing
            line = word

    if line:
        surf = font.render(line, True, color)
        surface.blit(surf, (x, y))
        y += surf.get_height() + line_spacing

    return y


# ------------------------------------------------------------
# Skin preview
# ------------------------------------------------------------

def draw_skin_preview(surface, card_rect, skin_assets, ui_scale):
    """
    Draws the slime preview using idle / run / jump frames from skin_assets.
    Expects skin_assets = {"idle":[...], "run":[...], "jump":surface or None}
    """
    idle_frames = skin_assets.get("idle") or []
    run_frames = skin_assets.get("run") or []
    jump_img = skin_assets.get("jump")

    frame = None
    if idle_frames:
        frame = idle_frames[0]
    elif run_frames:
        frame = run_frames[0]
    elif jump_img is not None:
        frame = jump_img

    if frame is None:
        return

    fw, fh = frame.get_size()
    target_h = int(card_rect.height * 0.45)
    scale = target_h / float(fh)
    target_w = int(fw * scale)

    preview = pygame.transform.smoothscale(frame, (target_w, target_h))
    dest = preview.get_rect(center=(card_rect.centerx, card_rect.centery + int(10 * ui_scale)))
    surface.blit(preview, dest)


# ------------------------------------------------------------
# Cycle selector & toggle switch (for menus)
# ------------------------------------------------------------

def draw_cycle_selector(surface, label, value, fonts, x, y, w, h, focused=False):
    box = Rect(x, y, w, h)
    pygame.draw.rect(surface, (5, 5, 15, 200), box, border_radius=2)
    border_col = (160, 220, 255) if not focused else (255, 255, 160)
    pygame.draw.rect(surface, border_col, box, 2, border_radius=2)

    label_surf = fonts["normal"].render(f"{label}: {value}", True, WHITE)
    surface.blit(label_surf, (x + int(12 * (w / 300)), y + h // 4))


def draw_toggle_switch(surface, label, enabled, fonts, x, y, w, h, focused=False):
    box = Rect(x, y, w, h)
    pygame.draw.rect(surface, (5, 5, 15, 200), box, border_radius=2)
    border_col = (160, 220, 255) if not focused else (255, 255, 160)
    pygame.draw.rect(surface, border_col, box, 2, border_radius=2)

    state = "ON" if enabled else "OFF"
    text = fonts["normal"].render(f"{label}: {state}", True, WHITE)
    surface.blit(text, (x + int(12 * (w / 300)), y + h // 4))
