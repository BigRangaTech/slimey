# ============================================================
#  Slimey - ENEMY LOGIC HELPERS
# ------------------------------------------------------------
# Centralised place to decide:
#  - which enemy kinds are enabled at a given level
#  - how spawn weights scale with level
#  - how to randomly pick an enemy kind given config
#
#  This is *not* strictly required by the current main loop,
#  but can be used from slime_platformer.py to keep enemy
#  tuning in one place.
# ============================================================

import random

from config import (
    ENEMY_CONFIG,
    ENEMY_BEHAVIOR_CONFIG,
    ENEMY_LEVEL_SCALING,
    LEVEL_ENEMY_CONFIG,
)


def get_enabled_enemy_kinds(level: int) -> list[str]:
    """
    Return the list of enemy kinds allowed at this level
    based on LEVEL_ENEMY_CONFIG.
    """
    # per-level override
    per_level = LEVEL_ENEMY_CONFIG.get("by_level", {})
    if level in per_level:
        kinds = per_level[level].get("enabled_kinds")
        if kinds:
            return [k for k in kinds if k in ENEMY_CONFIG]

    # fallback to default
    default = LEVEL_ENEMY_CONFIG.get("default", {})
    kinds = default.get("enabled_kinds", list(ENEMY_CONFIG.keys()))
    return [k for k in kinds if k in ENEMY_CONFIG]


def get_base_spawn_weight(kind: str) -> float:
    """
    Base spawn "weight" from ENEMY_CONFIG. If no explicit,
    use a small default so the type is still eligible.
    """
    cfg = ENEMY_CONFIG.get(kind, {})
    # use spawn_chance as baseline, or a default
    base = cfg.get("spawn_chance", 0.05)
    return float(base) if base > 0 else 0.02


def get_level_scaled_spawn_weight(kind: str, level: int) -> float:
    """
    Apply ENEMY_LEVEL_SCALING to gradually increase spawn weight
    for tougher enemies at higher levels.
    """
    base = get_base_spawn_weight(kind)
    scfg = ENEMY_LEVEL_SCALING.get(kind)
    if not scfg:
        return base

    threshold = scfg.get("level_threshold", 1)
    per_level = scfg.get("spawn_scale_per_level", 0.0)
    if level <= threshold or per_level <= 0:
        return base

    extra_levels = max(0, level - threshold)
    return base * (1.0 + extra_levels * per_level)


def build_spawn_table(level: int) -> list[tuple[str, float]]:
    """
    Build a list of (kind, weight) for all enabled enemies at this level.
    """
    kinds = get_enabled_enemy_kinds(level)
    table: list[tuple[str, float]] = []
    for k in kinds:
        w = get_level_scaled_spawn_weight(k, level)
        if w > 0:
            table.append((k, w))
    return table


def pick_enemy_kind(level: int, rng=random.random) -> str | None:
    """
    Pick a random enemy kind based on the spawn table for a given level.
    Returns None if no enemy is configured.
    """
    table = build_spawn_table(level)
    if not table:
        return None

    total = sum(w for _, w in table)
    if total <= 0:
        return None

    r = rng() * total
    acc = 0.0
    for kind, w in table:
        acc += w
        if r <= acc:
            return kind

    return table[-1][0]


def describe_enemy(kind: str) -> str:
    """
    Return a short human-readable description of an enemy type,
    based on ENEMY_CONFIG and ENEMY_BEHAVIOR_CONFIG.
    """
    cfg = ENEMY_CONFIG.get(kind, {})
    bcfg = ENEMY_BEHAVIOR_CONFIG.get(kind, {})

    spawn_type = cfg.get("spawn_type", "unknown")
    dmg = cfg.get("damage", 1)
    speed = cfg.get("speed", 0)
    behavior = bcfg.get("type", "plain")

    return f"{kind} — {behavior} ({spawn_type}), dmg {dmg}, speed {speed}"


def debug_spawn_table(level: int) -> str:
    """
    Build a debug string showing the spawn weights at a given level.
    Useful when tuning ENEMY_CONFIG / ENEMY_LEVEL_SCALING.
    """
    table = build_spawn_table(level)
    if not table:
        return f"Level {level}: no enemies enabled."

    parts = [f"Level {level} spawn table:"]
    total = sum(w for _, w in table)
    for kind, w in table:
        pct = (w / total) * 100 if total > 0 else 0
        parts.append(f"  - {kind}: weight {w:.3f} ({pct:.1f}%)")
    return "\n".join(parts)
