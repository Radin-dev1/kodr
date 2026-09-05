"""Nova-1 — fully offline game-code generation.

Turns a plain-English prompt into modular game code for Roblox (Luau),
Python, Unity (C#), Godot (GDScript) or Unreal (C++). No LLM, no network:
packaged templates are composed from the theme + mechanics detected in the
prompt and the procedural world grid.
"""
from __future__ import annotations

import hashlib
import os
import random
import re
import tempfile

from . import theme as theme_mod
from . import three_d

TILE_HEIGHT = three_d.TILE_HEIGHT

ENGINES = {
    "python": {"label": "Python", "ext": ".py", "complete": True},
    "roblox": {"label": "Roblox Studio", "ext": ".lua", "complete": True},
    "unity": {"label": "Unity (C#)", "ext": ".cs", "complete": False},
    "godot": {"label": "Godot (GDScript)", "ext": ".gd", "complete": False},
    "unreal": {"label": "Unreal (C++)", "ext": ".cpp", "complete": False},
}

PLAYABLE_WORDS = {
    "spring": ["A", "D", "S", "S", "A", "D", "."],
    "combat": ["M", "M", "M", "P", "D", ".", "."],
    "parkour": ["#", "G", "P", "C", ".", ".", "."],
    "race": ["G", "P", "C", ".", ".", "#", "#"],
    "survival": ["M", "P", ".", ".", "C", "#"],
    "puzzle": ["K", "D", "P", ".", "#", "#", "C"],
    "explore": ["C", "C", "C", "P", "G", ".", "#"],
}


def _as_hex(color):
    return "#%02x%02x%02x" % tuple(color)


def _slug(text):
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)[:48].strip("_")
    return s or "nova_game"


ENEMIES = {
    "slime": ["slime", "blob", "goo", "mold"],
    "zombie": ["zombie", "undead", "horde", "crawler"],
    "drone": ["drone", "robot", "turret", "machin", "droid"],
    "skeleton": ["skeleton", "bone", "soldier", "guard", "warrior"],
    "kraken": ["kraken", "tentacle", "octop", "seamonster"],
    "shade": ["ghost", "spirit", "shadow", "wraith", "shade"],
}
ENEMY_RGB = {
    "slime": (120, 220, 90), "zombie": (150, 170, 60), "drone": (210, 60, 210),
    "skeleton": (225, 220, 205), "kraken": (60, 120, 190), "shade": (155, 120, 190),
}
ENEMY_PLURAL = {
    "slime": "slimes", "zombie": "zombies", "drone": "drones",
    "skeleton": "skeletons", "kraken": "krakens", "shade": "shades",
}
HARD_WORDS = ["hard", "brutal", "swarm", "horde", "nightmare", "endless", "dense",
              "many", "intense", "insane", "deadly", "dangerous", "invasion"]
EASY_WORDS = ["easy", "chill", "calm", "few", "light", "casual", "cozy", "gentle",
              "peaceful", "relaxing", "beginner"]
OBJECTIVE_WORDS = {
    "survive": ["surviv", "wave", "hold", "defend", "stand your ground"],
    "collect": ["collect", "gather", "loot", "gem", "treasure", "crystal", "coin", "artifact"],
    "reach": ["reach", "beacon", "final", "gate", "goal", "end", "escape", "finish"],
}


def features(text):
    low = (text or "").lower()
    enemy = "drone"
    for key, words in ENEMIES.items():
        if any(w in low for w in words):
            enemy = key
            break
    hard = sum(1 for w in HARD_WORDS if w in low)
    easy = sum(1 for w in EASY_WORDS if w in low)
    difficulty = "hard" if hard > easy else ("easy" if easy > hard else "normal")
    density = max(0.18, min(0.62, 0.36 + 0.12 * hard - 0.10 * easy))
    objective = "reach"
    for key, words in OBJECTIVE_WORDS.items():
        if any(w in low for w in words):
            objective = key
            break
    weapons = [w for w in ["bow", "laser", "flame", "sword", "staff", "cannon", "ice", "dagger"]
               if w in low]
    objectives = {
        "survive": "Hold out against the %s until relief arrives." % ENEMY_PLURAL[enemy],
        "collect": "Gather every shard and escape through the gate.",
        "reach": "Reach the goal beacon alive while the %s hunt you." % ENEMY_PLURAL[enemy],
    }
    victory = {
        "survive": "You survived the onslaught. Victory!",
        "collect": "All shards gathered. Victory!",
        "reach": "Beacon reached. Victory!",
    }
    return {
        "enemy": enemy,
        "enemy_name": enemy.title(),
        "enemy_rgb": ENEMY_RGB[enemy],
        "difficulty": difficulty,
        "density": density,
        "objective": objective,
        "objective_text": objectives[objective],
        "victory_text": victory[objective],
        "weapons": weapons or ["basic"],
    }


DIFF_STATS = {
    "easy": {"monsters": 4, "hp": 160, "ammo": 12, "turns": 320, "waves": 3, "waves_base": 1},
    "normal": {"monsters": 7, "hp": 100, "ammo": 6, "turns": 240, "waves": 4, "waves_base": 2},
    "hard": {"monsters": 11, "hp": 70, "ammo": 4, "turns": 170, "waves": 6, "waves_base": 3},
}


def concept(text):
    """Analyze a prompt into theme / palette / mechanics / playables."""
    theme_key = theme_mod.detect_theme(text)
    mechanics = theme_mod.detect_mechanics(text)
    archetype = (mechanics[0] if mechanics else "explore")
    if archetype not in PLAYABLE_WORDS:
        archetype = "explore"
    pal = theme_mod.PALETTES[theme_key]["colors"]
    return {
        "title": _slug(text or "planet"),
        "theme": theme_key,
        "theme_name": theme_mod.PALETTES[theme_key]["name"],
        "palette_rgb": pal,
        "palette_hex": [_as_hex(c) for c in pal],
        "mechanics": mechanics or [archetype],
        "archetype": archetype,
        "features": features(text),
        "stats": DIFF_STATS[features(text)["difficulty"]],
    }


# --------------------------------------------------------------------------- world grid


def world_grid(seed=None, size=16, density=0.45):
    """Deterministic procedural grid (list of strings) for a prompt."""
    if seed is None:
        seed = 1
    rows = []
    for y in range(size):
        row = []
        rng = random.Random((seed) * 1000 + y * 97 + (y * 31))
        for x in range(size):
            p = rng.random()
            rng = random.Random((seed) * 1000 + y * 97 + x * 31)
            p = rng.random()
            if p < density * 1.15:
                row.append("#")
            elif p < density * 1.15 + 0.05:
                row.append("W")
            elif p < density * 1.15 + 0.10:
                row.append("C")
            elif p < density * 1.15 + 0.14:
                row.append("M")
            elif p < density * 1.15 + 0.17:
                row.append("K")
            elif p < density * 1.15 + 0.20:
                row.append("D")
            else:
                row.append(".")
        rows.append("".join(row))
    # carve a clear path from top-left to bottom-right
    x, y = 0, 0
    rows[y] = rows[y][:x] + "P" + rows[y][x + 1:]
    seen = {"%d,%d" % (x, y)}
    for _ in range(size * 3):
        if x == size - 1 and y == size - 1:
            break
        if random.Random((seed or 1) * 7 + x + y * 13).random() < 0.5 and x < size - 1:
            x += 1
        elif y < size - 1:
            y += 1
        else:
            x += 1
        key = "%d,%d" % (x, y)
        if key not in seen:
            seen.add(key)
            rows[y] = rows[y][:x] + "G" + rows[y][x + 1:]
    return rows


# --------------------------------------------------------------------------- python template


def _python_game(c, seed):
    grid = world_grid(seed, 14, c["features"]["density"])
    pal = c["palette_rgb"]
    theme_name = c["theme_name"]
    brgb = c["features"]["enemy_rgb"]
    stats = c["stats"]
    g_rows = []
    for row in grid:
        g_rows.append('    "%s",' % row)
    grid_body = "\n".join(g_rows)
    pal_lines = "\n".join("    (%d, %d, %d)," % p for p in pal)

    code = _PY.split("__PALETTE__")[0] + pal_lines + _PY.split("__PALETTE__")[1]
    code = code.split("__GRID__")[0] + grid_body + code.split("__GRID__")[1]
    code = (code.replace("__THEME__", theme_name)
                .replace("__ENEMY_RGB__", "(%d, %d, %d)" % brgb)
                .replace("__HP__", str(stats["hp"]))
                .replace("__AMMO__", str(stats["ammo"]))
                .replace("__TURNS__", str(stats["turns"]))
                .replace("__OBJECTIVE__", c["features"]["objective_text"])
                .replace("__VICTORY__", c["features"]["victory_text"]))
    return code, grid


_PY = """\
#!/usr/bin/env python3
# Nova-1 generated game - %(theme)s theme (offline template)
print("NOVA-1  ::  turns-based game  ::  arrow keys WASD, quit with Q")

import sys, os, time

TILE = {}
WALL = {"#"}; WATER = {"W"}; GEM = {"C"}; MONSTER = {"M"}; KEY = {"K"}; DOOR = {"D"}
START = "P"; GOAL = "G"

# palette (R, G, B) for ANSI true-color terminals
PALETTE = [
__PALETTE__
]
def rgb(rgb):
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return "\\x1b[38;2;%d;%d;%dm" % (r, g, b)

TILE_COLORS = {
    "#": PALETTE[0], "W": (36, 110, 180), "C": PALETTE[4], "M": __ENEMY_RGB__,
    "K": (240, 200, 90), "P": (120, 240, 120), "G": (80, 220, 80), ".": (40, 40, 46),
}

GRID = [
__GRID__
]

HEIGHT, WIDTH = len(GRID), len(GRID[0])

def render(px, py, hp, ammo, gems, keys):
    os.system("cls" if os.name == "nt" else "clear")
    print("\\x1b[0mNOVA-1  %s  HP:%s  ammo:%s  gems:%s  keys:%s\\n" % ("__THEME__", hp, ammo, gems, keys))
    print("\\x1b[0m__OBJECTIVE__\\n")
    for y in range(HEIGHT):
        line = ""
        for x in range(WIDTH):
            ch = GOAL if (x == px and y == py) else GRID[y][x]
            col = TILE_COLORS.get(ch, (40, 40, 46))
            line += rgb(col) + ch + "\\x1b[0m"
        print(line)
    print("\\n[WASD] move  [space] shoot  [Q] quit")

def find(ch):
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if GRID[y][x] == ch:
                return x, y
    return 1, 1

def move_to(x, y):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT and GRID[y][x] not in WALL and GRID[y][x] not in WATER:
        return x, y
    return None

def sim(key, px, py, monsters, hp, ammo, gems, keys):
    dx = dy = 0
    if key == "w": dy = -1
    elif key == "s": dy = 1
    elif key == "a": dx = -1
    elif key == "d": dx = 1
    if dx or dy:
        nxy = move_to(px + dx, py + dy)
        if nxy:
            px, py = nxy
            if GRID[py][px] in GEM:
                gems += 1
            elif GRID[py][px] in KEY:
                keys += 1
            elif GRID[py][px] in DOOR and keys:
                keys -= 1
    elif key == " " and ammo > 0:
        ammo -= 1
        monsters.sort(key=lambda m: abs(m[0]-px)+abs(m[1]-py))
        if monsters and abs(monsters[0][0]-px) + abs(monsters[0][1]-py) <= 1:
            monsters.pop(0)
    # monsters chase
    rem = []
    for mx, my in monsters:
        if abs(mx-px) + abs(my-py) <= 1:
            hp -= 1
            continue
        nxy = None
        for sx, sy in ((1,0),(-1,0),(0,1),(0,-1)):
            txy = move_to(mx+sx, my+sy)
            if txy and abs(txy[0]-px)+abs(txy[1]-py) < abs(mx-px)+abs(my-py):
                nxy = txy
                break
        rem.append(nxy or (mx, my))
    return px, py, rem, hp, ammo, gems, keys

p_start = find(START); px, py = p_start
gx, gy = find(GOAL)
monsters = [(x, y) for y in range(HEIGHT) for x in range(WIDTH) if GRID[y][x] in MONSTER]
hp, ammo, gems, keys = __HP__, __AMMO__, 0, 0
turns = 0

def getkey():
    if os.name == "nt":
        import msvcrt
        k = msvcrt.getwch()
        if k in "\\x00\\xe0":
            k = msvcrt.getwch()
            return {72:"w", 77:"d", 75:"a", 80:"s"}.get(ord(k), "")
        return k.lower()
    import tty, termios, sys as _s
    fd = _s.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = _s.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch.lower()

while True:
    render(px, py, hp, ammo, gems, keys)
    if hp <= 0:
        print("You were overwhelmed... GAME OVER")
        sys.exit(1)
    if px == gx and py == gy:
        print("__VICTORY__ (%d turns)." % turns)
        sys.exit(0)
    if turns > __TURNS__:
        print("Time ran out. GAME OVER")
        sys.exit(1)
    key = getkey()
    if key == "q":
        sys.exit(0)
    px, py, monsters, hp, ammo, gems, keys = sim(key, px, py, monsters, hp, ammo, gems, keys)
    turns += 1
"""

# --------------------------------------------------------------------------- roblox template


def _roblox(c, seed):
    grid = world_grid(seed, 16, c["features"]["density"])
    pal = c["palette_rgb"]
    brgb = c["features"]["enemy_rgb"]
    stats = c["stats"]
    g_rows = "\n".join(
        '        "%s",' % ("".join(ch if ch in "#WLCPMKDT" else "." for ch in row))
        for row in grid
    )
    pal_lines = "\n".join("        Color3.fromRGB(%d, %d, %d)," % p for p in pal)
    code = _LUA.split("__PALETTE__")[0] + pal_lines + _LUA.split("__PALETTE__")[1]
    code = code.split("__GRID__")[0] + g_rows + code.split("__GRID__")[1]
    code = (code.replace("__THEME__", c["theme_name"])
                .replace("__ENEMY_RGB_LUA__", "%d, %d, %d" % brgb)
                .replace("__OBJECTIVE_LUA__", c["features"]["objective_text"])
                .replace("__VICTORY_LUA__", c["features"]["victory_text"])
                .replace("__WAVES__", str(stats["waves"]))
                .replace("__WAVES_BASE__", str(stats["waves_base"])))
    return code, grid


_LUA = """\
-- Nova-1 generated by Kodr   (paste in ServerScriptService)
local Players = game:GetService("Players")

local PALETTE = {
__PALETTE__
}

local GRID = {
__GRID__
}

local HEIGHTS = {
    ["#"] = 1, ["W"] = 0.5, ["L"] = 0.35, ["C"] = 0.6, ["M"] = 0.9,
    ["K"] = 0.5, ["P"] = 0.2, ["D"] = 1.4, ["G"] = 1.3, ["."] = nil,
}

local function color(ch)
    if ch == "W" then return Color3.fromRGB(54, 120, 190) end
    if ch == "L" then return Color3.fromRGB(255, 90, 30) end
    if ch == "C" then return PALETTE[5] or PALETTE[2] end
    if ch == "M" then return Color3.fromRGB(190, 50, 50) end
    if ch == "P" then return Color3.fromRGB(120, 240, 120) end
    if ch == "G" then return Color3.fromRGB(70, 250, 90) end
    if ch == "D" then return PALETTE[3] or PALETTE[1] end
    if ch == "K" then return Color3.fromRGB(245, 200, 90) end
    return PALETTE[1]
end

local function buildWorld()
    local folder = Instance.new("Folder")
    folder.Name = "NovaWorld"
    folder.Parent = workspace
    for z, line in ipairs(GRID) do
        for x = 1, #line do
            local ch = line:sub(x, x)
            local h = HEIGHTS[ch]
            if h then
                local p = Instance.new("Part")
                p.Name = ch .. "_" .. x .. "_" .. z
                p.Size = Vector3.new(1, h, 1)
                p.Anchored = true
                p.Material = Enum.Material.SmoothPlastic
                p.Color = color(ch)
                p.Position = Vector3.new(x - #GRID[1] / 2, h / 2 + 0.6, z - #GRID / 2)
                p.TopSurface = Enum.SurfaceType.Smooth
                p.BottomSurface = Enum.SurfaceType.Smooth
                p.Parent = folder
            end
        end
    end
    return folder
end

local root = buildWorld()
print("Nova-1 :: __OBJECTIVE_LUA__")

-- Wave combat (open world = just spawn a few chasers)
local humans = {}
local monsters = {}
local waves = 0
local maxWaves = __WAVES__

local function pickSpawn(p)
    local ang = math.random() * math.pi * 2
    return p + Vector3.new(math.cos(ang) * 14, 9, math.sin(ang) * 14)
end

local function spawnWave(around)
    waves = waves + 1
    for i = 1, __WAVES_BASE__ + waves do
        local m = Instance.new("Part")
        m.Size = Vector3.new(1.4, 1.4, 1.4)
        m.Shape = Enum.PartType.Block
        m.Anchored = false
        m.Material = Enum.Material.Neon
        m.Color = Color3.fromRGB(__ENEMY_RGB_LUA__)
        m.Position = pickSpawn(around)
        m.CanCollide = true
        m.Parent = workspace
        local touch
        touch = m.Touched:Connect(function(other)
            local c = other.Parent
            local hum = c and c:FindFirstChildOfClass("Humanoid")
            if hum and not m:GetAttribute("hit") then
                m:SetAttribute("hit", true)
                hum:TakeDamage(8)
                task.delay(1.2, function() m:SetAttribute("hit", false) end)
            end
        end)
        task.spawn(function()
            while m and m.Parent and waves <= maxWaves do
                local hp = m:FindFirstChildOfClass("Humanoid")
                if hp and hp.Health <= 0 then
                    m:Destroy()
                    break
                end
                for _, plr in ipairs(Players:GetPlayers()) do
                    local char = plr.Character
                    if char and char:FindFirstChild("HumanoidRootPart") then
                        local hrp = char.HumanoidRootPart
                        local dir = (hrp.Position - m.Position).Unit * 8
                        m.AssemblyLinearVelocity = Vector3.new(dir.X, 0, dir.Z)
                    end
                end
                task.wait(0.35)
            end
            if m then m:Destroy() end
        end)
        table.insert(monsters, m)
    end
end

local function checkEnd()
    if waves >= maxWaves and #monsters == 0 then
        print("Nova-1 :: __VICTORY_LUA__")
    end
end

spawnWave(Vector3.new(0, 1, 0))

Players.PlayerAdded:Connect(function(plr)
    plr.CharacterAdded:Connect(function(char)
        local hum = char:WaitForChild("Humanoid")
        hum.MaxHealth = 100
        hum.Health = 100
        task.wait(8)
        if waves < maxWaves then
            local hrp = char:WaitForChild("HumanoidRootPart")
            spawnWave(hrp.Position)
        end
    end)
end)
"""

# --------------------------------------------------------------------------- unity / godot / unreal scaffolds


def _unity(c):
    grid = world_grid((hash(c["title"]) % 10**9), 12)
    pal = c["palette_rgb"]
    g_rows = "\n".join('        "%s",' % row for row in grid)
    pal_lines = "\n".join("        new Color32(%d, %d, %d, 255)," % p for p in pal)
    head, tail = _CS.split("__PALETTE__"), _CS.split("__PALETTE__")[1]
    code = head[0] + pal_lines + tail.split("__GRID__")[0] + g_rows + tail.split("__GRID__")[1]
    return code, grid


_CS = """\
using System.Collections;
using UnityEngine;

public class KodrWorldBuilder : MonoBehaviour
{
    static Color32[] Palette = new Color32[]
    {
__PALETTE__
    };

    static string[] Grid = new string[]
    {
__GRID__
    };

    void Start()
    {
        BuildWorld();
    }

    void BuildWorld()
    {
        for (int z = 0; z < Grid.Length; z++)
        {
            string row = Grid[z];
            for (int x = 0; x < row.Length; x++)
            {
                char ch = row[x];
                float h = Height(ch);
                if (h < 0.05f) continue;
                var box = GameObject.CreatePrimitive(PrimitiveType.Cube);
                box.name = "cell_" + ch;
                box.transform.position = new Vector3(x - row.Length / 2f, h / 2f, z - Grid.Length / 2f);
                box.transform.localScale = new Vector3(1f, h, 1f);
                box.GetComponent<Renderer>().material.color = Color(ch);
                box.AddComponent<BoxCollider>();
            }
        }
        var player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        player.name = "Player";
        player.transform.position = new Vector3(0, 1f, 0);
        player.AddComponent<CharacterController>();
        player.AddComponent<KodrPlayer>();
    }

    float Height(char ch)
    {
        if (ch == '#') return 1f;
        if (ch == 'W') return 0.5f;
        if (ch == 'D') return 1.5f;
        if (ch == 'C' || ch == 'K') return 0.6f;
        if (ch == 'G') return 1.3f;
        return 0f;
    }

    Color Color(char ch)
    {
        if (ch == 'W') return new Color(0.2f, 0.5f, 0.75f);
        if (ch == 'K') return new Color(0.96f, 0.78f, 0.35f);
        if (ch == 'G') return new Color(0.3f, 0.95f, 0.4f);
        if (ch == 'M') return new Color(0.8f, 0.2f, 0.2f);
        return Palette[Mathf.Abs(ch * 17) % Palette.Length];
    }
}
"""


def _godot(c):
    grid = world_grid((hash(c["title"]) % 10**9), 12)
    pal = c["palette_rgb"]
    g_rows = "\n".join('	"%s",' % row for row in grid)
    pal_lines = "\n".join("	Color(%d, %d, %d, 1.0)," % p for p in pal)
    head, tail = _GD.split("__PALETTE__"), _GD.split("__PALETTE__")[1]
    code = head[0] + pal_lines + tail.split("__GRID__")[0] + g_rows + tail.split("__GRID__")[1]
    return code, grid


_GD = """\
extends Node3D

# Nova-1 generated world builder — add this script to a Node3D node.
const PALETTE = [
__PALETTE__
]

const GRID = [
__GRID__
]

func _ready():
	_build_world()

func _height(ch: String) -> float:
	match ch:
		"#": return 1.0
		"W": return 0.5
		"D": return 1.5
		"C", "K": return 0.6
		"G": return 1.3
		_: return 0.0

func _color(ch: String) -> Color:
	match ch:
		"W": return Color(0.2, 0.5, 0.75)
		"K": return Color(0.96, 0.78, 0.35)
		"G": return Color(0.3, 0.95, 0.4)
		"M": return Color(0.8, 0.2, 0.2)
		_: return PALETTE[abs(ch.hash()) % PALETTE.size()]

func _build_world():
	var mat = StandardMaterial3D.new()
	for z in range(GRID.size()):
		for x in range(GRID[z].length()):
			var ch = GRID[z][x]
			var h = _height(ch)
			if h < 0.05: continue
			var box = CSGBox3D.new()
			box.size = Vector3(1, h, 1)
			box.position = Vector3(x - GRID[z].length() / 2.0, h / 2.0, z - GRID.size() / 2.0)
			var m = mat.duplicate()
			m.albedo_color = _color(ch)
			box.material = m
			add_child(box)
	var player = CSGCylinder3D.new()
	player.position = Vector3(0, 1.5, 0)
	add_child(player)
	print("Nova-1 :: world ready (%d cells)" % GRID.size() * GRID[0].length())
"""


def _unreal(c):
    grid = world_grid((hash(c["title"]) % 10**9), 10)
    pal = c["palette_rgb"]
    g_rows = "\n".join('        TEXT("%s"),' % row for row in grid)
    pal_lines = "\n".join(
        "        FLinearColor(%.3f, %.3f, %.3f, 1.0f)," % (r / 255, g / 255, b / 255) for r, g, b in pal
    )
    code = _CPP.split("__PALETTE__")[0] + pal_lines + _CPP.split("__PALETTE__")[1]
    code = code.split("__GRID__")[0] + g_rows + code.split("__GRID__")[1]
    return code, grid


_CPP = """\
// Nova-1 generated world builder — Unreal C++ (header + implementation below)
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "KodrWorldActor.generated.h"

UCLASS(BlueprintType)
class AKodrWorldActor : public AActor
{
    GENERATED_BODY()
public:
    AKodrWorldActor();
    virtual void OnConstruction(const FTransform& Transform) override;

    UPROPERTY(EditAnywhere, Category = "Kodr")
    UMaterialInterface* CellMaterial = nullptr;
};

// ---- KodrWorldActor.cpp ------------------------------------------------------------
#include "KodrWorldActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

static const TArray<FLinearColor> KodrPalette = TArray<FLinearColor>
{
__PALETTE__
};

static const TArray<FString> KodrGrid = TArray<FString>
{
__GRID__
};

AKodrWorldActor::AKodrWorldActor()
{
    PrimaryActorTick.bCanEverTick = false;
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    auto* ISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("World"));
    ISM->SetupAttachment(RootComponent);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded()) { ISM->SetStaticMesh(Cube.Object); }
    else { UE_LOG(LogTemp, Error, TEXT("Kodr: cube mesh missing")); }
    ISM->SetMaterial(0, CellMaterial);
}

void AKodrWorldActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    auto* ISM = FindComponentByClass<UInstancedStaticMeshComponent>();
    if (!ISM) return;
    ISM->ClearInstances();
    for (int z = 0; z < KodrGrid.Num(); ++z)
    {
        const FString& Row = KodrGrid[z];
        for (int x = 0; x < Row.Len(); ++x)
        {
            float H = 0.0f;
            switch (Row[x])
            {
                case TEXT('#')[0]: H = 1.0f; break;
                case TEXT('W')[0]: H = 0.5f; break;
                case TEXT('D')[0]: H = 1.5f; break;
                case TEXT('G')[0]: H = 1.3f; break;
                default: continue;
            }
            FTransform T(FVector(float(x - Row.Len() / 2), float(z - KodrGrid.Num() / 2), H / 2.0f));
            T.SetScale3D(FVector(1, 1, H));
            ISM->AddInstance(T);
        }
    }
    UE_LOG(LogTemp, Log, TEXT("Nova-1 :: %d cells instanced"), ISM->GetInstanceCount());
}
"""


# --------------------------------------------------------------------------- public API


def compose(prompt, engine="python", seed=None):
    """Turn a prompt into generated game code for the requested engine."""
    engine = engine.lower()
    if engine not in ENGINES:
        engine = "python"
    c = concept(prompt)
    if seed is None:
        seed = int(hashlib.sha256(("nova1_" + (prompt or "")).encode()).hexdigest()[:10], 16)
    if engine == "python":
        code, grid = _python_game(c, seed)
        files = {"nova_game.py": code}
    elif engine == "roblox":
        code, grid = _roblox(c, seed)
        files = {"ServerScript_NovaGame.lua": code, "_README.txt": _ROBLOX_NOTE}
    elif engine == "unity":
        code, grid = _unity(c)
        files = {"KodrWorldBuilder.cs": code, "_README.txt": _UNITY_NOTE}
    elif engine == "godot":
        code, grid = _godot(c)
        files = {"kodr_world.gd": code, "_README.txt": _GODOT_NOTE}
    else:
        code, grid = _unreal(c)
        files = {"KodrWorldActor.h": _UNREAL_HDR, "KodrWorldActor.cpp": code, "_README.txt": _UNREAL_NOTE}
    ascii_art = "\n".join("  " + "".join(symbol(ch) for ch in row[:18]) for row in grid[:11])
    r = {
        "engine": engine,
        "engine_label": ENGINES[engine]["label"],
        "arch": ENGINES[engine]["complete"] and "complete" or "scaffold",
        "theme": c["theme_name"],
        "palette_hex": c["palette_hex"],
        "archetype": c["archetype"],
        "features": c["features"],
        "title": c["title"],
        "files": files,
        "main_file": next(iter(files)),
        "code": code,
        "preview_ascii": ascii_art,
        "seed": seed,
    }
    if engine == "roblox":
        r["roblox_instructions"] = _ROBLOX_NOTE
    return r


def symbol(ch):
    return {"#": "\u2588", "W": "\u2248", "C": "$", "M": "M", "K": "k",
            "P": "@", "D": "D", "G": "!"}.get(ch, ".")


def save(r, outdir=None):
    outdir = outdir or tempfile.mkdtemp(prefix="nova1_")
    for name, content in r["files"].items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
    r["outdir"] = outdir
    return r


_ROBLOX_NOTE = """\
HOW TO RUN (Roblox Studio)
1. Create a new place (Baseplate template).
2. Open ServerScriptService, insert a new Script named NovaGame.
3. Paste the contents of ServerScript_NovaGame.lua into it.
4. Play. A world builds in ~1s and enemy waves spawn near your character.
Demo players: your default R15/R6 character moves with WASD / arrow keys.
"""
_UNITY_NOTE = """\
HOW TO RUN (Unity)
1. New 3D project. Create an empty GameObject in the scene.
2. Add a new C# script called KodrWorldBuilder and paste the contents.
3. (Optional) GameObject > Player movement: the script expects a 'Player'
   capsule with a CharacterController named KodrPlayer — or add your own.
4. Press Play. Cubes are generated from the Nova-1 world grid.
"""
_GODOT_NOTE = """\
HOW TO RUN (Godot)
1. New 3D scene, add a root Node3D named World.
2. Attach a new script kodr_world.gd.
3. The builder generates CSGBox3D cells from the Nova-1 grid.
4. Play the scene (CSG needs a CSGCombiner3D parent inside a CSGShape3D
   hierarchy if you want CSG rendering on export — for a quick look just run).
"""
_UNREAL_NOTE = """\
HOW TO RUN (Unreal Engine)
1. Add these two files to your Game module (or to a new Project plugin module).
2. Add `Modules = { "Core", "CoreUObject", "Engine" }` to your Build.cs.
3. Compile, then drag an AKodrWorldActor into your level.
4. The world is built with an InstancedStaticMesh of cubes.
"""
_UNREAL_HDR = _CPP.split("\n\n// ----")[0]