import os
import json
import pygame

from config import (
    DEFAULT_RESOLUTION,
    DEFAULT_FULLSCREEN,
    REFERENCE_WIDTH,
    REFERENCE_HEIGHT,
    SUPPORTED_RESOLUTIONS,
    BACKGROUND_AUTO_PREFIX,
    SKIN_LIST,
    WORLD_PACKS,
    ENEMY_VISUAL_CONFIG,
    SOUND_JUMP_FILE,
    SOUND_COIN_FILE,
    SOUND_HIT_FILE,
    SOUND_LAND_FILE,
    MUSIC_FILE,
    SAVE_FILE,
    ASSETS_DIR,
)


# ============================================================
#  SAVE LOAD / SAVE WRITE
# ============================================================

def _default_save():
    return {
        "best_score": 0,
        "total_coins": 0,

        "settings": {
            "resolution": DEFAULT_RESOLUTION,
            "fullscreen": DEFAULT_FULLSCREEN,
            "vsync": True,
            "fx_mode": "scanlines",
            "particles_enabled": True,
            "particle_density": "medium",
            "difficulty": "Normal",
            "game_speed_mult": 1.0,
            "enemy_spawn_mult": 1.0,
            "enemy_damage_mult": 1.0,
            "gravity_mult": 1.0,
            "jump_mult": 1.0,
            "move_speed_mult": 1.0,
            "music_volume": 0.5,
        },

        "upgrades": {
            "double_jump": False,
            "coin_magnet": False,
            "extra_heart": False,
        },

        "skins": {
            "current_skin": "default",
            "unlocked": ["default"],
        },

        # Global top runs
        "high_scores": [],

        # Per-level scoreboard
        "scores_by_level": {},

        # Achievements (id -> bool)
        "achievements": {},
    }


def load_save():
    """Load save file, or create defaults."""
    if not os.path.exists(SAVE_FILE):
        data = _default_save()
        save_save(data)
        return data

    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = _default_save()

    # Ensure all required keys exist
    base = _default_save()

    # Top-level keys
    for key, val in base.items():
        if key not in data:
            data[key] = val

    # Settings
    for key, val in base["settings"].items():
        data["settings"].setdefault(key, val)

    # Upgrades
    for key, val in base["upgrades"].items():
        data["upgrades"].setdefault(key, val)

    # Skins
    data.setdefault("skins", base["skins"])
    data["skins"].setdefault("current_skin", "default")
    data["skins"].setdefault("unlocked", ["default"])

    # High scores
    data.setdefault("high_scores", [])

    # Per-level scores
    data.setdefault("scores_by_level", {})

    # Achievements
    data.setdefault("achievements", {})

    return data


def save_save(data):
    """Safely write the save file."""
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[save] Failed to save data: {e}")


# ============================================================
#  RESOLUTION HELPERS
# ============================================================

def parse_resolution(res_str: str):
    try:
        ws, hs = res_str.lower().split("x")
        return int(ws), int(hs)
    except Exception:
        return REFERENCE_WIDTH, REFERENCE_HEIGHT


def compute_scale_factor(res_str: str) -> float:
    w, _ = parse_resolution(res_str)
    return w / float(REFERENCE_WIDTH)


# ============================================================
#  ASSET HELPERS
# ============================================================

def _load_image(path, scale_factor=1.0):
    if not os.path.exists(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if scale_factor != 1.0:
            w = max(1, int(img.get_width() * scale_factor))
            h = max(1, int(img.get_height() * scale_factor))
            img = pygame.transform.scale(img, (w, h))
        return img
    except Exception as e:
        print(f"[assets] Error loading {path}: {e}")
        return None


# ------------------------------------------------------------
#  Background loader (supports layers)
# ------------------------------------------------------------
def _load_background_series(folder, screen_w, screen_h):
    """
    Loads background{n}_far/mid/near.png into structured layers.
    Returns: [ {"far":surf,"mid":surf,"near":surf}, ... ]
    """
    if not os.path.isdir(folder):
        return []

    backgrounds = []
    idx = 1

    while True:
        far_p  = os.path.join(folder, f"{BACKGROUND_AUTO_PREFIX}{idx}_far.png")
        mid_p  = os.path.join(folder, f"{BACKGROUND_AUTO_PREFIX}{idx}_mid.png")
        near_p = os.path.join(folder, f"{BACKGROUND_AUTO_PREFIX}{idx}_near.png")

        if not (os.path.exists(far_p) or os.path.exists(mid_p) or os.path.exists(near_p)):
            break

        layer = {}

        for key, path in (("far", far_p), ("mid", mid_p), ("near", near_p)):
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.scale(img, (screen_w, screen_h))
                    layer[key] = img
                except Exception as e:
                    print(f"[assets] Failed loading {path}: {e}")
                    layer[key] = None
            else:
                layer[key] = None

        backgrounds.append(layer)
        idx += 1

    return backgrounds


# ------------------------------------------------------------
#  Skins loader
# ------------------------------------------------------------
def _load_skins(base_path, scale_factor):
    skins = {}
    root = os.path.join(base_path, "skins")

    if not os.path.isdir(root):
        return skins

    for entry in os.listdir(root):
        skin_dir = os.path.join(root, entry)
        if not os.path.isdir(skin_dir):
            continue

        def load_frames(prefix):
            frames = []
            idx = 1
            while True:
                candidate = os.path.join(skin_dir, f"{prefix}_{idx}.png")
                if not os.path.exists(candidate):
                    break
                img = _load_image(candidate, scale_factor)
                if img:
                    frames.append(img)
                idx += 1

            # fallback: prefix.png
            if not frames:
                path = os.path.join(skin_dir, f"{prefix}.png")
                if os.path.exists(path):
                    img = _load_image(path, scale_factor)
                    if img:
                        frames.append(img)
            return frames

        idle_frames = load_frames("idle")
        run_frames = load_frames("run")
        jump_img   = _load_image(os.path.join(skin_dir, "jump.png"), scale_factor)

        skins[entry] = {
            "idle": idle_frames,
            "run": run_frames,
            "jump": jump_img,
        }

    # Ensure default fallback for missing skins
    if "default" in skins:
        for s in SKIN_LIST:
            if s not in skins:
                skins[s] = skins["default"]

    return skins


# ------------------------------------------------------------
#  Enemy sprite loader
# ------------------------------------------------------------
def _load_enemies(base_path, scale_factor):
    enemy_sprites = {}
    for kind, vconf in ENEMY_VISUAL_CONFIG.items():
        fname = os.path.join(base_path, f"enemy_{kind}.png")
        img = _load_image(fname, 1.0)
        if img:
            size = max(8, int(vconf["size"] * scale_factor))
            img = pygame.transform.smoothscale(img, (size, size))
            enemy_sprites[kind] = img
        else:
            enemy_sprites[kind] = None
    return enemy_sprites


# ------------------------------------------------------------
#  FX Mask loader
# ------------------------------------------------------------
def _load_fx_masks(base_path, screen_w, screen_h):
    fx = {}

    scan = os.path.join(base_path, "scanlines.png")
    if os.path.exists(scan):
        try:
            img = pygame.image.load(scan).convert_alpha()
            fx["scanlines"] = pygame.transform.scale(img, (screen_w, screen_h))
        except Exception as e:
            print(f"[assets] Error loading scanlines: {e}")

    crt = os.path.join(base_path, "crt_mask.png")
    if os.path.exists(crt):
        try:
            img = pygame.image.load(crt).convert_alpha()
            fx["crt"] = pygame.transform.scale(img, (screen_w, screen_h))
        except Exception as e:
            print(f"[assets] Error loading CRT mask: {e}")

    return fx


# ------------------------------------------------------------
#  AUDIO loader
# ------------------------------------------------------------
def load_sounds(base_path):
    out = {
        "jump": None,
        "coin": None,
        "hit": None,
        "land": None,
    }
    jump = os.path.join(base_path, SOUND_JUMP_FILE)
    coin = os.path.join(base_path, SOUND_COIN_FILE)
    hit  = os.path.join(base_path, SOUND_HIT_FILE)
    land = os.path.join(base_path, SOUND_LAND_FILE)

    try:
        if os.path.exists(jump):
            out["jump"] = pygame.mixer.Sound(jump)
        if os.path.exists(coin):
            out["coin"] = pygame.mixer.Sound(coin)
        if os.path.exists(hit):
            out["hit"] = pygame.mixer.Sound(hit)
        if os.path.exists(land):
            out["land"] = pygame.mixer.Sound(land)
    except Exception as e:
        print(f"[audio] Failed loading SFX: {e}")

    return out


def load_music(base_path):
    path = os.path.join(base_path, MUSIC_FILE)
    if os.path.exists(path):
        return path
    return None


# ============================================================
#  MAIN ASSET LOADER (called from slime_platformer.main)
# ============================================================

def reload_all_assets(scale_factor, cfg, screen_w, screen_h):
    base_path = ASSETS_DIR

    # --- Global backgrounds ---
    backgrounds = _load_background_series(
        os.path.join(base_path, "backgrounds"),
        screen_w, screen_h
    )

    # --- World backgrounds ---
    world_backgrounds = {}
    worlds_root = os.path.join(base_path, "worlds")
    if os.path.isdir(worlds_root):
        for world_id in cfg.WORLD_PACKS.keys():
            bg_folder = os.path.join(worlds_root, world_id, "backgrounds")
            bgs = _load_background_series(bg_folder, screen_w, screen_h)
            if bgs:
                world_backgrounds[world_id] = bgs

    # --- Skins ---
    skins = _load_skins(base_path, scale_factor)

    # --- Basic environment sprites ---
    ground_img = _load_image(os.path.join(base_path, "ground.png"), scale_factor)
    tree_img   = _load_image(os.path.join(base_path, "tree.png"), scale_factor)
    coin_img   = _load_image(os.path.join(base_path, "coin.png"), scale_factor)

    # --- Enemies ---
    enemy_sprites = _load_enemies(base_path, scale_factor)

    # --- FX overlays ---
    fx_masks = _load_fx_masks(base_path, screen_w, screen_h)

    # --- Audio ---
    sounds = load_sounds(base_path)
    music_path = load_music(base_path)

    return {
        "backgrounds": backgrounds,
        "world_backgrounds": world_backgrounds,
        "skins": skins,
        "ground": ground_img,
        "tree": tree_img,
        "coin": coin_img,
        "enemy_sprites": enemy_sprites,
        "fx": fx_masks,
        "sounds": sounds,
        "music_path": music_path,
    }
