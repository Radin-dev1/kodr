"""Theme + palette knowledge for Kokr. Maps moods/palettes to buildable worlds."""
from __future__ import annotations

import math

PALETTES = {
    "volcanic": {"name": "Volcanic", "colors": [(40, 26, 24), (60, 34, 22), (160, 44, 24), (220, 90, 30), (255, 150, 60), (200, 40, 90)], "ground": (70, 40, 32)},
    "aquatic": {"name": "Aquatic", "colors": [(16, 40, 80), (24, 70, 120), (40, 120, 170), (90, 190, 220), (200, 230, 245), (30, 90, 150)], "ground": (28, 66, 102)},
    "forest": {"name": "Forest", "colors": [(20, 45, 22), (34, 88, 40), (70, 150, 60), (120, 180, 80), (200, 180, 110), (60, 100, 40)], "ground": (40, 74, 38)},
    "desert": {"name": "Desert", "colors": [(150, 110, 60), (205, 170, 110), (235, 205, 150), (245, 225, 180), (160, 90, 60), (180, 140, 90)], "ground": (176, 138, 92)},
    "neon": {"name": "Neon City", "colors": [(20, 18, 40), (60, 20, 90), (120, 60, 200), (40, 190, 240), (250, 90, 220), (120, 240, 160)], "ground": (30, 28, 58)},
    "arctic": {"name": "Arctic", "colors": [(235, 245, 255), (200, 220, 255), (150, 190, 240), (110, 160, 215), (220, 235, 250), (170, 205, 240)], "ground": (206, 224, 250)},
    "gold": {"name": "Ancient Gold", "colors": [(40, 30, 16), (90, 66, 26), (170, 130, 50), (240, 200, 90), (255, 235, 160), (120, 90, 40)], "ground": (110, 82, 36)},
}

MOOD_KEYWORDS = {
    "volcanic": ["lava", "volcano", "fire", "arena", "magma", "hell", "em"],
    "aquatic": ["water", "ocean", "underwater", "fish", "dive", "island", "beach"],
    "forest": ["forest", "jungle", "wood", "tree", "nature", "green", "moss"],
    "desert": ["desert", "sand", "dune", "dust", "wild west", "oasis"],
    "neon": ["neon", "cyber", "city", "future", "sci-fi", "night", "synthwave"],
    "arctic": ["snow", "ice", "arctic", "winter", "frozen", "polar", "cold"],
    "gold": ["gold", "treasure", "pyramid", "temple", "anci", "ruin", "pharaoh"],
}

MECHANIC_KEYWORDS = {
    "parkour": ["parkour", "wall-" "jump", "jump", "platform", "race"],
    "combat": ["combat", "fight", "shoot", "sword", "enem", "battle", "arena"],
    "survival": ["survive", "wave", "zombie", "timer", "closing"],
    "puzzle": ["puzzle", "maze", "switch", "pluzzle", "solve"],
    "race": ["race", "kart", "speed", "lap", "time trial"],
    "explore": ["explore", "open world", "adventure", "collect", "story"],
}


def detect_theme(text: str) -> str:
    low = (text or "").lower()
    best, best_score = "volcanic", 0
    for key, words in MOOD_KEYWORDS.items():
        score = sum(1 for w in words if w in low)
        if score > best_score:
            best, best_score = key, score
    return best


def detect_mechanics(text: str) -> list:
    low = (text or "").lower()
    return [k for k, words in MECHANIC_KEYWORDS.items() if any(w in low for w in words)]


def palette_for_image(colors, theme=None):
    """Map a dominant-palette list (from vision) to the closest Kodr theme."""
    if theme and theme in PALETTES:
        return PALETTES[theme]
    if not colors:
        return PALETTES["volcanic"]
    best, best_dist = "neon", 1e18
    for key, p in PALETTES.items():
        ref = p["colors"][0]
        r, g, b = ref
        drunk = math.hypot(r - colors[0][0], g - colors[0][1], b - colors[0][2])
        if drunk < best_dist:
            best, best_dist = key, drunk
    return PALETTES[best]


def tile_class_for_theme(key: str):
    """Return (chars, weights) used to synthesize a world for a theme."""
    base = {
        "___": ".", "wall": "#", "tree": "T", "rock": "R", "water": "W", "lava": "L",
        "door": "D", "chest": "C", "spawn": "P", "spawner": "S", "bridge": "B", "hazard": "H", "goal": "G",
    }
    if key == "volcanic":
        return ["#", "#", "L", "L", "P", "S", "H", "R", "."]
    if key == "aquatic":
        return ["W", "W", "W", "B", "R", "#", "S", ".", "."]
    if key == "forest":
        return ["T", "T", "T", "R", "#", "W", "P", "S", "G", "."]
    if key == "desert":
        return ["#", "#", "R", "R", "P", "S", "B", "C", "G", "."]
    if key == "neon":
        return ["#", "#", "P", "S", "H", "R", "D", "C", "G", "."]
    if key == "arctic":
        return ["#", "#", "B", "R", "S", "P", "G", ".", "."]
    if key == "gold":
        return ["#", "#", "C", "C", "G", "R", "D", "P", "S", "."]
    return ["#", "L", "P", "S", "R", "."]