"""
Utility script to generate extra game assets using pygame.

Run from the project root:
    python generate_assets.py

It will:
  - Create tinted slime skins (green, purple, gold) based on the default skin.
  - Create a few extra global background variants by tinting existing ones.

Nothing existing is overwritten: files are only written if they do not exist.
"""

import os
import sys

try:
    import pygame
except ImportError:
    print("Pygame is not installed. Install it with:")
    print("  python -m pip install pygame")
    sys.exit(1)

import config


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")


def ensure_display():
    """
    Make sure pygame has a tiny display so convert_alpha() etc. work.
    (Needed when running as an offline generator script.)
    """
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))


def tint_surface(surface, rgb):
    """Return a tinted copy of a surface."""
    tinted = surface.copy().convert_alpha()
    # Multiply existing pixels by the tint color
    tinted.fill((*rgb, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def generate_tinted_skins():
    """
    Create extra skins (green, purple, gold) in assets/skins/
    based on assets/skins/default/ idle/run/jump frames.
    """
    ensure_display()

    skins_root = os.path.join(ASSETS_DIR, "skins")
    default_dir = os.path.join(skins_root, "default")

    if not os.path.isdir(default_dir):
        print("[skins] Default skin directory not found:", default_dir)
        return

    colors = {
        "green": (140, 255, 160),
        "purple": (220, 160, 255),
        "gold": (255, 230, 150),
    }
    frame_names = ["idle.png", "run.png", "jump.png"]

    for skin_name, rgb in colors.items():
        dst_dir = os.path.join(skins_root, skin_name)
        ensure_dir(dst_dir)
        wrote_any = False

        for fname in frame_names:
            src_path = os.path.join(default_dir, fname)
            dst_path = os.path.join(dst_dir, fname)

            if not os.path.exists(src_path):
                continue
            if os.path.exists(dst_path):
                # Keep user-modified or existing art
                continue

            try:
                surf = pygame.image.load(src_path).convert_alpha()
            except Exception as e:
                print(f"[skins] Failed loading {src_path}: {e}")
                continue

            tinted = tint_surface(surf, rgb)
            try:
                pygame.image.save(tinted, dst_path)
                wrote_any = True
                print(f"[skins] Wrote {dst_path}")
            except Exception as e:
                print(f"[skins] Failed saving {dst_path}: {e}")

        if not wrote_any:
            print(f"[skins] No new files written for skin '{skin_name}' (they may already exist).")


def generate_extra_backgrounds():
    """
    Create a couple of extra global background series by tinting background1_*.
    Outputs to assets/backgrounds/background4_*.png, background5_*.png, etc.
    """
    ensure_display()

    bg_root = os.path.join(ASSETS_DIR, "backgrounds")
    if not os.path.isdir(bg_root):
        print("[bg] Backgrounds folder not found:", bg_root)
        return

    base_idx = 1
    layers = ["far", "mid", "near"]

    def load_layer(idx, layer):
        path = os.path.join(bg_root, f"background{idx}_{layer}.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"[bg] Failed loading {path}: {e}")
            return None

    # Use background1_* as the template if available
    base_layers = {layer: load_layer(base_idx, layer) for layer in layers}
    if not any(base_layers.values()):
        print("[bg] No base background1_far/mid/near.png found; skipping background generation.")
        return

    # Define a few tints for new background indices
    new_sets = {
        4: (180, 220, 255),  # pale blue
        5: (255, 210, 180),  # warm sunset
        6: (200, 200, 255),  # cool night
    }

    for idx, tint_rgb in new_sets.items():
        for layer in layers:
            src = base_layers.get(layer)
            if src is None:
                continue

            dst_path = os.path.join(bg_root, f"background{idx}_{layer}.png")
            if os.path.exists(dst_path):
                continue  # don't overwrite

            tinted = tint_surface(src, tint_rgb)
            try:
                pygame.image.save(tinted, dst_path)
                print(f"[bg] Wrote {dst_path}")
            except Exception as e:
                print(f"[bg] Failed saving {dst_path}: {e}")


def generate_world_backgrounds_from_global():
    """
    For each WORLD_PACK in config.WORLD_PACKS that doesn't already have
    layered backgrounds, create a simple tinted set based on the global
    background1_* layers.

    Outputs to:
        assets/worlds/<world_id>/backgrounds/background1_far|mid|near.png
    """
    ensure_display()

    bg_root = os.path.join(ASSETS_DIR, "backgrounds")
    worlds_root = os.path.join(ASSETS_DIR, "worlds")

    if not os.path.isdir(bg_root) or not os.path.isdir(worlds_root):
        return

    layers = ["far", "mid", "near"]

    # Collect a few global background sets (1..3) to use as templates.
    indices = [1, 2, 3]

    def load_global_layer(idx, layer):
        path = os.path.join(bg_root, f"background{idx}_{layer}.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"[world bg] Failed loading {path}: {e}")
            return None

    global_sets = {}
    for idx in indices:
        layer_map = {layer: load_global_layer(idx, layer) for layer in layers}
        if any(layer_map.values()):
            global_sets[idx] = layer_map

    if not global_sets:
        return

    for world_id, cfg in config.WORLD_PACKS.items():
        world_folder = os.path.join(worlds_root, world_id)
        bg_folder = os.path.join(world_folder, "backgrounds")

        os.makedirs(bg_folder, exist_ok=True)

        tint = cfg.get("tint") or config.DEFAULT_LEVEL_TINT
        rgb = tuple(tint[:3])

        for idx, layer_map in global_sets.items():
            for layer in layers:
                base = layer_map.get(layer)
                if base is None:
                    continue

                dst_path = os.path.join(bg_folder, f"background{idx}_{layer}.png")
                if os.path.exists(dst_path):
                    continue

                tinted = tint_surface(base, rgb)
                try:
                    pygame.image.save(tinted, dst_path)
                    print(f"[world bg] Wrote {dst_path}")
                except Exception as e:
                    print(f"[world bg] Failed saving {dst_path}: {e}")


def generate_fx_overlays():
    """
    Ensure scanlines/crt mask overlays exist where the game loader expects:
        assets/scanlines.png
        assets/crt_mask.png

    If the user has versions in assets/fx/, copy them; otherwise generate
    simple retro-style placeholders.
    """
    ensure_display()

    fx_root = os.path.join(ASSETS_DIR, "fx")

    def ensure_overlay(target_name, source_name=None, pattern="scanlines"):
        target_path = os.path.join(ASSETS_DIR, target_name)
        if os.path.exists(target_path):
            return

        src_path = None
        if source_name is not None and os.path.isdir(fx_root):
            candidate = os.path.join(fx_root, source_name)
            if os.path.exists(candidate):
                src_path = candidate

        if src_path:
            try:
                surf = pygame.image.load(src_path).convert_alpha()
                pygame.image.save(surf, target_path)
                print(f"[fx] Copied {src_path} -> {target_path}")
                return
            except Exception as e:
                print(f"[fx] Failed copying {src_path}: {e}")

        # Fallback: generate a simple placeholder overlay
        width, height = 1920, 1080
        surf = pygame.Surface((width, height), pygame.SRCALPHA)

        if pattern == "scanlines":
            # Dark transparent horizontal lines
            for y in range(0, height, 4):
                pygame.draw.line(surf, (0, 0, 0, 60), (0, y), (width, y))
        elif pattern == "crt":
            # Soft vignette-style mask
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 0))
            pygame.draw.rect(
                overlay,
                (0, 0, 0, 120),
                overlay.get_rect().inflate(-80, -80),
                border_radius=40,
            )
            surf.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

        try:
            pygame.image.save(surf, target_path)
            print(f"[fx] Generated placeholder {target_path}")
        except Exception as e:
            print(f"[fx] Failed saving placeholder {target_path}: {e}")

    ensure_overlay("scanlines.png", "scanlines.png", pattern="scanlines")
    ensure_overlay("crt_mask.png", "crt_mask.png", pattern="crt")


def main():
    generate_tinted_skins()
    generate_extra_backgrounds()
    generate_world_backgrounds_from_global()
    generate_fx_overlays()
    print("Done. Launch the game to see new skins, backgrounds, and FX overlays.")


if __name__ == "__main__":
    main()
