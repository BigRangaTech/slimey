# ============================================================
#  Slimey — CENTRALIZED GAME CONFIGURATION
# ============================================================

import os
import json

# ------------------------------------------------------------
#  BASE PATHS
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LEVELS_DIR = os.path.join(BASE_DIR, "levels")
CONFIG_DIR = os.path.join(BASE_DIR, "configs")

SAVE_FILE = os.path.join(BASE_DIR, "save_data.json")

# Background auto prefix (for background1_far/mid/near.png etc)
BACKGROUND_AUTO_PREFIX = "background"


# ------------------------------------------------------------
#  DISPLAY / RESOLUTION
# ------------------------------------------------------------
SUPPORTED_RESOLUTIONS = [
    "1280x720",
    "1600x900",
    "1920x1080",
    "2560x1440",
    "3840x2160",
]

DEFAULT_RESOLUTION = "1920x1080"
DEFAULT_FULLSCREEN = False

REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080
FPS = 60


# ------------------------------------------------------------
#  GAMEPLAY / PHYSICS
# ------------------------------------------------------------
GRAVITY = 2200.0
JUMP_STRENGTH = -900.0
PLAYER_MOVE_SPEED = 480.0
GAME_SPEED_BASE = 220.0
GROUND_Y_RATIO = 0.8

INVINCIBLE_TIME = 1.0
KNOCKBACK_TIME = 0.22
KNOCKBACK_SPEED = 680.0

DASH_SPEED = 1100.0
DASH_DURATION = 0.25
DASH_COOLDOWN = 1.1

SCREEN_SHAKE_HIT = 0.25
SCREEN_SHAKE_KILL = 0.40
SCREEN_SHAKE_INTENSITY = 6

BASE_MAX_HEALTH = 3
LEVEL_UP_EVERY_COINS = 20

OBSTACLE_SPAWN_DELAY_BASE = 1600
COIN_SPAWN_DELAY_BASE = 900
PLATFORM_SPAWN_DELAY_BASE = 1400


# ------------------------------------------------------------
#  CONTROLLER CONSTANTS (SDL GAMEPAD)
# ------------------------------------------------------------
BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_START = 7


# ------------------------------------------------------------
#  COLORS
# ------------------------------------------------------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SKY_COLOR = (60, 120, 180)


# ------------------------------------------------------------
#  SKINS — LIST, UNLOCKS, METADATA
# ------------------------------------------------------------
SKIN_LIST = ["default", "blue", "red", "green", "purple", "gold"]

SKIN_UNLOCK_LEVEL = {
    "default": 1,
    "blue": 3,
    "red": 5,
}

SKIN_META = {
    "default": {
        "display_name": "Classic Slime",
        "rarity": "Common",
        "description": "The original bouncy blob. Reliable and iconic.",
    },
    "blue": {
        "display_name": "Azure Slime",
        "rarity": "Rare",
        "description": "Cool and calm. Favours chilly winds and fast runs.",
    },
    "red": {
        "display_name": "Crimson Slime",
        "rarity": "Epic",
        "description": "Blazing hot energy. Looks faster just standing still.",
    },
}


# ------------------------------------------------------------
#  ENEMY CONFIG — STATS & BEHAVIOR
# ------------------------------------------------------------
ENEMY_CONFIG = {
    "walker": {
        "spawn_type": "platform",
        "platform_spawn_chance": 0.25,
        "spawn_chance": 0.00,
        "damage": 1,
        "min_level": 1,
        "speed": 140.0,
    },
    "flyer": {
        "spawn_type": "air",
        "spawn_chance": 0.08,
        "damage": 1,
        "min_level": 2,
        "speed": 180.0,
    },
    "jumper": {
        "spawn_type": "ground",
        "spawn_chance": 0.04,
        "damage": 2,
        "min_level": 3,
        "speed": 160.0,
    },
    # Extra enemies mainly for custom levels / editor
    "brute": {
        "spawn_type": "ground",
        "spawn_chance": 0.00,  # only appears if placed in editor
        "damage": 3,
        "min_level": 1,
        "speed": 110.0,
    },
    "swift": {
        "spawn_type": "ground",
        "spawn_chance": 0.00,  # only appears if placed in editor
        "damage": 1,
        "min_level": 1,
        "speed": 220.0,
    },
}

ENEMY_BEHAVIOR_CONFIG = {
    "walker": {
        "type": "patrol",
        "turn_on_edge": True,
        "aggressive_range": 0,
    },
    "flyer": {
        "type": "sine_fly",
        "amplitude": 40,
        "frequency": 1.4,
    },
    "jumper": {
        "type": "jump",
        "jump_interval": 2.0,
        "jump_force": -750.0,
    },
    "brute": {
        "type": "patrol",
        "turn_on_edge": True,
        "aggressive_range": 0,
    },
    "swift": {
        "type": "patrol",
        "turn_on_edge": True,
        "aggressive_range": 0,
    },
}

ENEMY_VISUAL_CONFIG = {
    "walker": {"color": (220, 200, 80), "size": 52},
    "flyer":  {"color": (160, 210, 255), "size": 44},
    "jumper": {"color": (230, 80, 120),  "size": 48},
    "brute":  {"color": (180, 60, 40),   "size": 60},
    "swift":  {"color": (120, 240, 120), "size": 40},
}

ENEMY_LEVEL_SCALING = {
    "walker": {"level_threshold": 3, "spawn_scale_per_level": 0.12},
    "flyer":  {"level_threshold": 4, "spawn_scale_per_level": 0.15},
}

LEVEL_ENEMY_CONFIG = {
    "default": {
        "enabled_kinds": ["walker", "flyer", "jumper"],
        "spawn_multipliers": {"walker": 1.0, "flyer": 1.0, "jumper": 1.0},
    },
    "by_level": {
        1: {"enabled_kinds": ["walker"]},
        2: {"enabled_kinds": ["walker", "flyer"]},
        3: {"enabled_kinds": ["walker", "flyer", "jumper"]},
    },
}


# ------------------------------------------------------------
#  WORLD PACKS (auto backgrounds, tint, scaling)
# ------------------------------------------------------------
WORLD_PACKS = {
    "forest": {
        "levels": [1, 2],
        "scroll_speed_mult": 1.0,
        "enemy_spawn_mult": 1.0,
        "enemy_damage_mult": 1.0,
        "tint": [20, 60, 20, 40],
    },
    "country": {
        "levels": [3, 4],
        "scroll_speed_mult": 1.05,
        "enemy_spawn_mult": 1.0,
        "enemy_damage_mult": 1.0,
        "tint": [60, 80, 20, 50],
    },
    "ice": {
        "levels": [5, 6],
        "scroll_speed_mult": 1.1,
        "enemy_spawn_mult": 1.1,
        "enemy_damage_mult": 1.05,
        "tint": [40, 60, 100, 60],
    },
    "desert": {
        "level_range": [7, 12],
        "scroll_speed_mult": 1.2,
        "enemy_spawn_mult": 1.2,
        "enemy_damage_mult": 1.1,
        "tint": [120, 90, 20, 60],
    },
    "lava": {
        "level_range": [13, 99],
        "scroll_speed_mult": 1.2,
        "enemy_spawn_mult": 1.3,
        "enemy_damage_mult": 1.2,
        "tint": [120, 40, 20, 70],
    },
}

AUTO_LEVEL_NAMING_FROM_FILENAME = True
AUTO_LEVEL_TINT_FROM_KEYWORD = True
AUTO_LEVEL_MUSIC_ENABLED = True
AUTO_ENEMY_PATTERN_SCALING = True
AUTO_COLLECTIBLES_ENABLED = True

LEVEL_TINT_KEYWORDS = {
    "forest": (20, 60, 20, 40),
    "ice": (40, 60, 100, 60),
    "desert": (80, 70, 20, 50),
    "lava": (120, 40, 20, 70),
}
DEFAULT_LEVEL_TINT = (0, 0, 0, 0)


# ------------------------------------------------------------
#  ACHIEVEMENTS
# ------------------------------------------------------------
ACHIEVEMENTS = {
    "reach_level_5": {
        "name": "Getting Serious",
        "desc": "Reach level 5 in a single run.",
    },
    "reach_level_10": {
        "name": "Double Digits",
        "desc": "Reach level 10 in a single run.",
    },
    "reach_level_20": {
        "name": "Endless Runner",
        "desc": "Reach level 20 in a single run.",
    },
    "no_hit_to_5": {
        "name": "Untouchable",
        "desc": "Reach level 5 without taking damage.",
    },
    "coins_100": {
        "name": "Treasure Hoarder",
        "desc": "Collect 100 coins in a single run.",
    },
}

LEVEL_CONFIGS = [
    {
        "name": "Grassy Plains",
        "scroll_speed_mult": 1.0,
        "enemy_spawn_mult": 1.0,
        "enemy_damage_mult": 1.0,
        "story": "A chill warmup run with gentle enemies.",
    },
    {
        "name": "Misty Woods",
        "scroll_speed_mult": 1.1,
        "enemy_spawn_mult": 1.1,
        "enemy_damage_mult": 1.0,
        "story": "Trees hide dangers. Stay alert.",
    },
    {
        "name": "Frozen Ravine",
        "scroll_speed_mult": 1.15,
        "enemy_spawn_mult": 1.2,
        "enemy_damage_mult": 1.1,
        "story": "Slippery platforms and more aggressive foes.",
    },
    {
        "name": "Volcanic Run",
        "scroll_speed_mult": 1.25,
        "enemy_spawn_mult": 1.4,
        "enemy_damage_mult": 1.2,
        "story": "Only the bravest slimes make it this far.",
    },
    {
        "name": "Crimson Chasm",
        "scroll_speed_mult": 1.30,
        "enemy_spawn_mult": 1.6,
        "enemy_damage_mult": 1.25,
        "story": "Lava vents and tight jumps test your timing.",
    },
    {
        "name": "Shattered Bridges",
        "scroll_speed_mult": 1.35,
        "enemy_spawn_mult": 1.8,
        "enemy_damage_mult": 1.30,
        "story": "Fragile paths hang over a glowing abyss.",
    },
    {
        "name": "Twilight Dunes",
        "scroll_speed_mult": 1.40,
        "enemy_spawn_mult": 2.0,
        "enemy_damage_mult": 1.35,
        "story": "Desert winds carry faster foes your way.",
    },
    {
        "name": "Storm Peaks",
        "scroll_speed_mult": 1.45,
        "enemy_spawn_mult": 2.2,
        "enemy_damage_mult": 1.40,
        "story": "Icy ledges and lightning-fast flyers abound.",
    },
    {
        "name": "Obsidian Depths",
        "scroll_speed_mult": 1.50,
        "enemy_spawn_mult": 2.4,
        "enemy_damage_mult": 1.50,
        "story": "Dark caverns where enemies swarm relentlessly.",
    },
    {
        "name": "Ancient Skyway",
        "scroll_speed_mult": 1.55,
        "enemy_spawn_mult": 2.6,
        "enemy_damage_mult": 1.60,
        "story": "Floating ruins demand precise jumps and dashes.",
    },
    {
        "name": "Chaos Citadel",
        "scroll_speed_mult": 1.60,
        "enemy_spawn_mult": 2.8,
        "enemy_damage_mult": 1.70,
        "story": "Every mistake is punished. Few reach the end.",
    },
    {
        "name": "Endless Gauntlet",
        "scroll_speed_mult": 1.65,
        "enemy_spawn_mult": 3.0,
        "enemy_damage_mult": 1.80,
        "story": "The ultimate test of reflexes in Slimey.",
    },
]

# Auto-extend LEVEL_CONFIGS so there are 100 distinct difficulty steps.
if len(LEVEL_CONFIGS) < 100:
    last = LEVEL_CONFIGS[-1]
    scroll = float(last.get("scroll_speed_mult", 1.0))
    spawn = float(last.get("enemy_spawn_mult", 1.0))
    dmg = float(last.get("enemy_damage_mult", 1.0))

    for idx in range(len(LEVEL_CONFIGS) + 1, 101):
        scroll = round(scroll + 0.02, 2)
        spawn = round(spawn + 0.06, 2)
        dmg = round(dmg + 0.04, 2)
        LEVEL_CONFIGS.append({
            "name": f"Level {idx}",
            "scroll_speed_mult": scroll,
            "enemy_spawn_mult": spawn,
            "enemy_damage_mult": dmg,
            "story": "Keep going. It only gets tougher.",
        })


# ------------------------------------------------------------
#  PLATFORM CONFIG
# ------------------------------------------------------------
PLATFORM_TYPE_CONFIG = {
    "normal":  {"desc": "Regular platform."},
    "bounce":  {"desc": "Extra bouncy.", "bounce_mult": 1.4},
    "fall":    {"desc": "Falls shortly after being stepped on.", "fall_delay": 0.4},
    "fragile": {"desc": "Breaks after one jump.", "hits_to_break": 1},
}

PLATFORM_BASE_COLOR = (90, 120, 150)

PLATFORM_TYPE_COLORS = {
    "normal":  {"mode": "base"},
    "bounce":  {"mode": "add", "color": (20, 60, 20)},
    "fall":    {"mode": "add", "color": (60, 20, 20)},
    "fragile": {"mode": "add", "color": (60, 60, 0)},
}


# ------------------------------------------------------------
#  AUDIO CONFIG
# ------------------------------------------------------------
SOUND_JUMP_FILE = "jump.wav"
SOUND_COIN_FILE = "coin.wav"
SOUND_HIT_FILE = "hit.wav"
SOUND_LAND_FILE = "land.wav"

MUSIC_FILE = "music.ogg"
PER_LEVEL_MUSIC_PATTERN = "music_level_{n:02d}.ogg"

# Display toggles for the display settings menu
DISPLAY_TOGGLES = ["fullscreen", "vsync"]


# ------------------------------------------------------------
#  FX & PARTICLES
# ------------------------------------------------------------
FX_MODES = ["off", "scanlines", "crt", "bloom"]
PARTICLE_DENSITY_OPTIONS = ["low", "medium", "high"]

# Movement / level-up / hit FX tuning
RUN_DUST_INTERVAL = 0.08         # seconds between run dust puffs
DASH_TRAIL_INTERVAL = 0.045      # seconds between dash trail puffs
LEVELUP_PARTICLE_BASE_COUNT = 32 # sparks per level-up burst
HIT_FLASH_FREQUENCY = 12.0       # Hz for damage flash blink
COIN_PICKUP_PARTICLE_BASE_COUNT = 12  # sparks for coin pickups


# ------------------------------------------------------------
#  BOSS / SPECIAL LEVEL CONFIG
# ------------------------------------------------------------
BOSS_LEVELS = {5, 10, 20, 30, 50, 75, 100}
BOSS_WAVE_GROUND_COUNT = 3
BOSS_WAVE_FLYER_COUNT = 3
BOSS_WAVE_GROUND_SPACING = 80.0   # pixels between ground boss enemies
BOSS_WAVE_FLYER_SPACING = 70.0    # vertical pixels between flyers
BOSS_WAVE_FLYER_BASE_Y_RATIO = 0.25  # starting Y as fraction of screen height


# ------------------------------------------------------------
#  DIFFICULTY PRESETS
# ------------------------------------------------------------
DIFFICULTY_ORDER = ["Easy", "Normal", "Hard"]
DIFFICULTY_PRESETS = {
    "Easy": {
        "game_speed_mult": 0.9,
        "enemy_spawn_mult": 0.7,
        "enemy_damage_mult": 0.7,
    },
    "Normal": {
        "game_speed_mult": 1.0,
        "enemy_spawn_mult": 1.0,
        "enemy_damage_mult": 1.0,
    },
    "Hard": {
        "game_speed_mult": 1.1,
        "enemy_spawn_mult": 1.3,
        "enemy_damage_mult": 1.3,
    },
}


# ------------------------------------------------------------
#  UI SLIDERS (Gameplay / Audio / Display)
# ------------------------------------------------------------
GAMEPLAY_SLIDER_ORDER = [
    "move_speed_mult",
    "gravity_mult",
    "jump_mult",
    "game_speed_mult",
    "enemy_spawn_mult",
    "enemy_damage_mult",
]

GAMEPLAY_SLIDER_CONFIG = {
    "move_speed_mult": {"label": "Move Speed",  "min": 0.5, "max": 2.0, "step": 0.1},
    "gravity_mult":    {"label": "Gravity",     "min": 0.5, "max": 2.0, "step": 0.1},
    "jump_mult":       {"label": "Jump Height", "min": 0.5, "max": 2.0, "step": 0.1},
    "game_speed_mult": {"label": "Game Speed",  "min": 0.5, "max": 2.0, "step": 0.1},
    "enemy_spawn_mult":{"label": "Enemy Spawn", "min": 0.5, "max": 3.0, "step": 0.1},
    "enemy_damage_mult":{"label": "Enemy Damage","min": 0.5, "max": 3.0, "step": 0.1},
}

AUDIO_SLIDER_ORDER = ["music_volume"]

AUDIO_SLIDER_CONFIG = {
    "music_volume": {
        "label": "Music Volume",
        "min": 0.0,
        "max": 1.0,
        "step": 0.1,
    },
}


# ------------------------------------------------------------
#  UPGRADE COSTS (Shop)
# ------------------------------------------------------------
UPGRADE_COSTS = {
    "double_jump": 40,
    "coin_magnet": 30,
    "extra_heart": 60,
}


# ------------------------------------------------------------
#  MAIN MENU ITEMS
# ------------------------------------------------------------
MAIN_MENU_ITEMS = [
    {"id": "play",         "label": "Play"},
    {"id": "level_select", "label": "Level Select"},
    {"id": "level_editor", "label": "Level Editor"},
    {"id": "high_scores",  "label": "High Scores"},
    {"id": "skins",        "label": "Skins"},
    {"id": "how_to_play",  "label": "How to Play"},
    {"id": "settings",     "label": "Settings"},
    {"id": "quit",         "label": "Quit"},
]


# ------------------------------------------------------------
#  INPUT CONFIG (FULL REMAPPABLE)
# ------------------------------------------------------------
INPUT_CONFIG = {
    "keyboard": {
        "move_left":  ["K_a", "K_LEFT"],
        "move_right": ["K_d", "K_RIGHT"],
        "jump":       ["K_SPACE", "K_w", "K_UP"],
        "dash":       ["K_LSHIFT", "K_RSHIFT"],
        "pause":      ["K_ESCAPE"],
    },

    "controller": {
        "move_axis": 0,
        "move_deadzone": 0.3,
        "move_left":  ["HAT_LEFT"],
        "move_right": ["HAT_RIGHT"],
        "jump":        ["BTN_A"],
        "dash":        ["BTN_X", "BTN_Y"],
        "pause":       ["BTN_START"],
    },
}


# ------------------------------------------------------------
#  CONFIG OVERRIDES SUPPORT
# ------------------------------------------------------------
OVERRIDES_FILE = os.path.join(CONFIG_DIR, "config_overrides.json")


def _apply_overrides():
    """
    Override matching globals with values from config_overrides.json.
    Unknown keys are ignored.
    """
    if not os.path.exists(OVERRIDES_FILE):
        return

    try:
        with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[config] Failed to load overrides: {e}")
        return

    g = globals()
    for key, value in data.items():
        if key in g:
            g[key] = value
            print(f"[config] Overrode {key} from overrides")


_apply_overrides()
