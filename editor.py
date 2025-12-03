import os
import json
import random

from pygame import Rect
import pygame

import config
from ui import draw_panel

WHITE = config.WHITE


# ------------------------------------------------------------
# Level Editor File & Runtime Helpers
# ------------------------------------------------------------

EDITOR_DIR = os.path.join(config.LEVELS_DIR, "custom")


def ensure_editor_dir():
    if not os.path.isdir(EDITOR_DIR):
        try:
            os.makedirs(EDITOR_DIR, exist_ok=True)
        except Exception:
            # Fail silently; editor will just see no levels
            pass


def editor_level_path(level: int) -> str:
    ensure_editor_dir()
    return os.path.join(EDITOR_DIR, f"level_{level:02d}.json")


def editor_load_level(level: int):
    """
    Load a custom level JSON from levels/custom/level_XX.json.
    Returns a dict with 'platforms', 'coins', 'enemies' lists.
    """
    path = editor_level_path(level)
    if not os.path.exists(path):
        return {"platforms": [], "coins": [], "enemies": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"platforms": [], "coins": [], "enemies": []}

    data.setdefault("platforms", [])
    data.setdefault("coins", [])
    data.setdefault("enemies", [])
    return data


def editor_save_level(level: int, data: dict):
    """
    Save a custom level JSON to levels/custom/level_XX.json.
    """
    path = editor_level_path(level)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[editor] Save failed: {e}")


def apply_custom_level_to_state(
    level: int,
    wstate: dict,
    coin_img,
    enemy_sprites: dict,
    scale_factor: float,
):
    """
    Load levels/custom/level_XX.json and populate the current run state.
    Keeps other state (health, timers) intact and only sets platforms/coins/enemies.
    Safe if the file is missing or empty.
    """
    data = editor_load_level(level)

    # Platforms
    plats = []
    for p in data.get("platforms", []):
        rect = Rect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
        ptype = p.get("type", "normal")
        plats.append(
            {
                "rect": rect,
                "type": ptype,
                "vx": 0.0,
                "vy": 0.0,
                "fall_started": False,
                "fall_timer": 0.0,
                "fragile_hits": 0,
                "depth": random.uniform(0.9, 1.1),
            }
        )
    wstate["platforms"] = plats

    # Coins
    coins = []
    if coin_img is not None:
        cw, ch = coin_img.get_size()
    else:
        size = int(32 * scale_factor)
        cw = ch = size

    for c in data.get("coins", []):
        r = Rect(0, 0, cw, ch)
        r.center = (int(c["x"]), int(c["y"]))
        coins.append(r)
    wstate["coins"] = coins

    # Enemies
    enemies = []
    for e in data.get("enemies", []):
        kind = e.get("kind", "walker")
        img = enemy_sprites.get(kind)
        if img is not None:
            w, h = img.get_size()
        else:
            size = int(48 * scale_factor)
            w = h = size
        r = Rect(0, 0, w, h)
        r.center = (int(e["x"]), int(e["y"]))
        enemies.append(
            {
                "kind": kind,
                "rect": r,
                "vx": 0.0,
                "vy": 0.0,
                "t": 0.0,
                "state": "idle",
                "base_y": float(r.centery),
            }
        )
    wstate["enemies"] = enemies


def draw_level_editor(
    game_surface,
    fonts,
    ui_scale: float,
    screen_w: int,
    screen_h: int,
    scale_factor: float,
    dt: float,
    editor_level: int,
    editor_data: dict,
    editor_tool: str,
    editor_enemy_kind: str,
    editor_platform_type: str,
    editor_grid_snap: bool,
    editor_platform_width: int,
    editor_platform_height: int,
    editor_status_msg: str,
    editor_status_timer: float,
    editor_drag_active: bool,
    editor_drag_kind,
    editor_drag_payload,
    editor_drag_from_palette: bool,
    editor_drag_target,
):
    """
    Render the level editor UI and return updated rect caches + status timer.
    """
    # Title
    title = fonts["title"].render("LEVEL EDITOR", True, WHITE)
    game_surface.blit(title, title.get_rect(center=(screen_w // 2, int(80 * ui_scale))))

    # Build interactive info line segments
    prefix_text = f"Custom Level {editor_level:02d} | "
    tool_text = f"Tool: {editor_tool}"
    plat_text = f" | Plat: {editor_platform_type} ({editor_platform_width}px)"
    enemy_text = f" | Enemy: {editor_enemy_kind}"
    snap_text = f" | Snap: {'ON' if editor_grid_snap else 'OFF'}"

    prefix_surf = fonts["small"].render(prefix_text, True, WHITE)
    tool_surf = fonts["small"].render(tool_text, True, WHITE)
    plat_surf = fonts["small"].render(plat_text, True, WHITE)
    enemy_surf = fonts["small"].render(enemy_text, True, WHITE)
    snap_surf = fonts["small"].render(snap_text, True, WHITE)

    total_w = (
        prefix_surf.get_width()
        + tool_surf.get_width()
        + plat_surf.get_width()
        + enemy_surf.get_width()
        + snap_surf.get_width()
    )
    line_y = int(120 * ui_scale)
    y_top = line_y - prefix_surf.get_height() // 2
    start_x = screen_w // 2 - total_w // 2

    x = start_x
    game_surface.blit(prefix_surf, (x, y_top))
    x += prefix_surf.get_width()

    tool_rect = prefix_surf.get_rect(topleft=(x, y_top))
    tool_rect.width = tool_surf.get_width()
    tool_rect.height = tool_surf.get_height()
    game_surface.blit(tool_surf, tool_rect)
    x += tool_surf.get_width()

    plat_rect = plat_surf.get_rect(topleft=(x, y_top))
    game_surface.blit(plat_surf, plat_rect)
    x += plat_surf.get_width()

    enemy_rect = enemy_surf.get_rect(topleft=(x, y_top))
    game_surface.blit(enemy_surf, enemy_rect)
    x += enemy_surf.get_width()

    snap_rect = snap_surf.get_rect(topleft=(x, y_top))
    game_surface.blit(snap_surf, snap_rect)

    editor_info_tool_rect = tool_rect
    editor_info_plat_rect = plat_rect
    editor_info_enemy_rect = enemy_rect
    editor_info_snap_rect = snap_rect

    # Left-side palette panel for drag-and-drop
    panel_w = int(220 * ui_scale)
    panel_h = screen_h - int(140 * ui_scale)
    editor_palette_rect = pygame.Rect(0, int(140 * ui_scale), panel_w, panel_h)
    draw_panel(game_surface, editor_palette_rect, ui_scale, title="PALETTE", fonts=fonts)

    editor_palette_platform_rects = []
    editor_palette_enemy_rects = []
    editor_palette_coin_rect = None

    palette_x = editor_palette_rect.left + int(12 * ui_scale)
    y = editor_palette_rect.top + int(40 * ui_scale)

    # Play area border (visual guide)
    play_left = editor_palette_rect.right + int(8 * ui_scale)
    play_rect = pygame.Rect(
        play_left,
        int(140 * ui_scale),
        screen_w - play_left - int(16 * ui_scale),
        screen_h - int(160 * ui_scale),
    )
    pygame.draw.rect(game_surface, (80, 160, 220), play_rect, 2)

    # Platforms section
    plat_label = fonts["small"].render("Platforms", True, WHITE)
    game_surface.blit(plat_label, (palette_x, y))
    y += plat_label.get_height() + int(6 * ui_scale)

    entry_h = int(28 * ui_scale)
    entry_w = editor_palette_rect.width - int(24 * ui_scale)
    for ptype in config.PLATFORM_TYPE_CONFIG.keys():
        r = pygame.Rect(palette_x, y, entry_w, entry_h)
        is_selected = (editor_tool == "platform" and editor_platform_type == ptype)
        base_col = (60, 80, 120) if not is_selected else (100, 140, 200)
        pygame.draw.rect(game_surface, base_col, r, border_radius=4)
        pygame.draw.rect(game_surface, WHITE, r, 1, border_radius=4)

        label = fonts["tiny"].render(ptype.title(), True, WHITE)
        game_surface.blit(label, label.get_rect(center=r.center))

        editor_palette_platform_rects.append((ptype, r))
        y += entry_h + int(4 * ui_scale)

    y += int(10 * ui_scale)

    # Coin section
    coin_label = fonts["small"].render("Coins", True, WHITE)
    game_surface.blit(coin_label, (palette_x, y))
    y += coin_label.get_height() + int(6 * ui_scale)

    coin_rect = pygame.Rect(palette_x, y, entry_w, entry_h)
    is_selected_coin = (editor_tool == "coin")
    base_col = (100, 90, 40) if not is_selected_coin else (160, 140, 60)
    pygame.draw.rect(game_surface, base_col, coin_rect, border_radius=4)
    pygame.draw.rect(game_surface, WHITE, coin_rect, 1, border_radius=4)
    coin_icon_r = int(entry_h * 0.35)
    pygame.draw.circle(
        game_surface,
        (240, 210, 80),
        (coin_rect.left + coin_icon_r + int(8 * ui_scale), coin_rect.centery),
        coin_icon_r,
    )
    text_x = coin_rect.left + int(8 * ui_scale) + 2 * coin_icon_r + int(6 * ui_scale)
    coin_text = fonts["tiny"].render("Coin", True, WHITE)
    game_surface.blit(coin_text, (text_x, coin_rect.centery - coin_text.get_height() // 2))
    editor_palette_coin_rect = coin_rect

    y += entry_h + int(10 * ui_scale)

    # Enemies section
    enemy_label = fonts["small"].render("Enemies", True, WHITE)
    game_surface.blit(enemy_label, (palette_x, y))
    y += enemy_label.get_height() + int(6 * ui_scale)

    editor_palette_enemy_rects = []
    for kind in config.ENEMY_CONFIG.keys():
        r = pygame.Rect(palette_x, y, entry_w, entry_h)
        is_selected_enemy = (editor_tool == "enemy" and editor_enemy_kind == kind)
        base_col = (120, 60, 80) if not is_selected_enemy else (180, 90, 120)
        pygame.draw.rect(game_surface, base_col, r, border_radius=4)
        pygame.draw.rect(game_surface, WHITE, r, 1, border_radius=4)

        label = fonts["tiny"].render(kind.title(), True, WHITE)
        game_surface.blit(label, label.get_rect(center=r.center))

        editor_palette_enemy_rects.append((kind, r))
        y += entry_h + int(4 * ui_scale)

    # Grid
    grid_color = (80, 80, 80, 80)
    for gx in range(0, screen_w, int(64 * ui_scale)):
        pygame.draw.line(game_surface, grid_color, (gx, int(140 * ui_scale)), (gx, screen_h))
    for gy in range(int(140 * ui_scale), screen_h, int(64 * ui_scale)):
        pygame.draw.line(game_surface, grid_color, (0, gy), (screen_w, gy))

    # Platforms
    for p in editor_data["platforms"]:
        r = pygame.Rect(p["x"], p["y"], p["w"], p["h"])
        pygame.draw.rect(game_surface, (140, 180, 220), r)
        pygame.draw.rect(game_surface, WHITE, r, 1)

    # Coins
    for c in editor_data["coins"]:
        pygame.draw.circle(game_surface, (240, 210, 80), (int(c["x"]), int(c["y"])), int(10 * ui_scale))

    # Enemies
    for e in editor_data["enemies"]:
        size = int(32 * ui_scale)
        r = pygame.Rect(0, 0, size, size)
        r.center = (int(e["x"]), int(e["y"]))
        pygame.draw.rect(game_surface, (220, 80, 80), r)
        pygame.draw.rect(game_surface, (255, 230, 230), r, 1)

        label = fonts["tiny"].render(e["kind"], True, WHITE)
        game_surface.blit(label, label.get_rect(center=r.center))

    # Mini-map overview (top-right)
    mini_w = int(220 * ui_scale)
    mini_h = int(140 * ui_scale)
    mini_rect = pygame.Rect(
        screen_w - mini_w - int(16 * ui_scale),
        int(80 * ui_scale),
        mini_w,
        mini_h,
    )
    pygame.draw.rect(game_surface, (5, 5, 15, 220), mini_rect, border_radius=4)
    pygame.draw.rect(game_surface, (160, 220, 255), mini_rect, 1, border_radius=4)

    scale_x = mini_rect.width / float(screen_w)
    scale_y = mini_rect.height / float(screen_h)

    # Mini platforms
    for p in editor_data["platforms"]:
        rx = int(p["x"] * scale_x)
        ry = int(p["y"] * scale_y)
        rw = max(1, int(p["w"] * scale_x))
        rh = max(1, int(p["h"] * scale_y))
        mr = pygame.Rect(mini_rect.left + rx, mini_rect.top + ry, rw, rh)
        pygame.draw.rect(game_surface, (100, 180, 230), mr)

    # Mini coins
    for c in editor_data["coins"]:
        cx = mini_rect.left + int(c["x"] * scale_x)
        cy = mini_rect.top + int(c["y"] * scale_y)
        pygame.draw.circle(game_surface, (240, 210, 80), (cx, cy), 2)

    # Mini enemies
    for e in editor_data["enemies"]:
        ex_m = mini_rect.left + int(e["x"] * scale_x)
        ey_m = mini_rect.top + int(e["y"] * scale_y)
        er = pygame.Rect(ex_m - 2, ey_m - 2, 4, 4)
        pygame.draw.rect(game_surface, (230, 100, 120), er)

    # Drag preview for palette items
    if editor_drag_active and editor_drag_kind:
        mx, my = pygame.mouse.get_pos()
        ex, ey = mx, my

        if editor_grid_snap:
            grid_x = int(64 * ui_scale)
            grid_y = int(64 * ui_scale)
            grid_top = int(140 * ui_scale)
            if grid_x > 0:
                ex = (ex // grid_x) * grid_x + grid_x // 2
            if grid_y > 0:
                if ey < grid_top:
                    ey = grid_top
                ey = grid_top + ((ey - grid_top) // grid_y) * grid_y + grid_y // 2

        if editor_drag_kind == "platform":
            w = editor_platform_width
            h = editor_platform_height
            r = pygame.Rect(ex - w // 2, ey - h // 2, w, h)
            pygame.draw.rect(game_surface, (120, 200, 255), r, 2)
        elif editor_drag_kind == "coin":
            radius = int(10 * ui_scale)
            pygame.draw.circle(game_surface, (240, 210, 80), (int(ex), int(ey)), radius, 2)
        elif editor_drag_kind == "enemy":
            size = int(32 * ui_scale)
            r = pygame.Rect(0, 0, size, size)
            r.center = (int(ex), int(ey))
            pygame.draw.rect(game_surface, (255, 160, 160), r, 2)

    # Status feedback message
    if editor_status_timer > 0.0:
        editor_status_timer -= dt
        if editor_status_timer < 0:
            editor_status_timer = 0.0
    if editor_status_timer > 0.0 and editor_status_msg:
        status_surf = fonts["small"].render(editor_status_msg, True, WHITE)
        game_surface.blit(
            status_surf,
            status_surf.get_rect(center=(screen_w // 2, int(150 * ui_scale))),
        )

    # Controls hint
    y = int(screen_h * 0.80)
    for line in [
        "Left-click: place/move | Right-click: delete",
        "1=platform 2=coin 3=enemy | Tab/wheel on 'Tool' to cycle",
        "Q/E or wheel on 'Enemy': enemy kind | Z/X or wheel on 'Plat': platform type | ,/. platform width",
        "G or wheel on 'Snap': toggle grid snap | P: test play level | Ctrl+Z/Y: undo/redo",
        "[ / ]: switch custom level | Ctrl+C/V: copy/paste | Ctrl+S: save | Esc/B: menu",
    ]:
        s = fonts["small"].render(line, True, WHITE)
        game_surface.blit(s, s.get_rect(center=(screen_w // 2, y)))
        y += int(22 * ui_scale)

    return (
        editor_palette_rect,
        editor_palette_platform_rects,
        editor_palette_enemy_rects,
        editor_palette_coin_rect,
        editor_info_tool_rect,
        editor_info_plat_rect,
        editor_info_enemy_rect,
        editor_info_snap_rect,
        editor_status_msg,
        editor_status_timer,
    )

