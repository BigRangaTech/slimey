# ============================================================
#  Slimey - MAIN GAME FILE
#  (Part 1/4)
# ------------------------------------------------------------
#  Core runtime, world loop, menus, editor integration,
#  input handling, rendering pipeline.
# ============================================================

import pygame
import time
import random
import math
import os
import json
import copy

from pygame import Rect

# Import master config
import config

# UI helpers
from ui import (
    build_fonts,
    draw_button,
    draw_panel,
    center_text,
    wrap_text,
    draw_skin_preview,
    draw_cycle_selector,
    draw_toggle_switch,
)

# World logic
from world import (
    reset_state,
    spawn_tree,
    spawn_coin,
    spawn_platform,
    spawn_platform_enemy,
    spawn_air_enemy,
    spawn_ground_enemy,
    spawn_dust_particles,
    spawn_spark_burst,
    spawn_levelup_burst,
    update_particles,
    update_enemies,
)

# Resource loader
from resources import (
    reload_all_assets,
    load_save,
    save_save,
    parse_resolution,
    compute_scale_factor,
)

pygame.init()
pygame.mixer.init()

# ------------------------------------------------------------
# Global Constants (imported for local readability)
# ------------------------------------------------------------
WHITE = config.WHITE
BLACK = config.BLACK

BTN_A = config.BTN_A
BTN_B = config.BTN_B
BTN_X = config.BTN_X
BTN_Y = config.BTN_Y
BTN_START = config.BTN_START

FPS = config.FPS

GRAVITY = config.GRAVITY
JUMP_STRENGTH = config.JUMP_STRENGTH
PLAYER_MOVE_SPEED = config.PLAYER_MOVE_SPEED
GAME_SPEED_BASE = config.GAME_SPEED_BASE

INVINCIBLE_TIME = config.INVINCIBLE_TIME
KNOCKBACK_TIME = config.KNOCKBACK_TIME
KNOCKBACK_SPEED = config.KNOCKBACK_SPEED

DASH_SPEED = config.DASH_SPEED
DASH_DURATION = config.DASH_DURATION
DASH_COOLDOWN = config.DASH_COOLDOWN

SCREEN_SHAKE_HIT = config.SCREEN_SHAKE_HIT
SCREEN_SHAKE_KILL = config.SCREEN_SHAKE_KILL
SCREEN_SHAKE_INTENSITY = config.SCREEN_SHAKE_INTENSITY

BASE_MAX_HEALTH = config.BASE_MAX_HEALTH
LEVEL_UP_EVERY_COINS = config.LEVEL_UP_EVERY_COINS

RUN_DUST_INTERVAL = config.RUN_DUST_INTERVAL
DASH_TRAIL_INTERVAL = config.DASH_TRAIL_INTERVAL
HIT_FLASH_FREQUENCY = config.HIT_FLASH_FREQUENCY
BOSS_LEVELS = config.BOSS_LEVELS


# ------------------------------------------------------------
# Input binding helpers (keyboard + controller)
# ------------------------------------------------------------

def action_down_kb(action, event_key, kb_bindings):
    """
    Check if a keyboard event key corresponds to an action.
    """
    bound = kb_bindings.get(action, [])
    name = pygame.key.name(event_key)
    code = f"K_{name}"
    return code in bound


def parse_controller_code(code):
    """
    Interpret controller binding strings: "BTN_A", "HAT_LEFT", etc.
    """
    if code.startswith("BTN_"):
        return ("button", getattr(config, code))
    elif code.startswith("HAT_"):
        direction = code.replace("HAT_", "")
        return ("hat", direction)
    return None


def action_down_controller(action, joystick, btn_event, hat_event, ctr_bindings):
    """
    Controller button or hat press detection.
    """
    codes = ctr_bindings.get(action, [])
    for code in codes:
        kind = parse_controller_code(code)
        if not kind:
            continue

        type_, value = kind
        if type_ == "button" and btn_event is not None:
            if btn_event.button == value:
                return True

        elif type_ == "hat" and hat_event is not None:
            hx, hy = hat_event.value
            if value == "LEFT" and hx < 0:
                return True
            if value == "RIGHT" and hx > 0:
                return True
            if value == "UP" and hy > 0:
                return True
            if value == "DOWN" and hy < 0:
                return True

    return False


# ------------------------------------------------------------
# Level Editor Helpers
# ------------------------------------------------------------

EDITOR_DIR = os.path.join(config.LEVELS_DIR, "custom")

def ensure_editor_dir():
    if not os.path.isdir(EDITOR_DIR):
        try:
            os.makedirs(EDITOR_DIR, exist_ok=True)
        except:
            pass

def editor_level_path(level:int)->str:
    ensure_editor_dir()
    return os.path.join(EDITOR_DIR, f"level_{level:02d}.json")

def editor_load_level(level:int):
    path = editor_level_path(level)
    if not os.path.exists(path):
        return {"platforms": [], "coins": [], "enemies": []}

    try:
        with open(path,"r",encoding="utf-8") as f:
            data = json.load(f)
    except:
        return {"platforms": [], "coins": [], "enemies": []}

    data.setdefault("platforms",[])
    data.setdefault("coins",[])
    data.setdefault("enemies",[])
    return data

def editor_save_level(level:int, data:dict):
    path = editor_level_path(level)
    try:
        with open(path,"w",encoding="utf-8") as f:
            json.dump(data,f,indent=2)
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
        plats.append({
            "rect": rect,
            "type": ptype,
            "vx": 0.0,
            "vy": 0.0,
            "fall_started": False,
            "fall_timer": 0.0,
            "fragile_hits": 0,
            "depth": random.uniform(0.9, 1.1),
        })
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
        enemies.append({
            "kind": kind,
            "rect": r,
            "vx": 0.0,
            "vy": 0.0,
            "t": 0.0,
            "state": "idle",
            "base_y": float(r.centery),
        })
    wstate["enemies"] = enemies


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def clamp(x, mn, mx):
    return mn if x < mn else mx if x > mx else x

def sign(x):
    return -1 if x < 0 else 1 if x > 0 else 0


# ------------------------------------------------------------
# Camera shake
# ------------------------------------------------------------

def apply_shake(surface, sx, sy):
    shaken = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    shaken.blit(surface, (sx, sy))
    return shaken


def draw_heart(surface, cx, cy, size, color, outline_color=None):
    """
    Simple pixel-style heart using circles + triangle.
    cx, cy = center of the heart.
    """
    r = max(2, size // 2)

    # Top lobes
    left_center = (cx - r // 2, cy - r // 4)
    right_center = (cx + r // 2, cy - r // 4)
    pygame.draw.circle(surface, color, left_center, r // 2)
    pygame.draw.circle(surface, color, right_center, r // 2)

    # Bottom triangle
    points = [
        (cx - r, cy),
        (cx + r, cy),
        (cx, cy + r),
    ]
    pygame.draw.polygon(surface, color, points)

    if outline_color is not None:
        pygame.draw.circle(surface, outline_color, left_center, r // 2, 1)
        pygame.draw.circle(surface, outline_color, right_center, r // 2, 1)
        pygame.draw.lines(surface, outline_color, True, points, 1)


def adjust_setting(settings:dict, cfg_map:dict, key:str, delta:int):
    """
    Change a numeric setting by one step in cfg_map and clamp it.
    """
    cfg = cfg_map.get(key)
    if not cfg:
        return settings.get(key, 0)

    val = settings.get(key, cfg["min"])
    val += cfg.get("step", 0.1) * delta
    val = clamp(val, cfg["min"], cfg["max"])
    val = round(val, 2)
    settings[key] = val
    return val


def cycle_value(seq, current, delta):
    """
    Cycle forward/backward through seq by delta.
    Returns (new_value, new_index).
    """
    if not seq:
        return current, 0
    try:
        idx = seq.index(current)
    except ValueError:
        idx = 0
    idx = (idx + delta) % len(seq)
    return seq[idx], idx


def max_level_reached(save_data:dict)->int:
    """
    Best level reached across recorded runs.
    """
    levels = [r.get("level", 1) for r in save_data.get("high_scores", []) if isinstance(r, dict)]
    for runs in save_data.get("scores_by_level", {}).values():
        for r in runs:
            if isinstance(r, dict):
                levels.append(r.get("level", 1))
    return max(levels) if levels else 1


def medal_for_score(score: int) -> str:
    """
    Simple medal tier based on best score (time survived).
    """
    if score >= 120:
        return "Gold"
    if score >= 60:
        return "Silver"
    if score >= 30:
        return "Bronze"
    return ""


CONTROL_ACTION_ORDER = ["move_left", "move_right", "jump", "dash", "pause"]
CONTROL_ACTION_LABELS = {
    "move_left": "Move Left",
    "move_right": "Move Right",
    "jump": "Jump",
    "dash": "Dash",
    "pause": "Pause",
}


def format_key_list(codes):
    if not codes:
        return "-"
    parts = []
    for c in codes:
        if c.startswith("K_"):
            parts.append(c[2:].upper())
        else:
            parts.append(c.upper())
    return " / ".join(parts)


def format_controller_list(codes):
    if not codes:
        return "-"
    parts = []
    for c in codes:
        if c.startswith("BTN_"):
            # Friendly button names
            name = c.replace("BTN_", "")
            parts.append(name)
        elif c.startswith("HAT_"):
            dir_name = c.replace("HAT_", "")
            parts.append(f"D-Pad {dir_name.title()}")
        else:
            parts.append(c)
    return " / ".join(parts)


def controller_button_name(btn_index: int) -> str:
    """Map a joystick button index back to a BTN_* code string."""
    mapping = {
        config.BTN_A: "BTN_A",
        config.BTN_B: "BTN_B",
        config.BTN_X: "BTN_X",
        config.BTN_Y: "BTN_Y",
        config.BTN_START: "BTN_START",
    }
    return mapping.get(btn_index, f"BTN_{btn_index}")


def hat_direction_name(hx: int, hy: int):
    """Return a HAT_* code string for a hat direction, or None."""
    if hx < 0:
        return "HAT_LEFT"
    if hx > 0:
        return "HAT_RIGHT"
    if hy > 0:
        return "HAT_UP"
    if hy < 0:
        return "HAT_DOWN"
    return None


def get_level_meta(level: int):
    """
    Return (name, story) for a level index based on config.LEVEL_CONFIGS.
    """
    if 1 <= level <= len(config.LEVEL_CONFIGS):
        cfg = config.LEVEL_CONFIGS[level - 1]
        return cfg.get("name", f"Level {level}"), cfg.get("story", "")
    return f"Level {level}", ""


def get_world_for_level(level: int, world_packs: dict):
    """
    Pick a world_id and config for a given level using WORLD_PACKS.
    Falls back to the last defined world if no explicit match.
    """
    chosen_id = None
    chosen_cfg = None
    last_id = None
    last_cfg = None

    for wid, cfg in world_packs.items():
        last_id, last_cfg = wid, cfg

        levels = cfg.get("levels")
        if isinstance(levels, (list, tuple)) and level in levels:
            return wid, cfg

        lr = cfg.get("level_range")
        if isinstance(lr, (list, tuple)) and len(lr) == 2:
            lo, hi = lr
            if lo <= level <= hi:
                chosen_id, chosen_cfg = wid, cfg

    if chosen_id is not None:
        return chosen_id, chosen_cfg
    if last_id is not None:
        return last_id, last_cfg
    return None, None


def award_achievement(save_data: dict, ach_id: str):
    """
    Mark an achievement unlocked if defined in config.ACHIEVEMENTS.
    """
    if ach_id not in config.ACHIEVEMENTS:
        return False
    ach = save_data.setdefault("achievements", {})
    if ach.get(ach_id):
        return False
    ach[ach_id] = True
    save_save(save_data)
    return True


# Settings hub menu items (grouped settings + extras)
SETTINGS_MENU_ITEMS = [
    {"id": "display_settings",  "label": "Display"},
    {"id": "gameplay_settings", "label": "Gameplay"},
    {"id": "audio_settings",    "label": "Audio"},
    {"id": "controls_settings", "label": "Controls"},
    {"id": "skins_menu",        "label": "Skins"},
    {"id": "high_scores",       "label": "High Scores"},
    {"id": "how_to_play",       "label": "How to Play"},
    {"id": "level_editor",      "label": "Level Editor"},
    {"id": "shop",              "label": "Shop"},
    {"id": "back",              "label": "Back"},
]


def editor_push_undo(stack, editor_data):
    """
    Push a deep copy of editor_data onto the undo stack.
    """
    snapshot = {
        "platforms": [dict(p) for p in editor_data.get("platforms", [])],
        "coins": [dict(c) for c in editor_data.get("coins", [])],
        "enemies": [dict(e) for e in editor_data.get("enemies", [])],
    }
    stack.append(snapshot)


# ------------------------------------------------------------
# MAIN game loop
# ------------------------------------------------------------

def main():

    # --------------------------------------------------------
    # Load save + settings
    # --------------------------------------------------------
    save_data = load_save()
    settings = save_data["settings"]

    # If player never chose an FX mode, default to scanlines for a retro feel.
    if settings.get("fx_mode", "off") == "off":
        settings["fx_mode"] = "scanlines"
        save_save(save_data)

    resolution_str = settings.get("resolution", config.DEFAULT_RESOLUTION)
    fullscreen_flag = settings.get("fullscreen", config.DEFAULT_FULLSCREEN)
    vsync_flag = bool(settings.get("vsync", True))
    screen_w, screen_h = parse_resolution(resolution_str)
    flags = pygame.FULLSCREEN if fullscreen_flag else 0
    try:
        screen = pygame.display.set_mode((screen_w, screen_h), flags, vsync=1 if vsync_flag else 0)
    except TypeError:
        # Older pygame without vsync kwarg
        screen = pygame.display.set_mode((screen_w, screen_h), flags)
    pygame.display.set_caption("Slimey")

    scale_factor = compute_scale_factor(resolution_str)
    ui_scale = scale_factor

    # --------------------------------------------------------
    # Load assets (backgrounds, skins, FX, audio)
    # --------------------------------------------------------
    assets = reload_all_assets(scale_factor, config, screen_w, screen_h)

    backgrounds = assets["backgrounds"]
    world_backgrounds = assets["world_backgrounds"]
    skins_assets = assets["skins"]
    ground_img = assets["ground"]
    tree_img = assets["tree"]
    coin_img = assets["coin"]
    enemy_sprites = assets["enemy_sprites"]
    fx_masks = assets["fx"]
    sounds = assets["sounds"]

    music_path = assets["music_path"]
    if music_path:
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(settings["music_volume"])
            pygame.mixer.music.play(-1)
        except:
            print("[audio] Could not start music")

    jump_snd = sounds.get("jump")
    coin_snd = sounds.get("coin")
    hit_snd  = sounds.get("hit")
    land_snd = sounds.get("land")

    # --------------------------------------------------------
    # Fonts
    # --------------------------------------------------------
    fonts = build_fonts(ui_scale)

    # --------------------------------------------------------
    # Game state variables
    # --------------------------------------------------------
    clock = pygame.time.Clock()

    game_state = "menu"  # menu, playing, paused, game_over, settings menus, editor
    running = True

    # Menu focus indices
    menu_focus = 0
    display_focus = 0
    gameplay_focus = 0
    audio_focus = 0
    game_over_focus = 0
    pause_focus = 0
    level_select_focus = 0
    skins_focus = 0
    high_scores_focus = 0
    settings_menu_focus = 0
    shop_focus = 0
    controls_focus = 0
    controls_waiting_action = None
    controls_mode = "keyboard"  # "keyboard" or "controller"
    controls_waiting_mode = None
    menu_button_rects = []
    pause_option_rects = []
    game_over_option_rects = []
    shop_item_rects = []
    display_row_rects = []
    display_fullscreen_rect = None
    display_vsync_rect = None
    gameplay_row_rects = []
    audio_row_rects = []
    level_row_rects = []
    controls_row_rects = []

    # Level intro / transitions
    level_intro_timer = 0.0
    level_intro_title = ""
    level_intro_story = ""

    # Level editor
    editor_level = 1
    editor_data = editor_load_level(editor_level)
    editor_tool = "platform"
    editor_enemy_kind = "walker"
    editor_platform_type = "normal"
    editor_grid_snap = True
    editor_platform_width = int(200 * scale_factor)
    editor_platform_height = int(24 * scale_factor)
    editor_status_msg = ""
    editor_status_timer = 0.0
    editor_palette_rect = None
    editor_palette_platform_rects = []
    editor_palette_enemy_rects = []
    editor_palette_coin_rect = None
    editor_info_tool_rect = None
    editor_info_plat_rect = None
    editor_info_enemy_rect = None
    editor_info_snap_rect = None
    editor_drag_active = False
    editor_drag_kind = None  # "platform", "coin", "enemy"
    editor_drag_payload = None  # platform_type or enemy_kind or None for coin
    editor_drag_from_palette = False
    editor_drag_target = None  # ("platforms"/"coins"/"enemies", index) for moving existing
    editor_undo_stack = []
    editor_redo_stack = []
    editor_clipboard = None

    # --------------------------------------------------------
    # Player & World State
    # --------------------------------------------------------
    player_w = int(80 * scale_factor)
    player_h = int(80 * scale_factor)
    player_rect = pygame.Rect(
        int(screen_w * 0.15), int(screen_h * 0.5) - player_h // 2,
        player_w, player_h
    )

    max_health = BASE_MAX_HEALTH + (1 if save_data["upgrades"]["extra_heart"] else 0)

    wstate = reset_state(player_rect, player_h, max_health)

    # Animation state shortcuts
    skin_name = save_data["skins"]["current_skin"]
    skin_idle = skins_assets.get(skin_name, skins_assets["default"])["idle"]
    skin_run  = skins_assets.get(skin_name, skins_assets["default"])["run"]
    skin_jump = skins_assets.get(skin_name, skins_assets["default"])["jump"]

    # --------------------------------------------------------
    # Controls
    # --------------------------------------------------------
    # Keyboard bindings can be remapped per-save.
    save_data.setdefault("input", {})
    if "keyboard" in save_data["input"]:
        kb_cfg = save_data["input"]["keyboard"]
    else:
        save_data["input"]["keyboard"] = {
            action: list(keys) for action, keys in config.INPUT_CONFIG["keyboard"].items()
        }
        kb_cfg = save_data["input"]["keyboard"]
        save_save(save_data)

    # Controller bindings can also be remapped per-save.
    if "controller" in save_data["input"]:
        ctr_cfg = save_data["input"]["controller"]
    else:
        save_data["input"]["controller"] = {
            action: list(v) for action, v in config.INPUT_CONFIG["controller"].items()
            if isinstance(v, (list, tuple))
        }
        ctr_cfg = save_data["input"]["controller"]
        save_save(save_data)

    joysticks = []
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        joysticks.append(j)

    # Movement inputs
    move_left_down = False
    move_right_down = False
    jump_down = False
    dash_down = False

    # Editor flags
    mouse_left = False
    mouse_right = False

    # --------------------------------------------------------
    # Background scrolling
    # --------------------------------------------------------
    scroll_offsets = []
    for _ in backgrounds:
        scroll_offsets.append({"far": 0.0, "mid": 0.0, "near": 0.0})

    # --------------------------------------------------------
    # Main LOOP begins here
    # --------------------------------------------------------
    last_time = time.time()

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now
        dt = min(dt, 1 / 30)

        # time-scale from settings
        dt_scaled = dt * settings.get("game_speed_mult", 1.0)

        # Screen buffer
        game_surface = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)

        # ----------------------------------------------------
        # Process input events
        # ----------------------------------------------------
        btn_event = None
        hat_event = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # --- KEYDOWN ---
            if event.type == pygame.KEYDOWN:
                # Controls remap capture
                if game_state == "controls_settings" and controls_waiting_action is not None:
                    # Keyboard remap
                    if controls_waiting_mode == "keyboard":
                        if event.key == pygame.K_ESCAPE:
                            controls_waiting_action = None
                            controls_waiting_mode = None
                        else:
                            name = pygame.key.name(event.key)
                            code = f"K_{name}"
                            kb_cfg.setdefault(controls_waiting_action, [])
                            kb_cfg[controls_waiting_action] = [code]
                            save_data.setdefault("input", {})
                            save_data["input"]["keyboard"] = kb_cfg
                            save_save(save_data)
                            controls_waiting_action = None
                            controls_waiting_mode = None
                    else:
                        # In controller mode, only Esc cancels; actual binding is captured
                        # via JOYBUTTONDOWN / JOYHATMOTION handlers.
                        if event.key == pygame.K_ESCAPE:
                            controls_waiting_action = None
                            controls_waiting_mode = None
                    continue

                # ESC global handling
                if event.key == pygame.K_ESCAPE or action_down_kb("pause", event.key, kb_cfg):
                    if game_state == "playing":
                        game_state = "paused"
                        pause_focus = 0
                    elif game_state in (
                        "display_settings", "gameplay_settings", "audio_settings",
                        "skins_menu", "shop", "level_select", "game_over",
                        "high_scores", "level_editor", "controls_settings",
                        "how_to_play", "settings_menu"
                    ):
                        game_state = "menu"
                        menu_focus = 0
                    elif game_state == "menu":
                        running = False
                    continue

                # --- Editor shortcuts ---
                if game_state == "level_editor":
                    if event.key == pygame.K_1:
                        editor_tool = "platform"
                        editor_status_msg = "Tool: platform"
                        editor_status_timer = 2.0
                    elif event.key == pygame.K_2:
                        editor_tool = "coin"
                        editor_status_msg = "Tool: coin"
                        editor_status_timer = 2.0
                    elif event.key == pygame.K_3:
                        editor_tool = "enemy"
                        editor_status_msg = "Tool: enemy"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_TAB:
                        tools = ["platform", "coin", "enemy"]
                        editor_tool = tools[(tools.index(editor_tool) + 1) % len(tools)]
                        editor_status_msg = f"Tool: {editor_tool}"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_q:
                        kinds = list(config.ENEMY_CONFIG.keys())
                        if kinds:
                            i = kinds.index(editor_enemy_kind)
                            editor_enemy_kind = kinds[(i - 1) % len(kinds)]
                            editor_status_msg = f"Enemy: {editor_enemy_kind}"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_e:
                        kinds = list(config.ENEMY_CONFIG.keys())
                        if kinds:
                            i = kinds.index(editor_enemy_kind)
                            editor_enemy_kind = kinds[(i + 1) % len(kinds)]
                            editor_status_msg = f"Enemy: {editor_enemy_kind}"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_z:
                        types = list(config.PLATFORM_TYPE_CONFIG.keys())
                        if types:
                            i = types.index(editor_platform_type)
                            editor_platform_type = types[(i - 1) % len(types)]
                            editor_status_msg = f"Platform: {editor_platform_type}"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_x:
                        types = list(config.PLATFORM_TYPE_CONFIG.keys())
                        if types:
                            i = types.index(editor_platform_type)
                            editor_platform_type = types[(i + 1) % len(types)]
                            editor_status_msg = f"Platform: {editor_platform_type}"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_g:
                        editor_grid_snap = not editor_grid_snap
                        editor_status_msg = f"Snap: {'ON' if editor_grid_snap else 'OFF'}"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_COMMA:
                        step = int(32 * scale_factor)
                        min_w = int(64 * scale_factor)
                        editor_platform_width = max(min_w, editor_platform_width - step)
                        editor_status_msg = f"Platform width: {editor_platform_width}px"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_PERIOD:
                        step = int(32 * scale_factor)
                        max_w = screen_w
                        editor_platform_width = min(max_w, editor_platform_width + step)
                        editor_status_msg = f"Platform width: {editor_platform_width}px"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_p:
                        # Quick-test the current custom level from the editor
                        editor_save_level(editor_level, editor_data)
                        wstate = reset_state(player_rect, player_h, max_health)
                        wstate["level"] = editor_level
                        game_state = "playing"
                        apply_custom_level_to_state(editor_level, wstate, coin_img, enemy_sprites, scale_factor)
                        name, story = get_level_meta(editor_level)
                        prefix = "BOSS LEVEL" if editor_level in BOSS_LEVELS else "LEVEL"
                        level_intro_title = f"{prefix} {editor_level}: {name}"
                        level_intro_story = story
                        level_intro_timer = 3.0
                        editor_status_msg = f"Playtest level {editor_level:02d}"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_LEFTBRACKET:
                        editor_undo_stack.clear()
                        editor_redo_stack.clear()
                        editor_level = max(1, editor_level - 1)
                        editor_data = editor_load_level(editor_level)
                        editor_status_msg = f"Level {editor_level:02d} loaded"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_RIGHTBRACKET:
                        editor_undo_stack.clear()
                        editor_redo_stack.clear()
                        editor_level += 1
                        editor_data = editor_load_level(editor_level)
                        editor_status_msg = f"Level {editor_level:02d} loaded"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        editor_save_level(editor_level, editor_data)
                        editor_status_msg = f"Saved level {editor_level:02d}"
                        editor_status_timer = 2.0

                    elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Undo
                        if editor_undo_stack:
                            editor_redo_stack.append(editor_data)
                            editor_data = editor_undo_stack.pop()
                            editor_status_msg = "Undo"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_y and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Redo
                        if editor_redo_stack:
                            editor_undo_stack.append(editor_data)
                            editor_data = editor_redo_stack.pop()
                            editor_status_msg = "Redo"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_c and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Copy nearest object under mouse into clipboard
                        mx, my = pygame.mouse.get_pos()
                        ex, ey = mx, my
                        nearest = None
                        best_dist2 = (40 * scale_factor) ** 2

                        for i, p in enumerate(editor_data["platforms"]):
                            cx = p["x"] + p["w"] / 2
                            cy = p["y"] + p["h"] / 2
                            d2 = (cx - ex) ** 2 + (cy - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("platforms", i)

                        for i, c in enumerate(editor_data["coins"]):
                            d2 = (c["x"] - ex) ** 2 + (c["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("coins", i)

                        for i, e in enumerate(editor_data["enemies"]):
                            d2 = (e["x"] - ex) ** 2 + (e["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("enemies", i)

                        if nearest:
                            arr, idx = nearest
                            if arr == "platforms":
                                editor_clipboard = ("platforms", dict(editor_data["platforms"][idx]))
                                editor_status_msg = "Copied platform"
                            elif arr == "coins":
                                editor_clipboard = ("coins", dict(editor_data["coins"][idx]))
                                editor_status_msg = "Copied coin"
                            else:
                                editor_clipboard = ("enemies", dict(editor_data["enemies"][idx]))
                                editor_status_msg = "Copied enemy"
                            editor_status_timer = 2.0

                    elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        # Paste clipboard at mouse position
                        if editor_clipboard is not None:
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

                            arr, data = editor_clipboard
                            editor_push_undo(editor_undo_stack, editor_data)
                            editor_redo_stack.clear()

                            if arr == "platforms":
                                p = dict(data)
                                w = p.get("w", editor_platform_width)
                                h = p.get("h", editor_platform_height)
                                p["w"] = w
                                p["h"] = h
                                p["x"] = ex - w // 2
                                p["y"] = ey - h // 2
                                editor_data["platforms"].append(p)
                                editor_status_msg = "Pasted platform"
                            elif arr == "coins":
                                c = dict(data)
                                c["x"] = ex
                                c["y"] = ey
                                editor_data["coins"].append(c)
                                editor_status_msg = "Pasted coin"
                            else:
                                e = dict(data)
                                e["x"] = ex
                                e["y"] = ey
                                editor_data["enemies"].append(e)
                                editor_enemy_kind = e.get("kind", editor_enemy_kind)
                                editor_tool = "enemy"
                                editor_status_msg = "Pasted enemy"

                            editor_status_timer = 2.0

                    continue

                # --- General gameplay keybinds ---
                if action_down_kb("move_left", event.key, kb_cfg):
                    move_left_down = True
                elif action_down_kb("move_right", event.key, kb_cfg):
                    move_right_down = True
                elif action_down_kb("jump", event.key, kb_cfg):
                    jump_down = True
                elif action_down_kb("dash", event.key, kb_cfg):
                    dash_down = True

                # --- Menu navigation ---
                if game_state == "menu":
                    if event.key == pygame.K_UP:
                        menu_focus = max(0, menu_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        menu_focus = min(len(config.MAIN_MENU_ITEMS) - 1, menu_focus + 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        item_id = config.MAIN_MENU_ITEMS[menu_focus]["id"]
                        if item_id == "play":
                            game_state = "playing"
                            # reset run:
                            wstate.update(reset_state(player_rect, player_h, max_health))
                            # Start at level 1, load matching custom layout if present
                            wstate["level"] = 1
                            apply_custom_level_to_state(1, wstate, coin_img, enemy_sprites, scale_factor)
                            # Intro for level 1
                            name, story = get_level_meta(1)
                            level_intro_title = f"LEVEL 1: {name}"
                            level_intro_story = story
                            level_intro_timer = 3.0
                        elif item_id == "level_select":
                            game_state = "level_select"
                            level_select_focus = 0
                        elif item_id == "level_editor":
                            game_state = "level_editor"
                            editor_data = editor_load_level(editor_level)
                        elif item_id == "high_scores":
                            game_state = "high_scores"
                            high_scores_focus = 0
                        elif item_id == "skins":
                            game_state = "skins_menu"
                            skins_focus = 0
                        elif item_id == "how_to_play":
                            game_state = "how_to_play"
                        elif item_id == "settings":
                            game_state = "settings_menu"
                            settings_menu_focus = 0
                        elif item_id == "quit":
                            running = False
                elif game_state == "settings_menu":
                    max_idx = len(SETTINGS_MENU_ITEMS) - 1
                    if event.key == pygame.K_UP:
                        settings_menu_focus = max(0, settings_menu_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        settings_menu_focus = min(max_idx, settings_menu_focus + 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        entry = SETTINGS_MENU_ITEMS[settings_menu_focus]
                        sid = entry["id"]
                        if sid == "display_settings":
                            game_state = "display_settings"
                            display_focus = 0
                        elif sid == "gameplay_settings":
                            game_state = "gameplay_settings"
                            gameplay_focus = 0
                        elif sid == "audio_settings":
                            game_state = "audio_settings"
                            audio_focus = 0
                        elif sid == "controls_settings":
                            game_state = "controls_settings"
                            controls_focus = 0
                        elif sid == "skins_menu":
                            game_state = "skins_menu"
                            skins_focus = 0
                        elif sid == "level_editor":
                            game_state = "level_editor"
                            editor_data = editor_load_level(editor_level)
                        elif sid == "shop":
                            game_state = "shop"
                            shop_focus = 0
                        elif sid == "high_scores":
                            game_state = "high_scores"
                            high_scores_focus = 0
                        elif sid == "how_to_play":
                            game_state = "how_to_play"
                        elif sid == "back":
                            game_state = "menu"
                            menu_focus = 0
                elif game_state == "display_settings":
                    res_count = len(config.SUPPORTED_RESOLUTIONS)
                    max_focus = res_count + 1  # resolutions + fullscreen + vsync
                    if event.key == pygame.K_UP:
                        display_focus = max(0, display_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        display_focus = min(max_focus, display_focus + 1)
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                        if display_focus < res_count:
                            delta = -1 if event.key == pygame.K_LEFT else 1
                            res, _ = cycle_value(
                                config.SUPPORTED_RESOLUTIONS,
                                settings.get("resolution", config.DEFAULT_RESOLUTION),
                                delta if event.key in (pygame.K_LEFT, pygame.K_RIGHT) else 1
                            )
                            settings["resolution"] = res
                        elif display_focus == res_count:
                            settings["fullscreen"] = not settings.get("fullscreen", False)
                        else:
                            settings["vsync"] = not settings.get("vsync", True)
                        save_save(save_data)

                elif game_state == "gameplay_settings":
                    max_idx = len(config.GAMEPLAY_SLIDER_ORDER)
                    if event.key == pygame.K_UP:
                        gameplay_focus = max(0, gameplay_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        gameplay_focus = min(max_idx, gameplay_focus + 1)
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                        delta = -1 if event.key == pygame.K_LEFT else 1
                        if gameplay_focus == 0:
                            # Cycle difficulty
                            cur = settings.get("difficulty", "Normal")
                            names = config.DIFFICULTY_ORDER
                            new_name, _ = cycle_value(names, cur, delta if event.key in (pygame.K_LEFT, pygame.K_RIGHT) else 1)
                            settings["difficulty"] = new_name
                            preset = config.DIFFICULTY_PRESETS.get(new_name, {})
                            for k, v in preset.items():
                                settings[k] = v
                            save_save(save_data)
                        else:
                            key = config.GAMEPLAY_SLIDER_ORDER[gameplay_focus - 1]
                            adjust_setting(settings, config.GAMEPLAY_SLIDER_CONFIG, key, delta)
                            save_save(save_data)

                elif game_state == "audio_settings":
                    max_idx = len(config.AUDIO_SLIDER_ORDER) - 1
                    if event.key == pygame.K_UP:
                        audio_focus = max(0, audio_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        audio_focus = min(max_idx, audio_focus + 1)
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                        delta = -1 if event.key == pygame.K_LEFT else 1
                        key = config.AUDIO_SLIDER_ORDER[audio_focus]
                        adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, key, delta)
                        pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                        save_save(save_data)

                elif game_state == "skins_menu":
                    if event.key == pygame.K_LEFT:
                        skins_focus = (skins_focus - 1) % len(config.SKIN_LIST)
                    elif event.key == pygame.K_RIGHT:
                        skins_focus = (skins_focus + 1) % len(config.SKIN_LIST)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        skin_choice = config.SKIN_LIST[skins_focus]
                        unlocked = skin_choice in save_data["skins"]["unlocked"]
                        if not unlocked:
                            req_lvl = config.SKIN_UNLOCK_LEVEL.get(skin_choice, 1)
                            if max_level_reached(save_data) >= req_lvl:
                                save_data["skins"]["unlocked"].append(skin_choice)
                                unlocked = True
                        if unlocked:
                            save_data["skins"]["current_skin"] = skin_choice
                            skin_assets = skins_assets.get(skin_choice, skins_assets["default"])
                            skin_idle = skin_assets["idle"]
                            skin_run  = skin_assets["run"]
                            skin_jump = skin_assets["jump"]
                            save_save(save_data)

                elif game_state == "level_select":
                    max_idx = len(config.LEVEL_CONFIGS) - 1
                    if event.key == pygame.K_UP:
                        level_select_focus = max(0, level_select_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        level_select_focus = min(max_idx, level_select_focus + 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        chosen_level = level_select_focus + 1
                        wstate = reset_state(player_rect, player_h, max_health)
                        wstate["level"] = chosen_level
                        game_state = "playing"
                         # Load custom layout for this level, if defined
                        apply_custom_level_to_state(chosen_level, wstate, coin_img, enemy_sprites, scale_factor)
                        name, story = get_level_meta(chosen_level)
                        prefix = "BOSS LEVEL" if chosen_level in BOSS_LEVELS else "LEVEL"
                        level_intro_title = f"{prefix} {chosen_level}: {name}"
                        level_intro_story = story
                        level_intro_timer = 3.0

                elif game_state == "shop":
                    items = list(config.UPGRADE_COSTS.items())
                    if items:
                        if event.key == pygame.K_UP:
                            shop_focus = max(0, shop_focus - 1)
                        elif event.key == pygame.K_DOWN:
                            shop_focus = min(len(items) - 1, shop_focus + 1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            key, cost = items[shop_focus]
                            owned = save_data["upgrades"].get(key, False)
                            if not owned and save_data["total_coins"] >= cost:
                                save_data["total_coins"] -= cost
                                save_data["upgrades"][key] = True
                                if key == "extra_heart":
                                    max_health = BASE_MAX_HEALTH + 1
                                    wstate["max_health"] = max_health
                                    wstate["health"] = max_health
                                save_save(save_data)

                elif game_state == "paused":
                    if event.key == pygame.K_UP:
                        pause_focus = max(0, pause_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        pause_focus = min(2, pause_focus + 1)
                    elif event.key == pygame.K_LEFT:
                        adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, "music_volume", -1)
                        pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                        save_save(save_data)
                    elif event.key == pygame.K_RIGHT:
                        adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, "music_volume", +1)
                        pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                        save_save(save_data)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if pause_focus == 0:
                            game_state = "playing"
                        elif pause_focus == 1:
                            game_state = "menu"
                            menu_focus = 0
                        elif pause_focus == 2:
                            running = False

                elif game_state == "game_over":
                    if event.key == pygame.K_UP:
                        game_over_focus = max(0, game_over_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        game_over_focus = min(2, game_over_focus + 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if game_over_focus == 0:
                            wstate = reset_state(player_rect, player_h, max_health)
                            game_state = "playing"
                        elif game_over_focus == 1:
                            game_state = "menu"
                            menu_focus = 0
                        elif game_over_focus == 2:
                            running = False

                elif game_state == "controls_settings":
                    max_idx = len(CONTROL_ACTION_ORDER) - 1
                    if event.key == pygame.K_UP:
                        controls_focus = max(0, controls_focus - 1)
                    elif event.key == pygame.K_DOWN:
                        controls_focus = min(max_idx, controls_focus + 1)
                    elif event.key == pygame.K_TAB:
                        controls_mode = "controller" if controls_mode == "keyboard" else "keyboard"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        controls_waiting_action = CONTROL_ACTION_ORDER[controls_focus]
                        controls_waiting_mode = controls_mode

            # --- KEYUP ---
            if event.type == pygame.KEYUP:
                if action_down_kb("move_left", event.key, kb_cfg):
                    move_left_down = False
                elif action_down_kb("move_right", event.key, kb_cfg):
                    move_right_down = False
                elif action_down_kb("jump", event.key, kb_cfg):
                    jump_down = False
                elif action_down_kb("dash", event.key, kb_cfg):
                    dash_down = False

            # --- MOUSE BUTTON DOWN ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                if game_state == "level_editor":
                    # Editor placement logic
                    ex, ey = mx, my

                    # Optional snap-to-grid
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

                    # LEFT CLICK = place entities
                    if event.button == 1:
                        # Click on the Snap label toggles snapping instead of placing
                        if editor_info_snap_rect and editor_info_snap_rect.collidepoint(mx, my):
                            editor_grid_snap = not editor_grid_snap
                            editor_status_msg = f"Snap: {'ON' if editor_grid_snap else 'OFF'}"
                            editor_status_timer = 2.0
                            continue

                        # Click inside the left palette starts a drag from that asset
                        started_drag = False
                        if editor_palette_rect and editor_palette_rect.collidepoint(mx, my):
                            # Platforms
                            for ptype, r in editor_palette_platform_rects:
                                if r.collidepoint(mx, my):
                                    editor_drag_active = True
                                    editor_drag_kind = "platform"
                                    editor_drag_payload = ptype
                                    editor_drag_from_palette = True
                                    editor_drag_target = None
                                    editor_tool = "platform"
                                    editor_platform_type = ptype
                                    editor_status_msg = f"Drag: platform ({ptype})"
                                    editor_status_timer = 2.0
                                    started_drag = True
                                    break

                            # Coin
                            if not started_drag and editor_palette_coin_rect and editor_palette_coin_rect.collidepoint(mx, my):
                                editor_drag_active = True
                                editor_drag_kind = "coin"
                                editor_drag_payload = None
                                editor_drag_from_palette = True
                                editor_drag_target = None
                                editor_tool = "coin"
                                editor_status_msg = "Drag: coin"
                                editor_status_timer = 2.0
                                started_drag = True

                            # Enemies
                            if not started_drag:
                                for kind, r in editor_palette_enemy_rects:
                                    if r.collidepoint(mx, my):
                                        editor_drag_active = True
                                        editor_drag_kind = "enemy"
                                        editor_drag_payload = kind
                                        editor_drag_from_palette = True
                                        editor_drag_target = None
                                        editor_tool = "enemy"
                                        editor_enemy_kind = kind
                                        editor_status_msg = f"Drag: enemy ({kind})"
                                        editor_status_timer = 2.0
                                        started_drag = True
                                        break

                        if started_drag:
                            continue

                        # Left-click on existing objects starts a move-drag instead of placing new
                        nearest = None
                        best_dist2 = (40 * scale_factor) ** 2

                        # Platforms
                        for i, p in enumerate(editor_data["platforms"]):
                            cx = p["x"] + p["w"] / 2
                            cy = p["y"] + p["h"] / 2
                            d2 = (cx - ex) ** 2 + (cy - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("platforms", i)

                        # Coins
                        for i, c in enumerate(editor_data["coins"]):
                            d2 = (c["x"] - ex) ** 2 + (c["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("coins", i)

                        # Enemies
                        for i, e in enumerate(editor_data["enemies"]):
                            d2 = (e["x"] - ex) ** 2 + (e["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("enemies", i)

                        if nearest:
                            arr, idx = nearest
                            editor_push_undo(editor_undo_stack, editor_data)
                            editor_redo_stack.clear()
                            editor_drag_active = True
                            editor_drag_from_palette = False
                            editor_drag_target = (arr, idx)
                            if arr == "platforms":
                                editor_drag_kind = "platform"
                                editor_tool = "platform"
                            elif arr == "coins":
                                editor_drag_kind = "coin"
                                editor_tool = "coin"
                            else:
                                editor_drag_kind = "enemy"
                                editor_tool = "enemy"
                                editor_enemy_kind = editor_data["enemies"][idx]["kind"]
                            editor_status_msg = "Drag: move existing"
                            editor_status_timer = 2.0
                            continue

                        if editor_tool == "platform":
                            w = editor_platform_width
                            h = editor_platform_height
                            plat = {
                                "x": ex - w // 2,
                                "y": ey - h // 2,
                                "w": w,
                                "h": h,
                                "type": editor_platform_type,
                            }
                            editor_data["platforms"].append(plat)

                        elif editor_tool == "coin":
                            editor_data["coins"].append({"x": ex, "y": ey})

                        elif editor_tool == "enemy":
                            editor_data["enemies"].append({
                                "x": ex,
                                "y": ey,
                                "kind": editor_enemy_kind,
                            })

                    # RIGHT CLICK = delete nearest
                    elif event.button == 3:
                        nearest = None
                        best_dist2 = (40 * scale_factor) ** 2

                        # Platforms
                        for i, p in enumerate(editor_data["platforms"]):
                            cx = p["x"] + p["w"] / 2
                            cy = p["y"] + p["h"] / 2
                            d2 = (cx - ex) ** 2 + (cy - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("platforms", i)

                        # Coins
                        for i, c in enumerate(editor_data["coins"]):
                            d2 = (c["x"] - ex) ** 2 + (c["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("coins", i)

                        # Enemies
                        for i, e in enumerate(editor_data["enemies"]):
                            d2 = (e["x"] - ex) ** 2 + (e["y"] - ey) ** 2
                            if d2 < best_dist2:
                                best_dist2 = d2
                                nearest = ("enemies", i)

                        if nearest:
                            arr, idx = nearest
                            del editor_data[arr][idx]

                    # MOUSE WHEEL = cycle assets for current tool
                    elif event.button in (4, 5):
                        direction = -1 if event.button == 4 else 1
                        # Scroll over top info categories changes that category
                        if editor_info_tool_rect and editor_info_tool_rect.collidepoint(mx, my):
                            tools = ["platform", "coin", "enemy"]
                            i = tools.index(editor_tool)
                            editor_tool = tools[(i + direction) % len(tools)]
                            editor_status_msg = f"Tool: {editor_tool}"
                            editor_status_timer = 2.0

                        elif editor_info_plat_rect and editor_info_plat_rect.collidepoint(mx, my):
                            types = list(config.PLATFORM_TYPE_CONFIG.keys())
                            if types:
                                i = types.index(editor_platform_type)
                                editor_platform_type = types[(i + direction) % len(types)]
                                editor_status_msg = f"Platform: {editor_platform_type}"
                                editor_status_timer = 2.0

                        elif editor_info_enemy_rect and editor_info_enemy_rect.collidepoint(mx, my):
                            kinds = list(config.ENEMY_CONFIG.keys())
                            if kinds:
                                i = kinds.index(editor_enemy_kind)
                                editor_enemy_kind = kinds[(i + direction) % len(kinds)]
                                editor_status_msg = f"Enemy: {editor_enemy_kind}"
                                editor_status_timer = 2.0

                        elif editor_info_snap_rect and editor_info_snap_rect.collidepoint(mx, my):
                            editor_grid_snap = not editor_grid_snap
                            editor_status_msg = f"Snap: {'ON' if editor_grid_snap else 'OFF'}"
                            editor_status_timer = 2.0

                        # Otherwise, fall back to changing based on current tool
                        elif editor_tool == "platform":
                            types = list(config.PLATFORM_TYPE_CONFIG.keys())
                            if types:
                                i = types.index(editor_platform_type)
                                editor_platform_type = types[(i + direction) % len(types)]
                                editor_status_msg = f"Platform: {editor_platform_type}"
                                editor_status_timer = 2.0
                        elif editor_tool == "enemy":
                            kinds = list(config.ENEMY_CONFIG.keys())
                            if kinds:
                                i = kinds.index(editor_enemy_kind)
                                editor_enemy_kind = kinds[(i + direction) % len(kinds)]
                                editor_status_msg = f"Enemy: {editor_enemy_kind}"
                                editor_status_timer = 2.0

                    # Don’t let menu clicks fall through when in editor
                    continue

            # --- MOUSE MOTION ---
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos

                if game_state == "level_editor" and editor_drag_active and editor_drag_target:
                    # Move an existing object while dragging
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

                    arr, idx = editor_drag_target
                    if arr == "platforms" and 0 <= idx < len(editor_data["platforms"]):
                        p = editor_data["platforms"][idx]
                        w = p["w"]
                        h = p["h"]
                        p["x"] = ex - w // 2
                        p["y"] = ey - h // 2
                    elif arr == "coins" and 0 <= idx < len(editor_data["coins"]):
                        c = editor_data["coins"][idx]
                        c["x"] = ex
                        c["y"] = ey
                    elif arr == "enemies" and 0 <= idx < len(editor_data["enemies"]):
                        e = editor_data["enemies"][idx]
                        e["x"] = ex
                        e["y"] = ey

            # --- MOUSE BUTTON UP ---
            if event.type == pygame.MOUSEBUTTONUP:
                mx, my = event.pos

                if game_state == "level_editor" and event.button == 1 and editor_drag_active:
                    # Finish a drag (palette or existing)
                    ex, ey = mx, my

                    # If dropped back onto the palette, cancel without placing
                    if editor_palette_rect and editor_palette_rect.collidepoint(mx, my):
                        editor_drag_active = False
                        editor_drag_kind = None
                        editor_drag_payload = None
                        editor_drag_target = None
                        editor_drag_from_palette = False
                    else:
                        # Snap to grid on drop if enabled
                        if editor_drag_from_palette:
                            # New placement from palette
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

                            editor_push_undo(editor_undo_stack, editor_data)
                            editor_redo_stack.clear()

                            if editor_drag_kind == "platform":
                                ptype = editor_drag_payload or editor_platform_type
                                w = editor_platform_width
                                h = editor_platform_height
                                plat = {
                                    "x": ex - w // 2,
                                    "y": ey - h // 2,
                                    "w": w,
                                    "h": h,
                                    "type": ptype,
                                }
                                editor_data["platforms"].append(plat)
                                editor_status_msg = f"Placed platform ({ptype})"
                                editor_status_timer = 2.0

                            elif editor_drag_kind == "coin":
                                editor_data["coins"].append({"x": ex, "y": ey})
                                editor_status_msg = "Placed coin"
                                editor_status_timer = 2.0

                            elif editor_drag_kind == "enemy":
                                kind = editor_drag_payload or editor_enemy_kind
                                editor_data["enemies"].append({
                                    "x": ex,
                                    "y": ey,
                                    "kind": kind,
                                })
                                editor_status_msg = f"Placed enemy ({kind})"
                                editor_status_timer = 2.0

                        else:
                            # Dropped an existing object after move
                            editor_status_msg = "Moved object"
                            editor_status_timer = 2.0

                        editor_drag_active = False
                        editor_drag_kind = None
                        editor_drag_payload = None
                        editor_drag_target = None
                        editor_drag_from_palette = False

                if event.button == 1:
                    if game_state == "menu":
                        for i, r in enumerate(menu_button_rects):
                            if r.collidepoint(mx, my):
                                menu_focus = i
                                item_id = config.MAIN_MENU_ITEMS[i]["id"]
                                if item_id == "play":
                                    game_state = "playing"
                                    wstate.update(reset_state(player_rect, player_h, max_health))
                                elif item_id == "level_select":
                                    game_state = "level_select"
                                    level_select_focus = 0
                                elif item_id == "settings":
                                    game_state = "settings_menu"
                                    settings_menu_focus = 0
                                elif item_id == "level_editor":
                                    game_state = "level_editor"
                                    editor_data = editor_load_level(editor_level)
                                elif item_id == "high_scores":
                                    game_state = "high_scores"
                                    high_scores_focus = 0
                                elif item_id == "skins":
                                    game_state = "skins_menu"
                                    skins_focus = 0
                                elif item_id == "how_to_play":
                                    game_state = "how_to_play"
                                elif item_id == "quit":
                                    running = False
                                break

                    elif game_state == "paused":
                        for i, r in enumerate(pause_option_rects):
                            if r.collidepoint(mx, my):
                                pause_focus = i
                                if pause_focus == 0:
                                    game_state = "playing"
                                elif pause_focus == 1:
                                    game_state = "menu"
                                    menu_focus = 0
                                elif pause_focus == 2:
                                    running = False
                                break

                    elif game_state == "game_over":
                        for i, r in enumerate(game_over_option_rects):
                            if r.collidepoint(mx, my):
                                game_over_focus = i
                                if game_over_focus == 0:
                                    wstate = reset_state(player_rect, player_h, max_health)
                                    game_state = "playing"
                                elif game_over_focus == 1:
                                    game_state = "menu"
                                    menu_focus = 0
                                elif game_over_focus == 2:
                                    running = False
                                break

                    elif game_state == "settings_menu":
                        for i, r in enumerate(settings_menu_rects):
                            if r.collidepoint(mx, my):
                                settings_menu_focus = i
                                entry = SETTINGS_MENU_ITEMS[settings_menu_focus]
                                sid = entry["id"]
                                if sid == "display_settings":
                                    game_state = "display_settings"
                                    display_focus = 0
                                elif sid == "gameplay_settings":
                                    game_state = "gameplay_settings"
                                    gameplay_focus = 0
                                elif sid == "audio_settings":
                                    game_state = "audio_settings"
                                    audio_focus = 0
                                elif sid == "controls_settings":
                                    game_state = "controls_settings"
                                    controls_focus = 0
                                elif sid == "skins_menu":
                                    game_state = "skins_menu"
                                    skins_focus = 0
                                elif sid == "level_editor":
                                    game_state = "level_editor"
                                    editor_data = editor_load_level(editor_level)
                                elif sid == "shop":
                                    game_state = "shop"
                                    shop_focus = 0
                                elif sid == "high_scores":
                                    game_state = "high_scores"
                                    high_scores_focus = 0
                                elif sid == "how_to_play":
                                    game_state = "how_to_play"
                                elif sid == "back":
                                    game_state = "menu"
                                    menu_focus = 0
                                break

                    elif game_state == "shop":
                        for i, r in enumerate(shop_item_rects):
                            if r.collidepoint(mx, my):
                                shop_focus = i
                                items = list(config.UPGRADE_COSTS.items())
                                if i < len(items):
                                    key, cost = items[i]
                                    owned = save_data["upgrades"].get(key, False)
                                    if not owned and save_data["total_coins"] >= cost:
                                        save_data["total_coins"] -= cost
                                        save_data["upgrades"][key] = True
                                        if key == "extra_heart":
                                            max_health = BASE_MAX_HEALTH + 1
                                            wstate["max_health"] = max_health
                                            wstate["health"] = max_health
                                        save_save(save_data)
                                break

                    elif game_state == "display_settings":
                        # Click rows to change resolution / fullscreen
                        for i, r in enumerate(display_row_rects):
                            if r.collidepoint(mx, my):
                                display_focus = i
                                res, _ = cycle_value(
                                    config.SUPPORTED_RESOLUTIONS,
                                    settings.get("resolution", config.DEFAULT_RESOLUTION),
                                    1
                                )
                                settings["resolution"] = res
                                save_save(save_data)
                                break
                        else:
                            # Fullscreen toggle
                            if display_fullscreen_rect and display_fullscreen_rect.collidepoint(mx, my):
                                display_focus = len(config.SUPPORTED_RESOLUTIONS)
                                settings["fullscreen"] = not settings.get("fullscreen", False)
                                save_save(save_data)
                            # VSync toggle
                            elif 'display_vsync_rect' in locals() and display_vsync_rect and display_vsync_rect.collidepoint(mx, my):
                                display_focus = len(config.SUPPORTED_RESOLUTIONS) + 1
                                settings["vsync"] = not settings.get("vsync", True)
                                save_save(save_data)

                    elif game_state == "gameplay_settings":
                        for i, r in enumerate(gameplay_row_rects):
                            if r.collidepoint(mx, my):
                                gameplay_focus = i
                                key = config.GAMEPLAY_SLIDER_ORDER[gameplay_focus]
                                adjust_setting(settings, config.GAMEPLAY_SLIDER_CONFIG, key, 1)
                                save_save(save_data)
                                break

                    elif game_state == "audio_settings":
                        for i, r in enumerate(audio_row_rects):
                            if r.collidepoint(mx, my):
                                audio_focus = i
                                key = config.AUDIO_SLIDER_ORDER[audio_focus]
                                adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, key, 1)
                                pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                                save_save(save_data)
                                break

                    elif game_state == "skins_menu":
                        # Click left/right half of the card area to cycle, click title to select
                        card_w = int(420 * scale_factor)
                        card_h = int(220 * scale_factor)
                        card = pygame.Rect(
                            screen_w // 2 - card_w // 2,
                            int(220 * scale_factor),
                            card_w,
                            card_h
                        )
                        if card.collidepoint(mx, my):
                            if mx < card.centerx:
                                skins_focus = (skins_focus - 1) % len(config.SKIN_LIST)
                            else:
                                skins_focus = (skins_focus + 1) % len(config.SKIN_LIST)
                        else:
                            # Click title text area to confirm selection
                            title_rect = pygame.Rect(
                                0,
                                int(120 * scale_factor),
                                screen_w,
                                int(60 * scale_factor),
                            )
                            if title_rect.collidepoint(mx, my):
                                skin_choice = config.SKIN_LIST[skins_focus]
                                unlocked = skin_choice in save_data["skins"]["unlocked"]
                                if not unlocked:
                                    req_lvl = config.SKIN_UNLOCK_LEVEL.get(skin_choice, 1)
                                    if max_level_reached(save_data) >= req_lvl:
                                        save_data["skins"]["unlocked"].append(skin_choice)
                                        unlocked = True
                                if unlocked:
                                    save_data["skins"]["current_skin"] = skin_choice
                                    skin_assets = skins_assets.get(skin_choice, skins_assets["default"])
                                    skin_idle = skin_assets["idle"]
                                    skin_run  = skin_assets["run"]
                                    skin_jump = skin_assets["jump"]
                                    save_save(save_data)

                    elif game_state == "level_select":
                        for level_idx, r in level_row_rects:
                            if r.collidepoint(mx, my):
                                level_select_focus = level_idx
                                chosen_level = level_idx + 1
                                wstate = reset_state(player_rect, player_h, max_health)
                                wstate["level"] = chosen_level
                                game_state = "playing"
                                apply_custom_level_to_state(chosen_level, wstate, coin_img, enemy_sprites, scale_factor)
                                name, story = get_level_meta(chosen_level)
                                prefix = "BOSS LEVEL" if chosen_level in BOSS_LEVELS else "LEVEL"
                                level_intro_title = f"{prefix} {chosen_level}: {name}"
                                level_intro_story = story
                                level_intro_timer = 3.0
                                break

                    elif game_state == "high_scores":
                        # Any click closes high scores back to main menu
                        game_state = "menu"
                        menu_focus = 0

                    elif game_state == "controls_settings":
                        for i, r in enumerate(controls_row_rects):
                            if r.collidepoint(mx, my):
                                controls_focus = i
                                controls_waiting_action = CONTROL_ACTION_ORDER[controls_focus]
                                controls_waiting_mode = controls_mode
                                break


            # --- CONTROLLER ---
            if event.type == pygame.JOYBUTTONDOWN:
                # If we're remapping controller input, capture this as the new binding
                if game_state == "controls_settings" and controls_waiting_action is not None and controls_waiting_mode == "controller":
                    code = controller_button_name(event.button)
                    ctr_cfg.setdefault(controls_waiting_action, [])
                    ctr_cfg[controls_waiting_action] = [code]
                    save_data.setdefault("input", {})
                    save_data["input"]["controller"] = ctr_cfg
                    save_save(save_data)
                    controls_waiting_action = None
                    controls_waiting_mode = None
                else:
                    btn_event = event
            elif event.type == pygame.JOYHATMOTION:
                # If we're remapping controller input, capture D-pad direction
                if game_state == "controls_settings" and controls_waiting_action is not None and controls_waiting_mode == "controller":
                    hx, hy = event.value
                    code = hat_direction_name(hx, hy)
                    if code is not None:
                        ctr_cfg.setdefault(controls_waiting_action, [])
                        ctr_cfg[controls_waiting_action] = [code]
                        save_data.setdefault("input", {})
                        save_data["input"]["controller"] = ctr_cfg
                        save_save(save_data)
                        controls_waiting_action = None
                        controls_waiting_mode = None
                else:
                    hat_event = event



        # ----------------------------------------------------
        # CONTROLLER EVENTS (continued)
        # ----------------------------------------------------
        if hat_event is not None:
            hx, hy = hat_event.value

            if game_state == "menu":
                if hy > 0:
                    menu_focus = max(0, menu_focus - 1)
                elif hy < 0:
                    menu_focus = min(len(config.MAIN_MENU_ITEMS) - 1, menu_focus + 1)

            elif game_state == "display_settings":
                res_count = len(config.SUPPORTED_RESOLUTIONS)
                max_focus = res_count + 1
                if hy > 0:
                    display_focus = max(0, display_focus - 1)
                elif hy < 0:
                    display_focus = min(max_focus, display_focus + 1)

                if hx != 0:
                    if display_focus < res_count:
                        res, _ = cycle_value(
                            config.SUPPORTED_RESOLUTIONS,
                            settings.get("resolution", config.DEFAULT_RESOLUTION),
                            hx
                        )
                        settings["resolution"] = res
                    elif display_focus == res_count:
                        settings["fullscreen"] = not settings.get("fullscreen", False)
                    else:
                        settings["vsync"] = not settings.get("vsync", True)
                    save_save(save_data)

            elif game_state == "gameplay_settings":
                max_idx = len(config.GAMEPLAY_SLIDER_ORDER) - 1
                if hy > 0:
                    gameplay_focus = max(0, gameplay_focus - 1)
                elif hy < 0:
                    gameplay_focus = min(max_idx, gameplay_focus + 1)
                if hx != 0:
                    key = config.GAMEPLAY_SLIDER_ORDER[gameplay_focus]
                    adjust_setting(settings, config.GAMEPLAY_SLIDER_CONFIG, key, hx)
                    save_save(save_data)

            elif game_state == "audio_settings":
                max_idx = len(config.AUDIO_SLIDER_ORDER) - 1
                if hy > 0:
                    audio_focus = max(0, audio_focus - 1)
                elif hy < 0:
                    audio_focus = min(max_idx, audio_focus + 1)
                if hx != 0:
                    key = config.AUDIO_SLIDER_ORDER[audio_focus]
                    adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, key, hx)
                    pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                    save_save(save_data)

            elif game_state == "skins_menu":
                if hx != 0:
                    skins_focus = (skins_focus + hx) % len(config.SKIN_LIST)

            elif game_state == "level_select":
                if hy > 0:
                    level_select_focus = max(0, level_select_focus - 1)
                elif hy < 0:
                    level_select_focus = min(len(config.LEVEL_CONFIGS) - 1, level_select_focus + 1)

            elif game_state == "settings_menu":
                if hy > 0:
                    settings_menu_focus = max(0, settings_menu_focus - 1)
                elif hy < 0:
                    settings_menu_focus = min(len(SETTINGS_MENU_ITEMS) - 1, settings_menu_focus + 1)

            elif game_state == "shop":
                items = list(config.UPGRADE_COSTS.items())
                if items:
                    if hy > 0:
                        shop_focus = max(0, shop_focus - 1)
                    elif hy < 0:
                        shop_focus = min(len(items) - 1, shop_focus + 1)

            elif game_state == "paused":
                if hy > 0:
                    pause_focus = max(0, pause_focus - 1)
                elif hy < 0:
                    pause_focus = min(2, pause_focus + 1)

            elif game_state == "game_over":
                if hy > 0:
                    game_over_focus = max(0, game_over_focus - 1)
                elif hy < 0:
                    game_over_focus = min(2, game_over_focus + 1)

        if btn_event is not None:
            # Handle controller input in menus and gameplay
            if game_state == "playing" and btn_event.button == BTN_START:
                game_state = "paused"
                pause_focus = 0

            if game_state == "menu":
                if btn_event.button == BTN_A:
                    item_id = config.MAIN_MENU_ITEMS[menu_focus]["id"]
                    if item_id == "play":
                        game_state = "playing"
                        wstate = reset_state(player_rect, player_h, max_health)
                        wstate["level"] = 1
                        apply_custom_level_to_state(1, wstate, coin_img, enemy_sprites, scale_factor)
                        name, story = get_level_meta(1)
                        level_intro_title = f"LEVEL 1: {name}"
                        level_intro_story = story
                        level_intro_timer = 3.0
                    elif item_id == "level_select":
                        game_state = "level_select"
                        level_select_focus = 0
                    elif item_id == "level_editor":
                        game_state = "level_editor"
                        editor_data = editor_load_level(editor_level)
                    elif item_id == "shop":
                        game_state = "shop"
                        shop_focus = 0
                    elif item_id == "high_scores":
                        game_state = "high_scores"
                        high_scores_focus = 0
                    elif item_id == "display_settings":
                        game_state = "display_settings"
                        display_focus = 0
                    elif item_id == "gameplay_settings":
                        game_state = "gameplay_settings"
                        gameplay_focus = 0
                    elif item_id == "audio_settings":
                        game_state = "audio_settings"
                        audio_focus = 0
                    elif item_id == "skins":
                        game_state = "skins_menu"
                        skins_focus = 0
                    elif item_id == "quit":
                        running = False

                elif btn_event.button == BTN_B:
                    running = False

            elif game_state == "display_settings":
                if btn_event.button == BTN_A:
                    res_count = len(config.SUPPORTED_RESOLUTIONS)
                    if display_focus < res_count:
                        res, _ = cycle_value(
                            config.SUPPORTED_RESOLUTIONS,
                            settings.get("resolution", config.DEFAULT_RESOLUTION),
                            1
                        )
                        settings["resolution"] = res
                    elif display_focus == res_count:
                        settings["fullscreen"] = not settings.get("fullscreen", False)
                    else:
                        settings["vsync"] = not settings.get("vsync", True)
                    save_save(save_data)
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "gameplay_settings":
                if btn_event.button == BTN_A:
                    if gameplay_focus == 0:
                        cur = settings.get("difficulty", "Normal")
                        names = config.DIFFICULTY_ORDER
                        new_name, _ = cycle_value(names, cur, 1)
                        settings["difficulty"] = new_name
                        preset = config.DIFFICULTY_PRESETS.get(new_name, {})
                        for k, v in preset.items():
                            settings[k] = v
                        save_save(save_data)
                    else:
                        key = config.GAMEPLAY_SLIDER_ORDER[gameplay_focus - 1]
                        adjust_setting(settings, config.GAMEPLAY_SLIDER_CONFIG, key, 1)
                        save_save(save_data)
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "audio_settings":
                if btn_event.button == BTN_A:
                    key = config.AUDIO_SLIDER_ORDER[audio_focus]
                    adjust_setting(settings, config.AUDIO_SLIDER_CONFIG, key, 1)
                    pygame.mixer.music.set_volume(settings.get("music_volume", 0.5))
                    save_save(save_data)
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "skins_menu":
                if btn_event.button == BTN_A:
                    skin_choice = config.SKIN_LIST[skins_focus]
                    unlocked = skin_choice in save_data["skins"]["unlocked"]
                    if not unlocked:
                        req_lvl = config.SKIN_UNLOCK_LEVEL.get(skin_choice, 1)
                        if max_level_reached(save_data) >= req_lvl:
                            save_data["skins"]["unlocked"].append(skin_choice)
                            unlocked = True
                    if unlocked:
                        save_data["skins"]["current_skin"] = skin_choice
                        skin_assets = skins_assets.get(skin_choice, skins_assets["default"])
                        skin_idle = skin_assets["idle"]
                        skin_run  = skin_assets["run"]
                        skin_jump = skin_assets["jump"]
                        save_save(save_data)
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "controls_settings":
                if btn_event.button == BTN_A:
                    controls_waiting_action = CONTROL_ACTION_ORDER[controls_focus]
                    controls_waiting_mode = "controller"
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "level_select":
                if btn_event.button == BTN_A:
                    chosen_level = level_select_focus + 1
                    wstate = reset_state(player_rect, player_h, max_health)
                    wstate["level"] = chosen_level
                    game_state = "playing"
                    apply_custom_level_to_state(chosen_level, wstate, coin_img, enemy_sprites, scale_factor)
                    name, story = get_level_meta(chosen_level)
                    prefix = "BOSS LEVEL" if chosen_level in BOSS_LEVELS else "LEVEL"
                    level_intro_title = f"{prefix} {chosen_level}: {name}"
                    level_intro_story = story
                    level_intro_timer = 3.0
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "shop":
                items = list(config.UPGRADE_COSTS.items())
                if btn_event.button == BTN_A and items:
                    key, cost = items[shop_focus]
                    owned = save_data["upgrades"].get(key, False)
                    if not owned and save_data["total_coins"] >= cost:
                        save_data["total_coins"] -= cost
                        save_data["upgrades"][key] = True
                        if key == "extra_heart":
                            max_health = BASE_MAX_HEALTH + 1
                            wstate["max_health"] = max_health
                            wstate["health"] = max_health
                        save_save(save_data)
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "paused":
                if btn_event.button == BTN_A:
                    if pause_focus == 0:
                        game_state = "playing"
                    elif pause_focus == 1:
                        game_state = "menu"
                        menu_focus = 0
                    elif pause_focus == 2:
                        running = False
                elif btn_event.button == BTN_B:
                    game_state = "playing"

            elif game_state == "game_over":
                if btn_event.button == BTN_A:
                    if game_over_focus == 0:
                        wstate = reset_state(player_rect, player_h, max_health)
                        game_state = "playing"
                    elif game_over_focus == 1:
                        game_state = "menu"
                        menu_focus = 0
                    elif game_over_focus == 2:
                        running = False
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "high_scores":
                if btn_event.button in (BTN_A, BTN_B):
                    game_state = "menu"
                    menu_focus = 0

            elif game_state == "settings_menu":
                if btn_event.button == BTN_A:
                    # Reuse keyboard handler by simulating Enter on current focus
                    entry = SETTINGS_MENU_ITEMS[settings_menu_focus]
                    sid = entry["id"]
                    if sid == "display_settings":
                        game_state = "display_settings"
                        display_focus = 0
                    elif sid == "gameplay_settings":
                        game_state = "gameplay_settings"
                        gameplay_focus = 0
                    elif sid == "audio_settings":
                        game_state = "audio_settings"
                        audio_focus = 0
                    elif sid == "controls_settings":
                        game_state = "controls_settings"
                        controls_focus = 0
                    elif sid == "skins_menu":
                        game_state = "skins_menu"
                        skins_focus = 0
                    elif sid == "level_editor":
                        game_state = "level_editor"
                        editor_data = editor_load_level(editor_level)
                    elif sid == "shop":
                        game_state = "shop"
                        shop_focus = 0
                    elif sid == "high_scores":
                        game_state = "high_scores"
                        high_scores_focus = 0
                    elif sid == "how_to_play":
                        game_state = "how_to_play"
                    elif sid == "back":
                        game_state = "menu"
                        menu_focus = 0
                elif btn_event.button == BTN_B:
                    game_state = "menu"
                    menu_focus = 0

        # =====================================================
        #   RENDER BACKGROUND
        # =====================================================
        game_surface.fill(config.SKY_COLOR)

        # Pick world theme based on current level
        cur_level = wstate.get("level", 1)
        world_id, world_cfg = get_world_for_level(cur_level, config.WORLD_PACKS)
        world_scroll_mult = world_cfg.get("scroll_speed_mult", 1.0) if world_cfg else 1.0

        active_backgrounds = world_backgrounds.get(world_id) or backgrounds

        # Scroll backgrounds
        base_scroll_speed = GAME_SPEED_BASE * settings["game_speed_mult"] * world_scroll_mult

        for i, layer_set in enumerate(active_backgrounds):
            offs = scroll_offsets[i]

            near_speed = base_scroll_speed * 1.0
            mid_speed  = base_scroll_speed * 0.4
            far_speed  = base_scroll_speed * 0.2

            offs["near"] += near_speed * dt_scaled
            offs["mid"]  += mid_speed  * dt_scaled
            offs["far"]  += far_speed  * dt_scaled

            for key in ("far", "mid", "near"):
                img = layer_set.get(key)
                if img:
                    w = img.get_width()
                    x1 = -offs[key] % w
                    x2 = x1 - w
                    game_surface.blit(img, (x1, 0))
                    game_surface.blit(img, (x2, 0))

        # =====================================================
        #   GAMESTATE: PLAYING
        # =====================================================
        if game_state == "playing":

            # Get variables from world state
            player_rect = player_rect
            player_vel_y = wstate["player_vel_y"]
            on_ground = wstate["on_ground"]
            was_on_ground = wstate["was_on_ground"]

            coins_list = wstate["coins"]
            trees_list = wstate["trees"]
            plats_list = wstate["platforms"]
            enemies_list = wstate["enemies"]

            dust_particles = wstate["dust_particles"]
            spark_particles = wstate["spark_particles"]

            health = wstate["health"]
            max_health = wstate["max_health"]

            score_time = wstate["score_time"]
            coins_collected_run = wstate["coins_collected_run"]
            level = wstate["level"]

            # World theme multipliers for this level
            _, world_cfg = get_world_for_level(level, config.WORLD_PACKS)
            world_scroll_mult = world_cfg.get("scroll_speed_mult", 1.0) if world_cfg else 1.0
            world_enemy_spawn_mult = world_cfg.get("enemy_spawn_mult", 1.0) if world_cfg else 1.0
            world_enemy_damage_mult = world_cfg.get("enemy_damage_mult", 1.0) if world_cfg else 1.0

            inv_timer = wstate["invincible_timer"]
            knock_timer = wstate["knockback_timer"]
            knock_dx = wstate["knockback_dx"]

            dash_timer = wstate["dash_timer"]
            dash_cooldown = wstate["dash_cooldown"]
            dash_dir = wstate["dash_dir"]

            shake_timer = wstate["shake_timer"]
            run_dust_timer = wstate.get("run_dust_timer", 0.0)
            dash_trail_timer = wstate.get("dash_trail_timer", 0.0)

            # ------------------------------------------------
            # Player Movement
            # ------------------------------------------------
            move_x = 0
            if move_left_down:
                move_x -= 1
            if move_right_down:
                move_x += 1

            if move_x != 0:
                move_x *= PLAYER_MOVE_SPEED * settings["move_speed_mult"] * dt_scaled

            # Jump
            if jump_down:
                if on_ground:
                    player_vel_y = JUMP_STRENGTH * settings["jump_mult"]
                    on_ground = False
                    wstate["jump_count"] = 1
                    if jump_snd:
                        jump_snd.play()
                else:
                    if save_data["upgrades"]["double_jump"] and wstate["jump_count"] == 1:
                        player_vel_y = JUMP_STRENGTH * 0.9 * settings["jump_mult"]
                        wstate["jump_count"] = 2
                        if jump_snd:
                            jump_snd.play()

            # Gravity
            player_vel_y += GRAVITY * settings["gravity_mult"] * dt_scaled
            player_rect.y += int(player_vel_y * dt_scaled)

            # ------------------------------------------------
            # DASH
            # ------------------------------------------------
            dash_active = dash_timer > 0.0
            if dash_active:
                player_rect.x += int(dash_dir * DASH_SPEED * dt_scaled)
                dash_timer -= dt_scaled
            else:
                if dash_down and dash_cooldown <= 0.0:
                    dash_timer = DASH_DURATION
                    dash_cooldown = DASH_COOLDOWN
                    dash_dir = -1 if move_x < 0 else 1 if move_x > 0 else 1

            dash_cooldown -= dt_scaled
            if dash_cooldown < 0:
                dash_cooldown = 0

            # Regular x-movement (outside dash)
            player_rect.x += int(move_x)

            # Clamp x
            player_rect.x = clamp(player_rect.x, int(40 * scale_factor), screen_w - player_rect.width)

            # ------------------------------------------------
            # Collision with ground
            # ------------------------------------------------
            ground_y = int(screen_h * config.GROUND_Y_RATIO) - player_rect.height
            if player_rect.y >= ground_y:
                player_rect.y = ground_y
                if not on_ground:
                    if land_snd:
                        land_snd.play()
                    dust_particles.extend(spawn_dust_particles(
                        player_rect.centerx, player_rect.bottom, scale_factor,
                        settings["particle_density"]
                    ))
                on_ground = True
                player_vel_y = 0
            else:
                on_ground = False

            # ------------------------------------------------
            # Platforms update
            # ------------------------------------------------
            new_plats = []
            for p in plats_list:
                r = p["rect"]

                # Move platforms
                r.x -= int((GAME_SPEED_BASE * settings["game_speed_mult"]) * dt_scaled)
                r.x += int(p["vx"] * dt_scaled)

                # Update falling
                if p["type"] == "fall":
                    if p["fall_started"]:
                        p["fall_timer"] += dt_scaled
                        if p["fall_timer"] > config.PLATFORM_TYPE_CONFIG["fall"]["fall_delay"]:
                            p["vy"] += GRAVITY * 0.9 * dt_scaled
                            r.y += int(p["vy"] * dt_scaled)
                # Fragile logic
                if p["type"] == "fragile":
                    if p["fragile_hits"] >= config.PLATFORM_TYPE_CONFIG["fragile"]["hits_to_break"]:
                        continue

                if r.right < -200 or r.top > screen_h + 200:
                    continue
                new_plats.append(p)
            plats_list = new_plats

            # Stand on platform?
            for p in plats_list:
                r = p["rect"]
                if (
                    player_rect.bottom <= r.top + 10 and
                    player_rect.bottom >= r.top - 15 and
                    r.left < player_rect.centerx < r.right and
                    player_vel_y >= 0
                ):
                    player_rect.bottom = r.top
                    player_vel_y = 0
                    if not on_ground:
                        dust_particles.extend(spawn_dust_particles(
                            player_rect.centerx, player_rect.bottom, scale_factor,
                            settings["particle_density"]
                        ))
                    on_ground = True

                    # Bounce platforms
                    if p["type"] == "bounce":
                        player_vel_y = JUMP_STRENGTH * config.PLATFORM_TYPE_CONFIG["bounce"]["bounce_mult"]
                    # Fall platforms
                    elif p["type"] == "fall":
                        p["fall_started"] = True
                    # Fragile
                    elif p["type"] == "fragile":
                        p["fragile_hits"] += 1

            # ------------------------------------------------
            # RUN / DASH DUST TRAILS
            # ------------------------------------------------
            if settings.get("particles_enabled", True):
                run_dust_timer -= dt_scaled
                dash_trail_timer -= dt_scaled

                # Light dust while running on the ground
                if on_ground and move_x != 0 and run_dust_timer <= 0.0:
                    dust_particles.extend(
                        spawn_dust_particles(
                            player_rect.centerx,
                            player_rect.bottom,
                            scale_factor,
                            density="low",
                        )
                    )
                    run_dust_timer = RUN_DUST_INTERVAL

                # Heavier trail while dashing on the ground
                if dash_active and on_ground and dash_trail_timer <= 0.0:
                    dust_particles.extend(
                        spawn_dust_particles(
                            player_rect.centerx,
                            player_rect.bottom,
                            scale_factor,
                            density=settings.get("particle_density", "medium"),
                        )
                    )
                    dash_trail_timer = DASH_TRAIL_INTERVAL

            # ------------------------------------------------
            # SPAWNING: Trees/Coins/Platforms
            # (continues in Part 3)
            # ----------------------------------------------------
            # ------------------------------------------------
            # SPAWNING: Trees / Coins / Platforms
            # ------------------------------------------------
            now_ms = pygame.time.get_ticks()

            # TREE SPAWN
            if now_ms - wstate["last_tree_spawn"] >= config.OBSTACLE_SPAWN_DELAY_BASE / settings["game_speed_mult"]:
                t = spawn_tree(tree_img, screen_w, screen_h, scale_factor)
                trees_list.append(t)
                wstate["last_tree_spawn"] = now_ms

            # COIN SPAWN
            if now_ms - wstate["last_coin_spawn"] >= config.COIN_SPAWN_DELAY_BASE / settings["game_speed_mult"]:
                c = spawn_coin(screen_w, screen_h, coin_img, scale_factor)
                coins_list.append(c)
                wstate["last_coin_spawn"] = now_ms

            # PLATFORM SPAWN
            if now_ms - wstate["last_platform_spawn"] >= config.PLATFORM_SPAWN_DELAY_BASE / settings["game_speed_mult"]:
                p = spawn_platform(screen_w, screen_h, scale_factor)
                plats_list.append(p)
                wstate["last_platform_spawn"] = now_ms

                # Platform enemies
                if random.random() < config.ENEMY_CONFIG["walker"]["platform_spawn_chance"] * settings["enemy_spawn_mult"] * world_enemy_spawn_mult:
                    enemy = spawn_platform_enemy(
                        p["rect"],
                        enemy_sprites["walker"],
                        scale_factor,
                        kind="walker"
                    )
                    if enemy:
                        enemies_list.append(enemy)

            # ------------------------------------------------
            # SPAWN ENEMIES (ground/air)
            # ------------------------------------------------
            for kind, cfg_e in config.ENEMY_CONFIG.items():
                if cfg_e["spawn_type"] == "air":
                    if random.random() < cfg_e["spawn_chance"] * settings["enemy_spawn_mult"] * world_enemy_spawn_mult * dt_scaled:
                        e = spawn_air_enemy(kind, enemy_sprites, screen_w, screen_h,
                                            settings["enemy_spawn_mult"] * world_enemy_spawn_mult, scale_factor)
                        if e:
                            enemies_list.append(e)

                elif cfg_e["spawn_type"] == "ground":
                    if random.random() < cfg_e["spawn_chance"] * settings["enemy_spawn_mult"] * world_enemy_spawn_mult * dt_scaled:
                        e = spawn_ground_enemy(kind, enemy_sprites, screen_w, screen_h, scale_factor)
                        if e:
                            enemies_list.append(e)

            # ------------------------------------------------
            # BOSS WAVES on special levels
            # ------------------------------------------------
            if level in BOSS_LEVELS and not wstate.get("boss_wave_spawned", False):
                # Spawn a small crowd of tougher enemies as a mini-boss wave
                for i in range(config.BOSS_WAVE_GROUND_COUNT):
                    e = spawn_ground_enemy("jumper", enemy_sprites, screen_w, screen_h, scale_factor)
                    if e:
                        e["rect"].x += i * int(config.BOSS_WAVE_GROUND_SPACING * scale_factor)
                        enemies_list.append(e)
                for i in range(config.BOSS_WAVE_FLYER_COUNT):
                    e = spawn_air_enemy("flyer", enemy_sprites, screen_w, screen_h, world_enemy_spawn_mult * 1.5, scale_factor)
                    if e:
                        base_y = int(screen_h * config.BOSS_WAVE_FLYER_BASE_Y_RATIO)
                        e["rect"].y = base_y + i * int(config.BOSS_WAVE_FLYER_SPACING * scale_factor)
                        enemies_list.append(e)
                wstate["boss_wave_spawned"] = True

            # ------------------------------------------------
            # UPDATE ENTITIES
            # ------------------------------------------------

            # Trees (decor collisions not harmful)
            new_trees = []
            for t in trees_list:
                t.x -= int((GAME_SPEED_BASE * settings["game_speed_mult"] * world_scroll_mult) * dt_scaled)
                if t.right > -100:
                    new_trees.append(t)
            trees_list = new_trees

            # Coins
            new_coins = []
            for c in coins_list:
                c.x -= int((GAME_SPEED_BASE * settings["game_speed_mult"] * world_scroll_mult) * dt_scaled)
                if c.right < -50:
                    continue

                # Collect
                if c.colliderect(player_rect):
                    coins_collected_run += 1
                    # Achievement: 100 coins in one run
                    if coins_collected_run >= 100:
                        if award_achievement(save_data, "coins_100"):
                            popups = wstate.get("achievement_popups", [])
                            popups.append({"id": "coins_100", "timer": 3.0})
                            wstate["achievement_popups"] = popups
                    # Coin pickup feedback: sound + spark burst
                    if coin_snd:
                        coin_snd.play()
                    spark_particles.extend(
                        spawn_spark_burst(
                            c.centerx,
                            c.centery,
                            scale_factor,
                            density=settings.get("particle_density", "medium"),
                        )
                    )
                    continue
                new_coins.append(c)
            coins_list = new_coins

            # Enemy update
            enemies_list = update_enemies(
                enemies_list, dt_scaled, GAME_SPEED_BASE * settings["game_speed_mult"] * world_scroll_mult,
                scale_factor, player_rect, screen_w, screen_h
            )

            # ------------------------------------------------
            # DAMAGE from enemies
            # ------------------------------------------------
            if inv_timer > 0:
                inv_timer -= dt_scaled
            else:
                for e in enemies_list:
                    if e["rect"].colliderect(player_rect):
                        dmg = config.ENEMY_CONFIG[e["kind"]]["damage"]
                        dmg = int(dmg * settings["enemy_damage_mult"] * world_enemy_damage_mult)
                        health -= dmg
                        wstate["took_damage"] = True
                        inv_timer = INVINCIBLE_TIME

                        knock_timer = KNOCKBACK_TIME
                        knock_dx = -KNOCKBACK_SPEED * scale_factor * sign(player_rect.centerx - e["rect"].centerx)

                        # Hit feedback: brief, punchy shake
                        shake_timer = SCREEN_SHAKE_HIT
                        if hit_snd:
                            hit_snd.play()

            # Knockback
            if knock_timer > 0:
                player_rect.x += int(knock_dx * dt_scaled)
                knock_timer -= dt_scaled

            # ------------------------------------------------
            # LEVEL UP
            # ------------------------------------------------
            # Every N coins
            expected_level = 1 + coins_collected_run // LEVEL_UP_EVERY_COINS
            if expected_level > level:
                diff = expected_level - level
                level = expected_level

                # Level up bursts
                for _ in range(diff):
                    spark_particles.extend(spawn_levelup_burst(
                        player_rect.centerx,
                        player_rect.centery,
                        scale_factor,
                        settings["particle_density"]
                    ))

                shake_timer = SCREEN_SHAKE_KILL
                wstate["boss_wave_spawned"] = False

                # Level intro for new level
                name, story = get_level_meta(level)
                if level in BOSS_LEVELS:
                    level_intro_title = f"BOSS LEVEL {level}: {name}"
                else:
                    level_intro_title = f"LEVEL {level}: {name}"
                level_intro_story = story
                level_intro_timer = 3.0

                # Mid-run achievements for reaching certain levels
                if level >= 5:
                    if award_achievement(save_data, "reach_level_5"):
                        popups = wstate.get("achievement_popups", [])
                        popups.append({"id": "reach_level_5", "timer": 3.0})
                        wstate["achievement_popups"] = popups
                if level >= 10:
                    if award_achievement(save_data, "reach_level_10"):
                        popups = wstate.get("achievement_popups", [])
                        popups.append({"id": "reach_level_10", "timer": 3.0})
                        wstate["achievement_popups"] = popups
                if level >= 20:
                    if award_achievement(save_data, "reach_level_20"):
                        popups = wstate.get("achievement_popups", [])
                        popups.append({"id": "reach_level_20", "timer": 3.0})
                        wstate["achievement_popups"] = popups

                # No-hit to level 5 (check once when crossing 5+)
                if level >= 5 and not wstate.get("took_damage", False):
                    if award_achievement(save_data, "no_hit_to_5"):
                        popups = wstate.get("achievement_popups", [])
                        popups.append({"id": "no_hit_to_5", "timer": 3.0})
                        wstate["achievement_popups"] = popups

            # ------------------------------------------------
            # KILL (health <= 0)
            # ------------------------------------------------
            if health <= 0:
                run_score = int(score_time)
                run_coins = coins_collected_run
                run_level = level

                # Achievements
                if run_level >= 5:
                    award_achievement(save_data, "reach_level_5")
                if run_level >= 10:
                    award_achievement(save_data, "reach_level_10")
                if run_level >= 20:
                    award_achievement(save_data, "reach_level_20")
                if run_coins >= 100:
                    award_achievement(save_data, "coins_100")
                if run_level >= 5 and not wstate.get("took_damage", False):
                    award_achievement(save_data, "no_hit_to_5")

                # Update totals
                save_data["total_coins"] += run_coins
                save_data["best_score"] = max(save_data["best_score"], run_score)

                # Global top scores
                hs = save_data["high_scores"]
                hs.append({
                    "score": run_score,
                    "coins": run_coins,
                    "level": run_level
                })
                hs.sort(key=lambda r: r["score"], reverse=True)
                save_data["high_scores"] = hs[:10]

                # Per-level
                lvl_key = str(run_level)
                sbl = save_data["scores_by_level"].setdefault(lvl_key, [])
                sbl.append({
                    "score": run_score,
                    "coins": run_coins,
                    "level": run_level
                })
                sbl.sort(key=lambda r: r["score"], reverse=True)
                save_data["scores_by_level"][lvl_key] = sbl[:5]

                save_save(save_data)

                game_state = "game_over"
                game_over_focus = 0

            # ------------------------------------------------
            # UPDATE PARTICLES
            # ------------------------------------------------
            dust_particles = update_particles(dust_particles, dt_scaled, GRAVITY, scale_factor)
            spark_particles = update_particles(spark_particles, dt_scaled, GRAVITY, scale_factor)

            # Save updated world state
            wstate["player_vel_y"] = player_vel_y
            wstate["on_ground"] = on_ground
            wstate["was_on_ground"] = was_on_ground
            wstate["trees"] = trees_list
            wstate["coins"] = coins_list
            wstate["platforms"] = plats_list
            wstate["enemies"] = enemies_list
            wstate["dust_particles"] = dust_particles
            wstate["spark_particles"] = spark_particles

            wstate["health"] = health
            wstate["score_time"] = score_time + dt
            wstate["coins_collected_run"] = coins_collected_run
            wstate["level"] = level
            wstate["invincible_timer"] = inv_timer
            wstate["knockback_timer"] = knock_timer
            wstate["knockback_dx"] = knock_dx
            wstate["dash_timer"] = dash_timer
            wstate["dash_cooldown"] = dash_cooldown
            wstate["dash_dir"] = dash_dir
            wstate["shake_timer"] = shake_timer
            wstate["run_dust_timer"] = run_dust_timer
            wstate["dash_trail_timer"] = dash_trail_timer

            # ------------------------------------------------
            # DRAW ENTITIES
            # ------------------------------------------------

            # Ground
            if ground_img:
                game_surface.blit(ground_img, (0, int(screen_h * config.GROUND_Y_RATIO)))
            else:
                pygame.draw.rect(
                    game_surface, (80, 70, 50),
                    (0, int(screen_h * config.GROUND_Y_RATIO), screen_w, screen_h)
                )

            # Trees
            for t in trees_list:
                if tree_img:
                    game_surface.blit(tree_img, t)
                else:
                    pygame.draw.rect(game_surface, (40, 120, 40), t)

            # Platforms
            for p in plats_list:
                r = p["rect"]
                c = (140, 180, 220)
                pygame.draw.rect(game_surface, c, r)
                pygame.draw.rect(game_surface, WHITE, r, 2)

            # Coins
            for c in coins_list:
                if coin_img:
                    game_surface.blit(coin_img, c)
                else:
                    pygame.draw.circle(game_surface, (240, 200, 40), c.center, c.width // 2)

            # Enemies
            for e in enemies_list:
                img = enemy_sprites.get(e["kind"])
                if img:
                    game_surface.blit(img, e["rect"])
                else:
                    pygame.draw.rect(game_surface, (200, 40, 40), e["rect"])

            # Particles
            for p in dust_particles:
                pygame.draw.circle(game_surface, p["color"], (int(p["x"]), int(p["y"])), p["size"])
            for p in spark_particles:
                pygame.draw.circle(game_surface, p["color"], (int(p["x"]), int(p["y"])), p["size"])

            # ------------------------------------------------
            # Player drawing (animations + damage flash)
            # ------------------------------------------------
            if not on_ground:
                img = skin_jump
            elif move_x != 0:
                img = skin_run[int((now * 10) % len(skin_run))] if skin_run else skin_idle[0]
            else:
                img = skin_idle[int((now * 6) % len(skin_idle))] if skin_idle else None

            if img:
                game_surface.blit(img, player_rect)
                # Damage flash while invincible: white overlay blink
                if inv_timer > 0:
                    # Blink at configurable frequency during i-frames
                    if int(inv_timer * HIT_FLASH_FREQUENCY) % 2 == 0:
                        flash = img.copy()
                        flash.fill((255, 255, 255, 0), None, pygame.BLEND_RGBA_MULT)
                        game_surface.blit(flash, player_rect)
            else:
                base_color = (80, 200, 80)
                if inv_timer > 0 and int(inv_timer * HIT_FLASH_FREQUENCY) % 2 == 0:
                    base_color = (255, 255, 255)
                pygame.draw.rect(game_surface, base_color, player_rect)

            # ------------------------------------------------
            # HUD (health, score, coins, level) — retro style
            # ------------------------------------------------
            hud_color = (255, 255, 200)
            outline = (20, 20, 40)

            # Health hearts (up to 10)
            display_max = min(max_health, 10)
            display_health = clamp(health, 0, display_max)
            heart_size = int(18 * ui_scale)
            pad = int(6 * ui_scale)
            hx = int(24 * ui_scale)
            hy = int(26 * ui_scale)
            for i in range(display_max):
                cx = hx + i * (heart_size + pad)
                cy = hy
                if i < display_health:
                    draw_heart(game_surface, cx, cy, heart_size, (255, 80, 120), outline)
                else:
                    draw_heart(game_surface, cx, cy, heart_size, (60, 30, 40), outline)

            # Score and coins in top-right
            score_val = int(score_time)
            score_text = fonts["small"].render(f"SCORE {score_val:06d}", True, hud_color)
            coins_text = fonts["small"].render(f"COINS {coins_collected_run:03d}", True, hud_color)

            sx = screen_w - int(20 * ui_scale)
            sy = int(20 * ui_scale)
            score_rect = score_text.get_rect(topright=(sx, sy))
            coins_rect = coins_text.get_rect(topright=(sx, sy + score_rect.height + int(4 * ui_scale)))
            game_surface.blit(score_text, score_rect)
            game_surface.blit(coins_text, coins_rect)

            # Current level label under score
            level_text = fonts["tiny"].render(f"LEVEL {level}", True, hud_color)
            level_rect = level_text.get_rect(topright=(sx, coins_rect.bottom + int(2 * ui_scale)))
            game_surface.blit(level_text, level_rect)

            # ------------------------------------------------
            # Achievement popups (mid-run)
            # ------------------------------------------------
            popups = wstate.get("achievement_popups", [])
            if popups:
                new_popups = []
                base_y = int(80 * ui_scale)
                for i, p in enumerate(popups):
                    p["timer"] -= dt
                    if p["timer"] <= 0:
                        continue
                    new_popups.append(p)

                    ach_id = p.get("id")
                    meta = config.ACHIEVEMENTS.get(ach_id, {})
                    name = meta.get("name", ach_id)
                    text = f"Achievement Unlocked: {name}"

                    surf = fonts["small"].render(text, True, (255, 255, 200))
                    pad_x = int(12 * ui_scale)
                    pad_y = int(6 * ui_scale)
                    box = pygame.Rect(0, 0, surf.get_width() + pad_x * 2, surf.get_height() + pad_y * 2)
                    box.center = (screen_w // 2, base_y + i * (box.height + int(4 * ui_scale)))

                    pygame.draw.rect(game_surface, (5, 5, 20, 220), box, border_radius=6)
                    pygame.draw.rect(game_surface, (160, 240, 200), box, 2, border_radius=6)
                    game_surface.blit(surf, surf.get_rect(center=box.center))

                wstate["achievement_popups"] = new_popups

            # ------------------------------------------------
            # Level intro overlay
            # ------------------------------------------------
            if level_intro_timer > 0.0:
                level_intro_timer -= dt
                alpha = max(0, min(220, int(255 * min(level_intro_timer, 1.0))))
                if alpha > 0:
                    banner_h = int(80 * ui_scale)
                    banner = pygame.Surface((screen_w, banner_h), pygame.SRCALPHA)
                    banner.fill((5, 5, 20, alpha))
                    game_surface.blit(banner, (0, int(140 * ui_scale)))

                    if level_intro_title:
                        title_surf = fonts["large"].render(level_intro_title, True, (255, 255, 200))
                        game_surface.blit(title_surf, title_surf.get_rect(center=(screen_w // 2, int(160 * ui_scale))))
                    if level_intro_story:
                        story_surf = fonts["small"].render(level_intro_story, True, (220, 220, 220))
                        game_surface.blit(story_surf, story_surf.get_rect(center=(screen_w // 2, int(190 * ui_scale))))

        # =====================================================
        #  GAMESTATE: LEVEL EDITOR (RENDER)
        # =====================================================
        if game_state == "level_editor":
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

            tool_rect = tool_surf.get_rect(topleft=(x, y_top))
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

            # Store rects for hover-based scroll behaviour
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
            for x in range(0, screen_w, int(64 * ui_scale)):
                pygame.draw.line(game_surface, grid_color, (x, int(140 * ui_scale)), (x, screen_h))
            for y in range(int(140 * ui_scale), screen_h, int(64 * ui_scale)):
                pygame.draw.line(game_surface, grid_color, (0, y), (screen_w, y))

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

            # Platforms
            for p in editor_data["platforms"]:
                rx = int(p["x"] * scale_x)
                ry = int(p["y"] * scale_y)
                rw = max(1, int(p["w"] * scale_x))
                rh = max(1, int(p["h"] * scale_y))
                mr = pygame.Rect(mini_rect.left + rx, mini_rect.top + ry, rw, rh)
                pygame.draw.rect(game_surface, (100, 180, 230), mr)

            # Coins
            for c in editor_data["coins"]:
                cx = mini_rect.left + int(c["x"] * scale_x)
                cy = mini_rect.top + int(c["y"] * scale_y)
                pygame.draw.circle(game_surface, (240, 210, 80), (cx, cy), 2)

            # Enemies
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
                    status_surf.get_rect(center=(screen_w // 2, int(150 * ui_scale)))
                )

            # Controls hint
            y = int(screen_h * 0.80)
            for line in [
                "Left-click: place/move | Right-click: delete",
                "1=platform 2=coin 3=enemy | Tab/wheel on 'Tool' to cycle",
                "Q/E or wheel on 'Enemy': enemy kind | Z/X or wheel on 'Plat': platform type | ,/. platform width",
                "G or wheel on 'Snap': toggle grid snap | P: test play level | Ctrl+Z/Y: undo/redo",
                "[ / ]: switch custom level | Ctrl+C/V: copy/paste | Ctrl+S: save | Esc/B: menu"
            ]:
                s = fonts["small"].render(line, True, WHITE)
                game_surface.blit(s, s.get_rect(center=(screen_w // 2, y)))
                y += int(22 * ui_scale)

        # =====================================================
        #  PAUSE / MENUS / GAME OVER
        #  (Handled in Part 4)
        # =====================================================

        # End of Part 3
        # =====================================================
        #  GAMESTATE: MENUS (PAUSE, SETTINGS, GAME OVER, etc.)
        # =====================================================

        if game_state != "playing" and game_state != "level_editor":

            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            game_surface.blit(overlay, (0, 0))

            midx = screen_w // 2
            midy = screen_h // 2

            # --------------------------------------------
            # MAIN MENU
            # --------------------------------------------
            if game_state == "menu":
                title = fonts["title"].render("SLIMEY", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(140 * ui_scale))))

                items = config.MAIN_MENU_ITEMS
                rects = []
                button_w = int(340 * ui_scale)
                button_h = int(60 * ui_scale)
                start_y = int(230 * ui_scale)
                spacing = int(22 * ui_scale)

                for i, entry in enumerate(items):
                    r = Rect(midx - button_w // 2, start_y + i * (button_h + spacing),
                             button_w, button_h)
                    rects.append(r)
                    hovered = r.collidepoint(pygame.mouse.get_pos())
                    focused = (i == menu_focus)
                    draw_button(
                        game_surface,
                        r,
                        entry["label"],
                        fonts["normal"],
                        primary=False,
                        hovered=hovered,
                        focused=focused
                    )
                menu_button_rects = rects

            # --------------------------------------------
            # DISPLAY SETTINGS
            # --------------------------------------------
            elif game_state == "settings_menu":
                title = fonts["title"].render("SETTINGS", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(140 * ui_scale))))

                settings_menu_rects = []
                button_w = int(420 * ui_scale)
                button_h = int(52 * ui_scale)
                start_y = int(220 * ui_scale)
                spacing = int(14 * ui_scale)

                for i, entry in enumerate(SETTINGS_MENU_ITEMS):
                    r = Rect(midx - button_w // 2, start_y + i * (button_h + spacing),
                             button_w, button_h)
                    settings_menu_rects.append(r)
                    hovered = r.collidepoint(pygame.mouse.get_pos())
                    focused = (i == settings_menu_focus)
                    draw_button(
                        game_surface,
                        r,
                        entry["label"],
                        fonts["normal"],
                        primary=False,
                        hovered=hovered,
                        focused=focused
                    )

            # --------------------------------------------
            # DISPLAY SETTINGS
            # --------------------------------------------
            elif game_state == "display_settings":
                panel = Rect(
                    int(screen_w * 0.25),
                    int(screen_h * 0.15),
                    int(screen_w * 0.50),
                    int(screen_h * 0.70)
                )
                draw_panel(game_surface, panel, ui_scale, "DISPLAY", fonts)

                # Resolution selector
                y = panel.top + int(80 * ui_scale)
                opts = config.SUPPORTED_RESOLUTIONS
                display_row_rects = []
                for i, opt in enumerate(opts):
                    focused = (display_focus == i)
                    row_rect = Rect(
                        panel.left + int(40 * ui_scale),
                        y,
                        panel.width - int(80 * ui_scale),
                        int(60 * ui_scale),
                    )
                    draw_cycle_selector(
                        game_surface,
                        "Resolution",
                        opt if i == display_focus else "",
                        fonts,
                        row_rect.left,
                        row_rect.top,
                        row_rect.width,
                        row_rect.height,
                        focused=focused
                    )
                    display_row_rects.append(row_rect)
                    y += int(70 * ui_scale)

                # Fullscreen toggle
                focused = (display_focus == len(opts))
                display_fullscreen_rect = Rect(
                    panel.left + int(40 * ui_scale),
                    y,
                    panel.width - int(80 * ui_scale),
                    int(60 * ui_scale),
                )
                draw_toggle_switch(
                    game_surface,
                    "Fullscreen",
                    settings["fullscreen"],
                    fonts,
                    display_fullscreen_rect.left,
                    display_fullscreen_rect.top,
                    display_fullscreen_rect.width,
                    display_fullscreen_rect.height,
                    focused=focused
                )

                # VSync toggle
                focused = (display_focus == len(opts) + 1)
                display_vsync_rect = Rect(
                    panel.left + int(40 * ui_scale),
                    y + int(70 * ui_scale),
                    panel.width - int(80 * ui_scale),
                    int(60 * ui_scale),
                )
                draw_toggle_switch(
                    game_surface,
                    "VSync",
                    settings.get("vsync", True),
                    fonts,
                    display_vsync_rect.left,
                    display_vsync_rect.top,
                    display_vsync_rect.width,
                    display_vsync_rect.height,
                    focused=focused
                )

                # Note about when VSync takes effect
                note_text = "Note: VSync changes apply on next restart"
                note_surf = fonts["tiny"].render(note_text, True, WHITE)
                note_rect = note_surf.get_rect(
                    center=(panel.centerx, panel.bottom - int(30 * ui_scale))
                )
                game_surface.blit(note_surf, note_rect)

            # --------------------------------------------
            # GAMEPLAY SETTINGS
            # --------------------------------------------
            elif game_state == "gameplay_settings":
                panel = Rect(
                    int(screen_w * 0.25),
                    int(screen_h * 0.15),
                    int(screen_w * 0.50),
                    int(screen_h * 0.70)
                )
                draw_panel(game_surface, panel, ui_scale, "GAMEPLAY", fonts)

                y = panel.top + int(80 * ui_scale)

                # Difficulty row
                diff_label = "Difficulty"
                diff_value = settings.get("difficulty", "Normal")
                focused = (gameplay_focus == 0)
                diff_rect = Rect(
                    panel.left + int(40 * ui_scale),
                    y,
                    panel.width - int(80 * ui_scale),
                    int(60 * ui_scale),
                )
                draw_cycle_selector(
                    game_surface,
                    diff_label,
                    diff_value,
                    fonts,
                    diff_rect.left,
                    diff_rect.top,
                    diff_rect.width,
                    diff_rect.height,
                    focused=focused,
                )
                y += int(70 * ui_scale)

                items = config.GAMEPLAY_SLIDER_ORDER
                gameplay_row_rects = []
                for i, key in enumerate(items):
                    cfg = config.GAMEPLAY_SLIDER_CONFIG[key]
                    val = settings.get(key, cfg["min"])
                    focused = (gameplay_focus == i + 1)
                    row_rect = Rect(
                        panel.left + int(40 * ui_scale),
                        y,
                        panel.width - int(80 * ui_scale),
                        int(60 * ui_scale),
                    )
                    draw_cycle_selector(
                        game_surface,
                        cfg["label"],
                        f"{val:.2f}",
                        fonts,
                        row_rect.left,
                        row_rect.top,
                        row_rect.width,
                        row_rect.height,
                        focused=focused
                    )
                    gameplay_row_rects.append(row_rect)
                    y += int(70 * ui_scale)

            # --------------------------------------------
            # AUDIO SETTINGS
            # --------------------------------------------
            elif game_state == "audio_settings":
                panel = Rect(
                    int(screen_w * 0.25),
                    int(screen_h * 0.15),
                    int(screen_w * 0.50),
                    int(screen_h * 0.70)
                )
                draw_panel(game_surface, panel, ui_scale, "AUDIO", fonts)

                y = panel.top + int(80 * ui_scale)
                items = config.AUDIO_SLIDER_ORDER
                audio_row_rects = []
                for i, key in enumerate(items):
                    cfg = config.AUDIO_SLIDER_CONFIG[key]
                    val = settings.get(key, cfg["min"])
                    focused = (audio_focus == i)
                    row_rect = Rect(
                        panel.left + int(40 * ui_scale),
                        y,
                        panel.width - int(80 * ui_scale),
                        int(60 * ui_scale),
                    )
                    draw_cycle_selector(
                        game_surface,
                        cfg["label"],
                        f"{val:.2f}",
                        fonts,
                        row_rect.left,
                        row_rect.top,
                        row_rect.width,
                        row_rect.height,
                        focused=focused
                    )
                    audio_row_rects.append(row_rect)
                    y += int(70 * ui_scale)

            # --------------------------------------------
            # SKINS MENU
            # --------------------------------------------
            elif game_state == "skins_menu":
                title = fonts["title"].render("SKINS", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(140 * ui_scale))))

                card_w = int(420 * ui_scale)
                card_h = int(220 * ui_scale)
                card = Rect(
                    midx - card_w // 2,
                    int(220 * ui_scale),
                    card_w,
                    card_h
                )
                draw_panel(game_surface, card, ui_scale)

                skin_name = config.SKIN_LIST[skins_focus]
                unlocked = skin_name in save_data["skins"]["unlocked"]
                current = save_data["skins"]["current_skin"]

                meta = config.SKIN_META.get(skin_name, {})
                display_name = meta.get("display_name", skin_name)
                rarity = meta.get("rarity", "Common")
                desc = meta.get("description", "")

                preview_skin = skins_assets.get(skin_name, skins_assets["default"])
                draw_skin_preview(game_surface, card, preview_skin, ui_scale)

                name_surf = fonts["large"].render(display_name, True, WHITE)
                game_surface.blit(name_surf, name_surf.get_rect(center=(midx, card.top + int(40 * ui_scale))))

                status_parts = [rarity]
                if not unlocked:
                    req_lvl = config.SKIN_UNLOCK_LEVEL.get(skin_name, 1)
                    status_parts.append(f"Locked: Reach L{req_lvl}")
                else:
                    if skin_name == current:
                        status_parts.append("[Selected]")
                    else:
                        status_parts.append("[Unlocked]")

                status_surf = fonts["small"].render("  ".join(status_parts), True, WHITE)
                game_surface.blit(status_surf, status_surf.get_rect(center=(midx, card.top + int(80 * ui_scale))))

                if desc:
                    wrap_text(
                        game_surface,
                        desc,
                        fonts["small"],
                        WHITE,
                        card.left + int(20 * ui_scale),
                        card.bottom - int(70 * ui_scale),
                        card_w - int(40 * ui_scale)
                    )

            # --------------------------------------------
            # CONTROLS SETTINGS
            # --------------------------------------------
            elif game_state == "controls_settings":
                panel = Rect(
                    int(screen_w * 0.20),
                    int(screen_h * 0.15),
                    int(screen_w * 0.60),
                    int(screen_h * 0.70)
                )
                draw_panel(game_surface, panel, ui_scale, "CONTROLS", fonts)

                # Mode toggle (Keyboard / Controller)
                mode_text = f"Mode: {'Keyboard' if controls_mode == 'keyboard' else 'Controller'}  (Tab to switch)"
                mode_surf = fonts["small"].render(mode_text, True, WHITE)
                game_surface.blit(
                    mode_surf,
                    mode_surf.get_rect(center=(panel.centerx, panel.top + int(50 * ui_scale)))
                )

                y = panel.top + int(90 * ui_scale)
                controls_row_rects = []
                for i, action in enumerate(CONTROL_ACTION_ORDER):
                    label = CONTROL_ACTION_LABELS[action]
                    if controls_mode == "keyboard":
                        val = format_key_list(kb_cfg.get(action, []))
                    else:
                        val = format_controller_list(ctr_cfg.get(action, []))
                    focused = (controls_focus == i)
                    row_rect = Rect(
                        panel.left + int(40 * ui_scale),
                        y,
                        panel.width - int(80 * ui_scale),
                        int(60 * ui_scale),
                    )
                    draw_cycle_selector(
                        game_surface,
                        label,
                        val,
                        fonts,
                        row_rect.left,
                        row_rect.top,
                        row_rect.width,
                        row_rect.height,
                        focused=focused,
                    )
                    controls_row_rects.append(row_rect)
                    y += int(70 * ui_scale)

                if controls_waiting_action is not None:
                    if controls_waiting_mode == "keyboard":
                        prompt = f"Press a key for {CONTROL_ACTION_LABELS[controls_waiting_action]} (Esc to cancel)"
                    else:
                        prompt = f"Press a controller button or D-Pad for {CONTROL_ACTION_LABELS[controls_waiting_action]} (Esc to cancel)"
                    center_text(
                        game_surface,
                        prompt,
                        fonts["small"],
                        WHITE,
                        panel.bottom - int(40 * ui_scale),
                        screen_w,
                    )

            # --------------------------------------------
            # LEVEL SELECT
            # --------------------------------------------
            elif game_state == "level_select":
                title = fonts["title"].render("LEVEL SELECT", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(150 * ui_scale))))

                total_levels = len(config.LEVEL_CONFIGS)
                level_row_rects = []

                # How many rows fit on screen
                visible_rows = 8
                top_y = int(240 * ui_scale)
                row_h = int(70 * ui_scale)

                # Center the view around the focused entry when possible
                start = max(0, level_select_focus - visible_rows // 2)
                end = min(total_levels, start + visible_rows)
                start = max(0, end - visible_rows)

                for i, idx in enumerate(range(start, end)):
                    y = top_y + i * row_h

                    # Per-level best score (if any)
                    lvl_key = str(idx + 1)
                    runs = save_data["scores_by_level"].get(lvl_key, [])
                    best_run = runs[0] if runs else None
                    base_name = config.LEVEL_CONFIGS[idx]["name"]
                    is_boss = (idx + 1) in BOSS_LEVELS
                    if best_run is not None:
                        best_score = int(best_run.get("score", 0))
                        best_coins = int(best_run.get("coins", 0))
                        medal = medal_for_score(best_score)
                        medal_txt = f"  [{medal}]" if medal else ""
                        label = f"Level {idx+1}: {base_name}"
                        if is_boss:
                            label += "  [BOSS]"
                        label += f"  —  Best {best_score:06d}  {best_coins} coins{medal_txt}"
                    else:
                        label = f"Level {idx+1}: {base_name}"
                        if is_boss:
                            label += "  [BOSS]"

                    focused = (idx == level_select_focus)
                    color = (255, 255, 160) if focused else WHITE
                    surf = fonts["normal"].render(label, True, color)
                    rect = surf.get_rect(center=(midx, y))
                    game_surface.blit(surf, rect)
                    # Store (level_index, rect) so mouse clicks know which level
                    level_row_rects.append((idx, rect))

                # Small hint + page indicator at bottom
                hint = f"Use Up/Down, Enter to play  ({level_select_focus+1}/{total_levels})"
                center_text(game_surface, hint, fonts["tiny"], WHITE, int(screen_h * 0.9), screen_w)

            # --------------------------------------------
            # SHOP
            # --------------------------------------------
            elif game_state == "shop":
                title = fonts["title"].render("SHOP", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(150 * ui_scale))))

                coins_text = fonts["normal"].render(f"Coins: {save_data['total_coins']}", True, WHITE)
                game_surface.blit(coins_text, coins_text.get_rect(center=(midx, int(210 * ui_scale))))

                y = int(260 * ui_scale)
                items = list(config.UPGRADE_COSTS.items())
                shop_item_rects = []
                for i, (key, cost) in enumerate(items):
                    owned = save_data["upgrades"].get(key, False)
                    label = f"{key.replace('_', ' ').title()} — "
                    label += ("Owned" if owned else f"Cost {cost}")
                    color = (255, 255, 160) if i == shop_focus else WHITE
                    surf = fonts["normal"].render(label, True, color)
                    rect = surf.get_rect(center=(midx, y))
                    game_surface.blit(surf, rect)
                    shop_item_rects.append(rect)
                    y += int(60 * ui_scale)

            # --------------------------------------------
            # HIGH SCORES
            # --------------------------------------------
            elif game_state == "high_scores":
                title = fonts["title"].render("HIGH SCORES", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(120 * ui_scale))))

                # Global
                y = int(200 * ui_scale)
                center_text(game_surface, "Top Runs", fonts["large"], WHITE, y, screen_w)
                y += int(50 * ui_scale)

                for i, run in enumerate(save_data["high_scores"][:10]):
                    text = f"{i+1}. Score {run['score']} | L{run['level']} | {run['coins']} coins"
                    center_text(game_surface, text, fonts["normal"], WHITE, y, screen_w)
                    y += int(40 * ui_scale)

                # Per-level
                y += int(60 * ui_scale)
                center_text(game_surface, "Best by Level", fonts["large"], WHITE, y, screen_w)
                y += int(50 * ui_scale)

                # Sort levels numerically
                level_items = sorted(
                    save_data["scores_by_level"].items(),
                    key=lambda kv: int(kv[0])
                )

                for lvl_key, runs in level_items:
                    if not runs:
                        continue
                    best = runs[0]
                    medal = medal_for_score(int(best.get("score", 0)))
                    medal_txt = f"  [{medal}]" if medal else ""
                    text = f"Level {lvl_key}: best {best['score']} ({best['coins']} coins){medal_txt}"
                    center_text(game_surface, text, fonts["normal"], WHITE, y, screen_w)
                    y += int(40 * ui_scale)

                # Achievements
                y += int(60 * ui_scale)
                center_text(game_surface, "Achievements", fonts["large"], WHITE, y, screen_w)
                y += int(45 * ui_scale)

                for ach_id, meta in config.ACHIEVEMENTS.items():
                    unlocked = save_data.get("achievements", {}).get(ach_id, False)
                    name = meta.get("name", ach_id)
                    desc = meta.get("desc", "")
                    marker = "✔" if unlocked else " "
                    color = WHITE if unlocked else (150, 150, 150)
                    text = f"[{marker}] {name} — {desc}"
                    center_text(game_surface, text, fonts["small"], color, y, screen_w)
                    y += int(32 * ui_scale)

            # --------------------------------------------
            # HOW TO PLAY / LORE
            # --------------------------------------------
            elif game_state == "how_to_play":
                panel = Rect(
                    int(screen_w * 0.18),
                    int(screen_h * 0.14),
                    int(screen_w * 0.64),
                    int(screen_h * 0.72),
                )
                draw_panel(game_surface, panel, ui_scale, "HOW TO PLAY", fonts)

                y = panel.top + int(80 * ui_scale)
                lines = [
                    "Controls",
                    "Move: A/D or Left/Right    Jump: Space/W/Up",
                    "Dash: Shift    Pause: Esc or Start",
                    "",
                    "Goal",
                    "Survive as long as you can, collect coins,",
                    "and climb through tougher worlds and boss waves.",
                    "",
                    "Worlds",
                    "Forest and Country are warm-up runs, Ice is slippery,",
                    "Desert and Lava ramp up speed and danger.",
                    "",
                    "Custom Levels",
                    "Use Level Editor from the main menu to build",
                    "your own layouts, then play them via Level Select.",
                    "",
                    "Lore",
                    "You are a lone slime crossing broken worlds,",
                    "chasing an endless trail of coins and neon skies.",
                ]

                for text in lines:
                    if not text:
                        y += int(12 * ui_scale)
                        continue
                    surf = fonts["small"].render(text, True, WHITE)
                    game_surface.blit(surf, (panel.left + int(32 * ui_scale), y))
                    y += surf.get_height() + int(6 * ui_scale)

            # --------------------------------------------
            # PAUSE
            # --------------------------------------------
            elif game_state == "paused":
                title = fonts["title"].render("PAUSED", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(180 * ui_scale))))

                # Quick run summary
                summary_y = int(230 * ui_scale)
                lvl = wstate.get("level", 1)
                score_val = int(wstate.get("score_time", 0))
                coins_run = wstate.get("coins_collected_run", 0)

                summary_text = f"Level {lvl} | Score {score_val:06d} | Coins {coins_run:03d}"
                summary_surf = fonts["small"].render(summary_text, True, WHITE)
                game_surface.blit(summary_surf, summary_surf.get_rect(center=(midx, summary_y)))

                # Per-level best score (if any)
                lvl_key = str(lvl)
                runs = save_data.get("scores_by_level", {}).get(lvl_key, [])
                if runs:
                    best = runs[0]
                    best_score = int(best.get("score", 0))
                    best_coins = int(best.get("coins", 0))
                    medal = medal_for_score(best_score)
                    medal_txt = f"  [{medal}]" if medal else ""
                    best_txt = f"Best {best_score:06d}  {best_coins} coins{medal_txt}"
                    best_surf = fonts["tiny"].render(best_txt, True, WHITE)
                    game_surface.blit(best_surf, best_surf.get_rect(center=(midx, summary_y + int(28 * ui_scale))))

                # Simple music volume quick-adjust hint
                vol = settings.get("music_volume", 0.5)
                vol_text = f"Music Volume: {int(vol * 100)}%  (Use Left/Right)"
                vol_surf = fonts["tiny"].render(vol_text, True, WHITE)
                game_surface.blit(vol_surf, vol_surf.get_rect(center=(midx, summary_y + int(52 * ui_scale))))

                opts = ["Resume", "Main Menu", "Quit"]
                pause_option_rects = []
                for i, opt in enumerate(opts):
                    y = int(320 * ui_scale) + i * int(70 * ui_scale)
                    color = (255,255,160) if pause_focus == i else WHITE
                    surf = fonts["normal"].render(opt, True, color)
                    rect = surf.get_rect(center=(midx, y))
                    game_surface.blit(surf, rect)
                    pause_option_rects.append(rect)

            # --------------------------------------------
            # GAME OVER
            # --------------------------------------------
            elif game_state == "game_over":
                title = fonts["title"].render("GAME OVER", True, WHITE)
                game_surface.blit(title, title.get_rect(center=(midx, int(200 * ui_scale))))

                score_text = fonts["large"].render(f"Score: {int(wstate['score_time'])}", True, WHITE)
                game_surface.blit(score_text, score_text.get_rect(center=(midx, int(300 * ui_scale))))

                y = int(360 * ui_scale)
                opts = ["Retry", "Main Menu", "Quit"]
                game_over_option_rects = []
                for i, opt in enumerate(opts):
                    color = (255,255,160) if game_over_focus == i else WHITE
                    surf = fonts["normal"].render(opt, True, color)
                    rect = surf.get_rect(center=(midx, y))
                    game_surface.blit(surf, rect)
                    game_over_option_rects.append(rect)
                    y += int(60 * ui_scale)


        # =====================================================
        #  APPLY SCREEN SHAKE
        # =====================================================
        if game_state == "playing" and wstate["shake_timer"] > 0:
            wstate["shake_timer"] -= dt_scaled
            sx = int(random.uniform(-SCREEN_SHAKE_INTENSITY, SCREEN_SHAKE_INTENSITY))
            sy = int(random.uniform(-SCREEN_SHAKE_INTENSITY, SCREEN_SHAKE_INTENSITY))
            final_surface = apply_shake(game_surface, sx, sy)
        else:
            final_surface = game_surface

        # =====================================================
        #  FX OVERLAYS
        # =====================================================
        fx_mode = settings.get("fx_mode", "off")
        if fx_mode in fx_masks and fx_masks[fx_mode]:
            final_surface.blit(fx_masks[fx_mode], (0, 0))

        # =====================================================
        #  BLIT TO SCREEN
        # =====================================================
        screen.blit(final_surface, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
