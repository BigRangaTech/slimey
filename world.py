import random
import math
import pygame

from config import (
    GRAVITY,
    ENEMY_CONFIG,
    ENEMY_BEHAVIOR_CONFIG,
    PLATFORM_TYPE_CONFIG,
    LEVELUP_PARTICLE_BASE_COUNT,
    COIN_PICKUP_PARTICLE_BASE_COUNT,
)


# ============================================================
#  CORE RUN STATE
# ============================================================

def reset_state(player_rect, player_height, max_health):
    """
    Create the initial per-run state dictionary.
    """
    return {
        # Player physics
        "player_vel_y": 0.0,
        "on_ground": False,
        "was_on_ground": False,
        "ground_scroll_x": 0.0,

        # Entities
        "trees": [],
        "coins": [],
        "platforms": [],
        "enemies": [],
        "dust_particles": [],
        "spark_particles": [],
        "special_items": [],

        # Spawners: timestamps in ms
        "last_tree_spawn": 0,
        "last_coin_spawn": 0,
        "last_platform_spawn": 0,

        # Progress
        "score_time": 0.0,
        "coins_collected_run": 0,
        "level": 1,

        # Anim
        "animation_state": "idle",
        "animation_timer": 0.0,
        "animation_index": 0,

        # Misc timers
        "land_timer": 0.0,
        "jump_count": 0,

        # Health
        "health": max_health,
        "max_health": max_health,

        # Damage / knockback
        "invincible_timer": 0.0,
        "knockback_timer": 0.0,
        "knockback_dx": 0.0,

        # Level transition
        "level_transition_timer": 0.0,
        "achievement_popups": [],

        # Dash
        "dash_timer": 0.0,
        "dash_cooldown": 0.0,
        "dash_dir": 1,

        # Camera shake
        "shake_timer": 0.0,

        # Boss / special level helpers
        "boss_wave_spawned": False,

        # Movement FX timers (for dust trails)
        "run_dust_timer": 0.0,
        "dash_trail_timer": 0.0,

        # Achievement helpers
        "took_damage": False,
    }


# ============================================================
#  SIMPLE SPAWN HELPERS: TREES / COINS / PLATFORMS
# ============================================================

def spawn_tree(tree_img, screen_w, screen_h, scale_factor):
    """
    Spawn a tree at ground level off the right side of the screen.
    """
    if tree_img is None:
        w = int(64 * scale_factor)
        h = int(96 * scale_factor)
    else:
        w, h = tree_img.get_size()

    x = screen_w + random.randint(int(10 * scale_factor), int(120 * scale_factor))
    y = screen_h - h
    return pygame.Rect(x, y, w, h)


def spawn_coin(screen_w, screen_h, coin_img, scale_factor, platform_rect=None):
    """
    Spawn a coin either above a platform or in midair.
    """
    if coin_img is None:
        size = int(32 * scale_factor)
        w = h = size
    else:
        w, h = coin_img.get_size()

    if platform_rect:
        x = random.randint(platform_rect.left + w // 2, platform_rect.right - w // 2)
        y = platform_rect.top - h - int(10 * scale_factor)
    else:
        x = screen_w + random.randint(int(40 * scale_factor), int(140 * scale_factor))
        y = random.randint(int(screen_h * 0.25), int(screen_h * 0.65))

    return pygame.Rect(x, y, w, h)


def spawn_platform(screen_w, screen_h, scale_factor):
    """
    Spawn a moving/static platform with a random type/height.
    Returns a dict describing the platform.
    """
    width = int(random.randint(160, 260) * scale_factor)
    height = int(24 * scale_factor)

    x = screen_w + random.randint(int(20 * scale_factor), int(220 * scale_factor))
    y_min = int(screen_h * 0.25)
    y_max = int(screen_h * 0.7)
    y = random.randint(y_min, y_max)

    # pick type with simple weighting
    types = list(PLATFORM_TYPE_CONFIG.keys())
    weights = []
    for t in types:
        if t == "normal":
            weights.append(5.0)
        elif t == "bounce":
            weights.append(1.5)
        else:
            weights.append(1.0)

    ptype = random.choices(types, weights=weights, k=1)[0]

    vx = 0.0
    # Some platforms gently drift horizontally
    if ptype in ("normal", "bounce") and random.random() < 0.25:
        vx = random.choice([-1, 1]) * random.uniform(40.0, 80.0)

    return {
        "rect": pygame.Rect(x, y, width, height),
        "type": ptype,
        "vx": vx,
        "vy": 0.0,
        "fall_started": False,
        "fall_timer": 0.0,
        "fragile_hits": 0,
        "depth": random.uniform(0.9, 1.1),
    }


# ============================================================
#  ENEMY SPAWNING
# ============================================================

def _make_enemy_rect(kind, enemy_sprites, scale_factor):
    img = enemy_sprites.get(kind)
    if img is not None:
        w, h = img.get_size()
    else:
        size = int(48 * scale_factor)
        w = h = size
    return pygame.Rect(0, 0, w, h)


def spawn_platform_enemy(plat_rect, enemy_sprite, scale_factor, kind="walker"):
    """
    Spawn a platform enemy of 'kind' standing on a platform rect.
    NOTE: slime_platformer passes enemy_sprites[kind] here as enemy_sprite.
    """
    # ENEMY_CONFIG may not strictly need 'kind' here, but keep for symmetry
    _ = ENEMY_CONFIG.get(kind, {})

    if enemy_sprite is not None:
        w, h = enemy_sprite.get_size()
    else:
        size = int(48 * scale_factor)
        w = h = size

    r = pygame.Rect(0, 0, w, h)
    r.midbottom = (plat_rect.centerx, plat_rect.top)

    return {
        "kind": kind,
        "rect": r,
        "vx": 0.0,
        "vy": 0.0,
        "t": 0.0,
        "state": "idle",
        "base_y": float(r.centery),
    }


def spawn_air_enemy(kind, enemy_sprites, screen_w, screen_h, speed_mult, scale_factor):
    """
    Spawn an air enemy (flyer).
    """
    cfg = ENEMY_CONFIG.get(kind)
    if cfg is None:
        return None

    r = _make_enemy_rect(kind, enemy_sprites, scale_factor)
    r.x = screen_w + random.randint(int(20 * scale_factor), int(120 * scale_factor))
    r.y = random.randint(int(screen_h * 0.2), int(screen_h * 0.6))

    speed = cfg.get("speed", 160.0) * speed_mult

    return {
        "kind": kind,
        "rect": r,
        "vx": -speed,
        "vy": 0.0,
        "t": 0.0,
        "state": "fly",
        "base_y": float(r.centery),
    }


def spawn_ground_enemy(kind, enemy_sprites, screen_w, screen_h, scale_factor):
    """
    Spawn a ground enemy
    """
    cfg = ENEMY_CONFIG.get(kind)
    if cfg is None:
        return None

    r = _make_enemy_rect(kind, enemy_sprites, scale_factor)
    r.y = screen_h - r.height
    r.x = screen_w + random.randint(int(30 * scale_factor), int(160 * scale_factor))

    speed = cfg.get("speed", 140.0)

    return {
        "kind": kind,
        "rect": r,
        "vx": -speed,
        "vy": 0.0,
        "t": 0.0,
        "state": "run",
        "base_y": float(r.centery),
        "jump_cooldown": 0.0,
    }


# ============================================================
#  PARTICLES
# ============================================================

def spawn_dust_particles(x, y, scale_factor, density="medium"):
    base_count = {"low": 6, "medium": 10, "high": 16}.get(density, 10)
    parts = []
    for _ in range(base_count):
        angle = random.uniform(-math.pi, 0)
        speed = random.uniform(60, 160) * scale_factor
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed * 0.4
        size = random.randint(int(4 * scale_factor), int(8 * scale_factor))
        parts.append({
            "x": float(x),
            "y": float(y),
            "vx": vx,
            "vy": vy,
            "size": size,
            "color": (200, 200, 200),
            "life": 0.0,
            "max_life": random.uniform(0.35, 0.6),
        })
    return parts


def spawn_spark_burst(x, y, scale_factor, density="medium", base_count=None):
    mult = {"low": 0.7, "medium": 1.0, "high": 1.4}.get(density, 1.0)
    if base_count is None:
        base_count = COIN_PICKUP_PARTICLE_BASE_COUNT
    count = max(4, int(base_count * mult))
    parts = []
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(140, 260) * scale_factor
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        size = random.randint(int(3 * scale_factor), int(6 * scale_factor))
        parts.append({
            "x": float(x),
            "y": float(y),
            "vx": vx,
            "vy": vy,
            "size": size,
            "color": (255, 230, 120),
            "life": 0.0,
            "max_life": random.uniform(0.4, 0.7),
        })
    return parts


def spawn_levelup_burst(x, y, scale_factor, density="medium"):
    # Slightly denser burst for level-ups to feel special
    return spawn_spark_burst(
        x,
        y,
        scale_factor,
        density=density,
        base_count=LEVELUP_PARTICLE_BASE_COUNT,
    )


def update_particles(particles, dt, gravity, scale_factor):
    """
    Integrate particles with simple gravity + fade.
    """
    new_list = []
    for p in particles:
        p["life"] += dt
        if p["life"] >= p["max_life"]:
            continue
        p["vy"] += gravity * 0.2 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        new_list.append(p)
    return new_list


# ============================================================
#  ENEMY BEHAVIOR / AI
# ============================================================

def _update_enemy_behavior(enemy, dt, game_speed, scale_factor, player_rect, screen_w, screen_h):
    """
    Apply config-driven behavior to a single enemy.
    """
    kind = enemy["kind"]
    rect = enemy["rect"]
    cfg = ENEMY_CONFIG.get(kind, {})
    bcfg = ENEMY_BEHAVIOR_CONFIG.get(kind, {})
    behavior_type = bcfg.get("type", "plain")

    enemy.setdefault("t", 0.0)
    enemy["t"] += dt

    vx = enemy.get("vx", 0.0)
    vy = enemy.get("vy", 0.0)

    if behavior_type == "patrol":
        # Basic walker: moves left, scroll subtracts from it
        speed = cfg.get("speed", 120.0)
        if vx == 0.0:
            vx = -speed
        rect.x += int(vx * dt)
        rect.x -= int(game_speed * dt)

        if rect.right < -100:
            enemy["remove"] = True

    elif behavior_type == "sine_fly":
        # Flyer with sine-wave vertical movement
        base_y = enemy.setdefault("base_y", float(rect.centery))
        speed = cfg.get("speed", 160.0)
        amplitude = bcfg.get("amplitude", 40.0) * scale_factor
        freq = bcfg.get("frequency", 1.4)

        rect.x -= int((speed + game_speed) * dt)
        rect.centery = int(base_y + math.sin(enemy["t"] * freq) * amplitude)

        if rect.right < -100:
            enemy["remove"] = True

    elif behavior_type == "jump":
        # Jumper type: runs and occasionally jumps
        speed = cfg.get("speed", 130.0)
        jump_interval = bcfg.get("jump_interval", 2.0)
        jump_force = bcfg.get("jump_force", -750.0) * scale_factor

        rect.x -= int((speed + game_speed * 0.7) * dt)

        cd = enemy.get("jump_cooldown", random.uniform(0.0, jump_interval))
        cd -= dt
        if cd <= 0.0:
            vy = jump_force
            cd = jump_interval
        enemy["jump_cooldown"] = cd

        vy += GRAVITY * 0.9 * dt
        rect.y += int(vy * dt)
        if rect.bottom >= screen_h:
            rect.bottom = screen_h
            vy = 0.0

        enemy["vy"] = vy

        if rect.right < -120:
            enemy["remove"] = True

    else:
        # Default: move by vx/vy and scroll with game speed
        rect.x += int(vx * dt)
        rect.y += int(vy * dt)
        rect.x -= int(game_speed * dt)
        if rect.right < -120:
            enemy["remove"] = True

    if rect.left > screen_w + 200 or rect.top > screen_h + 200 or rect.bottom < -200:
        enemy["remove"] = True


def update_enemies(enemies, dt, game_speed, scale_factor, player_rect, screen_w, screen_h):
    """
    Update all enemies and cull off-screen ones.
    """
    updated = []
    for e in enemies:
        e["remove"] = False
        _update_enemy_behavior(e, dt, game_speed, scale_factor, player_rect, screen_w, screen_h)
        if not e.get("remove", False):
            updated.append(e)
    return updated
