import os
import json
import random


BASE_DIR = os.path.join("levels", "custom")
SCREEN_W, SCREEN_H = 1920, 1080


def make_level(level_idx: int):
    random.seed(level_idx)

    difficulty = 0.5 + (level_idx - 1) / 99.0

    platforms = []
    coins = []
    enemies = []

    plat_count = 5 + int(10 * difficulty)

    x = 260
    for i in range(plat_count):
        width = random.randint(180, 260)
        height = 24
        y_base = SCREEN_H * 0.45 + (i % 3) * 70
        y_jitter = random.randint(-40, 40)
        y = int(min(SCREEN_H * 0.8, max(SCREEN_H * 0.25, y_base + y_jitter)))

        if difficulty < 0.4:
            ptype = "normal"
        else:
            roll = random.random()
            if roll < 0.6:
                ptype = "normal"
            elif roll < 0.8:
                ptype = "bounce"
            elif roll < 0.9:
                ptype = "fall"
            else:
                ptype = "fragile"

        platforms.append(
            {
                "x": int(x),
                "y": int(y),
                "w": int(width),
                "h": int(height),
                "type": ptype,
            }
        )

        if random.random() < 0.75:
            coin_stack = 1 + (1 if random.random() < difficulty else 0)
            for c in range(coin_stack):
                coins.append(
                    {
                        "x": int(x + width * 0.5 + random.randint(-20, 20)),
                        "y": int(y - 40 - c * 22),
                    }
                )

        if random.random() < (0.3 + 0.4 * difficulty):
            kind_roll = random.random()
            if kind_roll < 0.5:
                kind = "walker"
            elif kind_roll < 0.8:
                kind = "jumper"
            else:
                kind = "flyer"
            enemies.append(
                {
                    "x": int(x + width * random.uniform(0.2, 0.8)),
                    "y": int(y - 10 if kind != "flyer" else y - 120),
                    "kind": kind,
                }
            )

        x += width + random.randint(80, 200)

    return {
        "platforms": platforms,
        "coins": coins,
        "enemies": enemies,
    }


def main():
    os.makedirs(BASE_DIR, exist_ok=True)

    for level in range(1, 101):
        path = os.path.join(BASE_DIR, f"level_{level:02d}.json")
        if os.path.exists(path):
            continue
        data = make_level(level)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()

