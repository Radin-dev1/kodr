"use strict";
(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];

  /* ---------------------------------- palette / theme knowledge (mirrors engine) */
  const PALETTES = {
    volcanic: { name: "Volcanic", colors: [[40, 26, 24], [60, 34, 22], [160, 44, 24], [220, 90, 30], [255, 150, 60], [200, 40, 90]] },
    aquatic: { name: "Aquatic", colors: [[16, 40, 80], [24, 70, 120], [40, 120, 170], [90, 190, 220], [200, 230, 245], [30, 90, 150]] },
    forest: { name: "Forest", colors: [[20, 45, 22], [34, 88, 40], [70, 150, 60], [120, 180, 80], [200, 180, 110], [60, 100, 40]] },
    desert: { name: "Desert", colors: [[150, 110, 60], [205, 170, 110], [235, 205, 150], [245, 225, 180], [160, 90, 60], [180, 140, 90]] },
    neon: { name: "Neon City", colors: [[20, 18, 40], [60, 20, 90], [120, 60, 200], [40, 190, 240], [250, 90, 220], [120, 240, 160]] },
    arctic: { name: "Arctic", colors: [[235, 245, 255], [200, 220, 255], [150, 190, 240], [110, 160, 215], [220, 235, 250], [170, 205, 240]] },
    gold: { name: "Ancient Gold", colors: [[40, 30, 16], [90, 66, 26], [170, 130, 50], [240, 200, 90], [255, 235, 160], [120, 90, 40]] },
  };
  const THEME_WORDS = {
    volcanic: ["lava", "volcano", "fire", "arena", "magma", "hell", "ember"],
    aquatic: ["water", "ocean", "underwater", "fish", "dive", "island", "beach"],
    forest: ["forest", "jungle", "wood", "tree", "nature", "green", "moss"],
    desert: ["desert", "sand", "dune", "dust", "wild west", "oasis"],
    neon: ["neon", "cyber", "city", "future", "sci-fi", "night", "synthwave"],
    arctic: ["snow", "ice", "arctic", "winter", "frozen", "polar", "cold"],
    gold: ["gold", "treasure", "pyramid", "temple", "ancient", "ruin", "pharaoh"],
  };
  const ENEMIES = {
    slime: ["slime", "blob", "goo", "mold"],
    zombie: ["zombie", "undead", "horde", "crawler"],
    drone: ["drone", "robot", "turret", "machin", "droid"],
    skeleton: ["skeleton", "bone", "soldier", "guard", "warrior"],
    kraken: ["kraken", "tentacle", "octop", "seamonster"],
    shade: ["ghost", "spirit", "shadow", "wraith", "shade"],
  };
  const ENEMY_RGB = { slime: [120, 220, 90], zombie: [150, 170, 60], drone: [210, 60, 210], skeleton: [225, 220, 205], kraken: [60, 120, 190], shade: [155, 120, 190] };
  const ENEMY_PLURAL = { slime: "slimes", zombie: "zombies", drone: "drones", skeleton: "skeletons", kraken: "krakens", shade: "shades" };
  const HARD = ["hard", "brutal", "swarm", "horde", "nightmare", "endless", "dense", "many", "intense", "insane", "deadly", "dangerous", "invasion"];
  const EASY = ["easy", "chill", "calm", "few", "light", "casual", "cozy", "gentle", "peaceful", "relaxing", "beginner"];
  const DIFF_STATS = { easy: { hp: 160, ammo: 12, turns: 320, waves: 3, wavesBase: 1 }, normal: { hp: 100, ammo: 6, turns: 240, waves: 4, wavesBase: 2 }, hard: { hp: 70, ammo: 4, turns: 170, waves: 6, wavesBase: 3 } };

  /* ---------------------------------- utils */
  const stableInt = (s) => {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h;
  };
  const mulberry = (a) => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    return () => {
      let t = (a = Math.imul(a ^ (a >>> 15), 1 | a)) ^ ((a ^ (a >>> 7)) ^ (a ^ (a >>> 15)));
      return ((t ^ (t >>> 7)) >>> 0) / 4294967296;
    };
  };
  const detectTheme = (t) => {
    const low = (t || "").toLowerCase();
    let best = "volcanic", bestScore = 0;
    for (const k in THEME_WORDS) {
      const s = THEME_WORDS[k].filter((w) => low.includes(w)).length;
      if (s > bestScore) { best = k; bestScore = s; }
    }
    return best;
  };
  const features = (t) => {
    const low = (t || "").toLowerCase();
    let enemy = "drone";
    for (const k in ENEMIES) { if (ENEMIES[k].some((w) => low.includes(w))) { enemy = k; break; } }
    const hard = HARD.filter((w) => low.includes(w)).length;
    const easy = EASY.filter((w) => low.includes(w)).length;
    const difficulty = hard > easy ? "hard" : easy > hard ? "easy" : "normal";
    const density = Math.max(0.18, Math.min(0.62, 0.36 + 0.12 * hard - 0.10 * easy));
    let objective = "reach";
    if (["surviv", "wave", "hold", "defend"].some((w) => low.includes(w))) objective = "survive";
    else if (["collect", "loot", "gem", "treasure", "crystal", "coin"].some((w) => low.includes(w))) objective = "collect";
    const objText = {
      survive: `Hold out against the ${ENEMY_PLURAL[enemy]} until relief arrives.`,
      collect: "Gather every shard and escape through the gate.",
      reach: `Reach the goal beacon alive while the ${ENEMY_PLURAL[enemy]} hunt you.`,
    }[objective];
    const vicText = { survive: "You survived the onslaught. Victory!", collect: "All shards gathered. Victory!", reach: "Beacon reached. Victory!" }[objective];
    return { enemy, enemyName: enemy[0].toUpperCase() + enemy.slice(1), enemyRgb: ENEMY_RGB[enemy], difficulty, density, objective, objectiveText: objText, victoryText: vicText, stats: DIFF_STATS[difficulty] };
  };
  const hex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, v | 0)).toString(16).padStart(2, "0")).join("");
  const grid = (seed, size, density) => {
    let rng = mulberry(seed);
    for (let i = 0; i < seed % 97; i++) rng();
    const rows = [];
    for (let y = 0; y < size; y++) {
      let row = "";
      for (let x = 0; x < size; x++) {
        const p = rng();
        row += p < density * 1.15 ? "#" : p < density * 1.15 + 0.05 ? "W" :
          p < density * 1.15 + 0.10 ? "C" : p < density * 1.15 + 0.14 ? "M" :
            p < density * 1.15 + 0.17 ? "K" : p < density * 1.15 + 0.20 ? "D" : ".";
      }
      rows.push(row);
    }
    let px = 0, py = 0;
    rows[0] = "P" + rows[0].slice(1);
    const seen = new Set(["0,0"]);
    let moved = true;
    let guard = 0;
    while (moved && guard++ < size * 3) {
      moved = false;
      const dir = mulberry(seed * 7 + px + py * 13)() < 0.5 && px < size - 1 ? "x" : py < size - 1 ? "y" : "x";
      const nx = dir === "x" ? px + 1 : px, ny = dir === "y" ? py + 1 : py;
      if (nx < size && ny < size && !seen.has(nx + "," + ny)) {
        px = nx; py = ny; seen.add(px + "," + py);
        rows[py] = rows[py].slice(0, px) + "G" + rows[py].slice(px + 1);
        moved = true;
      }
      if (px === size - 1 && py === size - 1) break;
    }
    return rows;
  };

  /* ---------------------------------- state */
  let mode = "demo";            // 'demo' | 'server'
  const S = {
    demoUsers: JSON.parse(localStorage.getItem("kodr_demo_users") || "{}"),
    session: localStorage.getItem("kodr_session"),   // demo: username
    user: null,
  };

  const keysByModel = (user) => { const ks = (user && user.keys) || {}; return ks; };

  /* reusable tiny demo user model */
  const demoLogin = (ident, pw) => {
    const u = S.demoUsers[ident] || Object.values(S.demoUsers).find((x) => x.email === ident.toLowerCase());
    if (!u || u.pw !== hash(pw)) return null;
    S.session = u.username; localStorage.setItem("kodr_session", u.username);
    return u;
  };
  const demoSignup = (username, email, pw) => {
    if (S.demoUsers[username] || Object.values(S.demoUsers).some((x) => x.email === email.toLowerCase())) return null;
    const usr = { username, email: email.toLowerCase(), pw: hash(pw), keys: {} };
    for (const m of ["nova1", "rex3d", "prism1"]) usr.keys[m] = { id: uid(), key: newKey(m), masked: "", revoked: 0, calls: 0, bytes: 0, lastUsed: null };
    usr.keys.nova1.masked = mask(usr.keys.nova1.key);
    usr.keys.rex3d.masked = mask(usr.keys.rex3d.key);
    usr.keys.prism1.masked = mask(usr.keys.prism1.key);
    S.demoUsers[username] = usr;
    localStorage.setItem("kodr_demo_users", JSON.stringify(S.demoUsers));
    S.session = username;
    return usr;
  };
  const newKey = (m) => m + "_" + randHex(16);
  const mask = (k) => k.slice(0, 14) + "..." + k.slice(-4);
  const uid = () => randHex(6);
  const randHex = (n) => { const a = new Uint8Array(n); crypto.getRandomValues(a); return [...a].map((b) => b.toString(16).padStart(2, "0")).join(""); };
  const hash = async (s) => {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  };
  let hasher = (s) => { let h = 7; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h.toString(); };
  // async-free demo hashing (crypto.subtle overkill for a demo store)
  hash = hasher;

  /* ---------------------------------- server client */
  const server = {
    async api(path, opts = {}) {
      try {
        const r = await fetch(path, { credentials: "include", ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
        const j = await r.json().catch(() => ({}));
        return { ok: r.ok, status: r.status, j };
      } catch (e) { return { ok: false, status: 0, j: {} }; }
    },
    me: () => server.api("/api/auth/me", { method: "GET" }),
    login: (u, p) => server.api("/api/auth/login", { method: "POST", body: JSON.stringify({ username: u, password: p }) }),
    signup: (u, e, p) => server.api("/api/auth/signup", { method: "POST", body: JSON.stringify({ username: u, email: e, password: p }) }),
    logout: () => server.api("/api/auth/logout", { method: "POST", body: "{}" }),
    createKey: (m) => server.api("/api/keys", { method: "POST", body: JSON.stringify({ model: m }) }),
    revokeKey: (id) => server.api("/api/keys/revoke", { method: "POST", body: JSON.stringify({ id }) }),
    regenerateKey: (id) => server.api("/api/keys/regenerate", { method: "POST", body: JSON.stringify({ id }) }),
    nova: (prompt, engine, key) => server.api("/api/v1/nova1/generate", { method: "POST", body: JSON.stringify({ prompt, engine }), headers: { Authorization: "Bearer " + key } }),
    rex: (prompt, size, key) => server.api("/api/v1/rex3d/generate", { method: "POST", body: JSON.stringify({ prompt, size }), headers: { Authorization: "Bearer " + key } }),
    prism: (prompt, style, key) => server.api("/api/v1/prism1/generate", { method: "POST", body: JSON.stringify({ prompt, style }), headers: { Authorization: "Bearer " + key } }),
  };

  /* ---------------------------------- auth UI */
  const authModal = $("#authModal"), accountModal = $("#accountModal");
  let authForm = "login";
  const setAuthUI = () => {
    const logged = !!S.user;
    $("#navSignin").hidden = logged;
    $("#navAccount").hidden = !logged;
    $("#navAccount").textContent = logged ? "Account" : "Get API key";
    $("#navSignout").hidden = !logged;
  };

  const openAuth = (tab) => {
    authForm = tab || "login";
    renderAuthTabs();
    authModal.hidden = false;
    if (mode === "demo") $("#authDemoNote").hidden = false;
    else $("#authDemoNote").hidden = true;
  };
  const closeModals = () => { authModal.hidden = true; accountModal.hidden = true; };
  const renderAuthTabs = () => {
    $$("#authTabs .auth-tab").forEach((b) => b.classList.toggle("active", b.dataset.aform === authForm));
    $("#fieldEmail").hidden = authForm !== "signup";
    $("#fieldUsername").querySelector("span").textContent = authForm === "signup" ? "Username" : "Username or email";
    $("#authMsg").textContent = ""; $("#authMsg").className = "auth-msg";
  };

  const toast = (msg) => { const t = $("#toast"); t.textContent = msg; t.hidden = false; setTimeout(() => { t.hidden = true; }, 3200); };

  const onAuthSubmit = async (e) => {
    e.preventDefault();
    const username = $("#authUsername").value.trim();
    const email = $("#authEmail").value.trim();
    const pw = $("#authPassword").value;
    const msg = $("#authMsg");
    if (authForm === "signup" && (username.length < 3 || !email.includes("@") || pw.length < 8)) {
      msg.textContent = "Username ≥ 3 chars, valid email, password ≥ 8 chars."; return;
    }
    if (mode === "server") {
      const { ok, j } = authForm === "signup" ? await server.signup(username, email, pw) : await server.login(username, pw);
      if (!ok) { msg.textContent = j.error || "request failed"; return; }
      await loadMe();
      closeModals();
      toast(authForm === "signup" ? "Account created — keys granted for all three models." : "Signed in.");
      openAccount();
      return;
    }
    const u = authForm === "signup" ? demoSignup(username, email, pw) : demoLogin(username, pw);
    if (!u) { msg.textContent = authForm === "signup" ? "Username or email already taken." : "Invalid credentials."; return; }
    S.user = u; setAuthUI(); closeModals();
    toast(authForm === "signup" ? "Demo account created — keys for all three models generated in your browser." : "Signed in (demo mode).");
    openAccount();
  };

  async function loadMe() {
    const { ok, j } = await server.me();
    if (ok) { S.user = { username: j.user, email: j.email, keys: j.keys, usage: j.usage, daily: j.daily }; }
    else S.user = null;
    setAuthUI();
  }

  const openAccount = () => {
    if (!S.user) { openAuth("login"); return; }
    renderAccount();
    accountModal.hidden = false;
  };

  const accountUser = () => (mode === "server" ? S.user : S.demoUsers[S.session] && { username: S.demoUsers[S.session].username, email: S.demoUsers[S.session].email, keys: S.demoUsers[S.session].keys });

  function renderAccount() {
    const u = accountUser();
    if (!u) return;
    $("#acctUser").textContent = u.username;
    const ks = u.keys || {};
    const agg = { nova1: ks.nova1, rex3d: ks.rex3d, prism1: ks.prism1 };
    const wrap = $("#usages");
    wrap.innerHTML = "";
    for (const m of ["nova1", "rex3d", "prism1"]) {
      const k = agg[m];
      const calls = k ? k.calls : 0, bytes = k ? k.bytes : 0;
      const div = document.createElement("div");
      div.className = "usage-cell";
      div.innerHTML = `<span class="lab">${m}</span><div class="val">${calls} calls</div><div class="bar"><i style="width:${Math.min(100, calls > 0 ? calls : 0)}%"></i></div>`;
      wrap.appendChild(div);
    }
    const dl = $("#dailyChart");
    dl.innerHTML = "";
    if (mode === "demo") {
      const day = new Date().toISOString().slice(0, 10);
      for (const m of ["nova1", "rex3d", "prism1"]) {
        const r = document.createElement("div");
        r.className = "daily-row"; r.innerHTML = `<b>${day}</b> · ${m} · ${agg[m] ? agg[m].calls : 0} calls`;
        dl.appendChild(r);
      }
    } else {
      (u.daily || []).slice(-12).forEach((d) => {
        const r = document.createElement("div");
        r.className = "daily-row"; r.innerHTML = `<b>${d.day}</b> · ${d.model} · ${d.calls} calls`;
        dl.appendChild(r);
      });
    }
    const kl = $("#keysList");
    kl.innerHTML = "";
    for (const m of ["nova1", "rex3d", "prism1"]) {
      const mk = ks[m];
      if (mk) {
        const row = document.createElement("div");
        row.className = "key-row";
        row.innerHTML = `
          <span class="key-model ${m === "nova1" ? "nova" : m === "rex3d" ? "rex" : "prism"}">${m}</span>
          <span class="key-value">${mk.revoked ? "revoked" : mk.masked || mask(mk.key)}</span>
          <span class="key-stat">${mk.calls} calls · ${mk.bytes} B</span>
          <span class="key-actions">
            ${mk.revoked ? `<span class="revoked">revoked</span></span>` : `
            <button class="btn btn-ghost btn-sm" data-rotate="${m}">Regenerate</button>
            <button class="btn btn-ghost btn-sm" data-revoke="${m}">Revoke</button></span>`}`;
        kl.appendChild(row);
      }
      const cbtn = document.createElement("button");
      cbtn.className = "btn btn-ghost btn-sm"; cbtn.textContent = "+ New " + m + " key";
      cbtn.onclick = () => createKeyFlow(m);
      kl.appendChild(cbtn);
    }
  }

  async function createKeyFlow(m) {
    if (mode === "server") {
      const { ok, j } = await server.createKey(m);
      if (!ok) { toast(j.error || "failed"); return; }
      toast("Key created: " + j.key);
      const t = $("#toast");
      setTimeout(() => { t.textContent = "Copy your new key — shown only once: " + j.key; }, 40);
      await loadMe(); renderAccount();
      return;
    }
    const u = S.demoUsers[S.session];
    const k = { id: uid(), key: newKey(m), masked: "", revoked: 0, calls: 0, bytes: 0, lastUsed: null };
    k.masked = mask(k.key);
    u.keys[m] = k;
    persistDemo();
    toast("New key: " + k.key);
    renderAccount();
  }

  const persistDemo = () => localStorage.setItem("kodr_demo_users", JSON.stringify(S.demoUsers));

  const onKeyAction = async (m, action) => {
    if (mode === "server") {
      const u = await (async () => { const { j } = await server.me(); return j; })();
      const kid = (u.keys || []).find((k) => k.model === m);
      if (!kid) return;
      if (action === "revoke") await server.revokeKey(kid.id);
      else { const { ok, j } = await server.regenerateKey(kid.id); if (ok) { toast("Regenerated: " + j.key); } }
      await loadMe(); renderAccount(); return;
    }
    const u = S.demoUsers[S.session];
    if (!u) return;
    if (action === "revoke") { u.keys[m].revoked = 1; }
    else { u.keys[m] = { id: uid(), key: newKey(m), masked: mask(newKey(m)), revoked: 0, calls: 0, bytes: 0, lastUsed: null }; toast("New key: " + u.keys[m].key); }
    persistDemo(); renderAccount();
  };

  /* ---------------------------------- theme */
  const applyTheme = (t) => { document.documentElement.dataset.theme = t; localStorage.setItem("kodr_theme", t); };
  $("#themeToggle").onclick = () => applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");

  /* ---------------------------------- playground wiring */
  const tabs = $$("#playgroundTabs .tab");
  const tabByName = (n) => tabs.find((t) => t.dataset.tab === n);
  const switchTab = (name) => {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    ["nova1", "rex3d", "prism1"].forEach((n) => { $("#panel-" + n).hidden = n !== name; });
  };
  tabs.forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));
  $$("[data-tab]").forEach((el) => { if (el.closest(".section, .model-card")) { const n = el.dataset.tab; if (n && ["nova1", "rex3d", "prism1"].includes(n)) el.addEventListener("click", () => switchTab(n)); } });
  $("#rexSize").oninput = () => { $("#rexSizeLabel").textContent = $("#rexSize").value + "×" + $("#rexSize").value; };

  const setStatus = (id, txt, cls) => { const el = $(id); el.textContent = txt; el.className = "pt-status slim " + (cls || ""); };

  /* ---------------------------------- Nova-1 ---------------------------------- */
  const PY = `#!/usr/bin/env python3
import os, sys

TILE = {}
WALL = {"#"}; WATER = {"W"}; GEM = {"C"}; MONSTER = {"M"}; KEY = {"K"}; DOOR = {"D"}
START = "P"; GOAL = "G"

PALETTE = [
__PALETTE__
]
def rgb(c):
    r, g, b = (max(0, min(255, int(v))) for v in c)
    return "\\x1b[38;2;%d;%d;%dm" % (r, g, b)

TILE_COLORS = {
    "#": PALETTE[0], "W": (36, 110, 180), "C": PALETTE[4], "M": __ENEMY_RGB__,
    "K": (240, 200, 90), "P": (120, 240, 120), "G": (80, 220, 80), ".": (40, 40, 46),
}

GRID = [
__GRID__
]
H, W = len(GRID), len(GRID[0])

def render(px, py, hp, ammo, gems, keys):
    os.system("cls" if os.name == "nt" else "clear")
    print("\\x1b[0mNOVA-1  __THEME__  HP:%s  ammo:%s  gems:%s  keys:%s\\n" % (hp, ammo, gems, keys))
    print("\\x1b[0m__OBJECTIVE__\\n")
    for y in range(H):
        line = ""
        for x in range(W):
            ch = GRID[y][x] if not (x == px and y == py) else GOAL
            line += rgb(TILE_COLORS.get(ch, (40, 40, 46))) + ch + "\\x1b[0m"
        print(line)
    print("\\n[WASD] move  [space] shoot  [Q] quit")

def find(ch):
    for y in range(H):
        for x in range(W):
            if GRID[y][x] == ch: return x, y
    return 1, 1

def move_to(x, y):
    if 0 <= x < W and 0 <= y < H and GRID[y][x] not in WALL | WATER:
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
            if GRID[py][px] in GEM: gems += 1
            elif GRID[py][px] in KEY: keys += 1
            elif GRID[py][px] in DOOR and keys: keys -= 1
    elif key == " " and ammo > 0:
        ammo -= 1
        monsters.sort(key=lambda m: abs(m[0]-px)+abs(m[1]-py))
        if monsters and abs(monsters[0][0]-px)+abs(monsters[0][1]-py) <= 1:
            monsters.pop(0)
    rem = []
    for mx, my in monsters:
        if abs(mx-px)+abs(my-py) <= 1:
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

def getkey():
    if os.name == "nt":
        import msvcrt
        k = msvcrt.getwch()
        if k in "\\x00\\xe0":
            k = msvcrt.getwch()
            return {72:"w", 77:"d", 75:"a", 80:"s"}.get(ord(k), "")
        return k.lower()
    import tty, termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch.lower()

px, py = find(START)
gx, gy = find(GOAL)
monsters = [(x, y) for y in range(H) for x in range(W) if GRID[y][x] in MONSTER]
hp, ammo, gems, keys = __HP__, __AMMO__, 0, 0
turns = 0

while True:
    render(px, py, hp, ammo, gems, keys)
    if hp <= 0:
        print("\\x1b[0mYou were overwhelmed... GAME OVER")
        sys.exit(1)
    if px == gx and py == gy:
        print("\\x1b[0m__VICTORY__ (%d turns)." % turns)
        sys.exit(0)
    if turns > __TURNS__:
        print("\\x1b[0mTime ran out. GAME OVER")
        sys.exit(1)
    key = getkey()
    if key == "q":
        sys.exit(0)
    px, py, monsters, hp, ammo, gems, keys = sim(key, px, py, monsters, hp, ammo, gems, keys)
    turns += 1
`;

  const fillPy = (o) => PY
    .replace("__PALETTE__", o.pal.map((c) => "    (" + c.join(", ") + "),").join("\n"))
    .replace("__GRID__", o.grid.map((r) => '    "' + r + '",').join("\n"))
    .replace("__THEME__", o.themeRow)
    .replace("__ENEMY_RGB__", "(" + o.f.enemyRgb.join(", ") + ")")
    .replace("__HP__", o.f.stats.hp)
    .replace("__AMMO__", o.f.stats.ammo)
    .replace("__TURNS__", o.f.stats.turns)
    .replace("__OBJECTIVE__", o.f.objectiveText)
    .replace("__VICTORY__", o.f.victoryText);

  const LUA = `-- Nova-1 generated by Kodr (ServerScriptService)
local Players = game:GetService("Players")
local PALETTE = {
__PALETTE__
}
local GRID = {
__GRID__
}
local HEIGHTS = { ["#"]=1, ["W"]=0.5, ["C"]=0.6, ["M"]=0.9, ["K"]=0.5, ["P"]=0.2, ["D"]=1.4, ["G"]=1.3 }
local function color(ch)
    if ch=="W" then return Color3.fromRGB(54,120,190) end
    if ch=="C" then return PALETTE[5] or PALETTE[3] end
    if ch=="M" then return Color3.fromRGB(__ENEMY_RGB_LUA__) end
    if ch=="P" then return Color3.fromRGB(120,240,120) end
    if ch=="G" then return Color3.fromRGB(70,250,90) end
    if ch=="D" then return PALETTE[4] or PALETTE[1] end
    if ch=="K" then return Color3.fromRGB(245,200,90) end
    return PALETTE[1]
end
local function buildWorld()
    local folder = Instance.new("Folder"); folder.Name = "NovaWorld"; folder.Parent = workspace
    for z, line in ipairs(GRID) do
        for x = 1, #line do
            local ch = line:sub(x, x)
            local h = HEIGHTS[ch]
            if h then
                local p = Instance.new("Part")
                p.Size = Vector3.new(1, h, 1); p.Anchored = true
                p.Material = Enum.Material.SmoothPlastic
                p.Color = color(ch)
                p.Position = Vector3.new(x - #GRID[1]/2, h/2 + 0.6, z - #GRID/2)
                p.Parent = folder
            end
        end
    end
    return folder
end
buildWorld()
print("Nova-1 :: __OBJECTIVE_LUA__")

local players, monsters = {}, {}
local waves, maxWaves = 0, __WAVES__
local function pickSpawn(p)
    local a = math.random()*math.pi*2
    return p + Vector3.new(math.cos(a)*14, 9, math.sin(a)*14)
end
local function spawnWave(around)
    waves = waves + 1
    for i = 1, __WAVES_BASE__ + waves do
        local m = Instance.new("Part")
        m.Size = Vector3.new(1.4, 1.4, 1.4); m.Anchored = false
        m.Material = Enum.Material.Neon; m.Color = Color3.fromRGB(__ENEMY_RGB_LUA__)
        m.Position = pickSpawn(around); m.Parent = workspace
        m.Touched:Connect(function(other)
            local hum = other.Parent and other.Parent:FindFirstChildOfClass("Humanoid")
            if hum and not m:GetAttribute("hit") then
                m:SetAttribute("hit", true); hum:TakeDamage(8)
                task.delay(1.2, function() m:SetAttribute("hit", false) end)
            end
        end)
        task.spawn(function()
            local t = 0
            while m.Parent and waves <= maxWaves and t < 120 do
                t = t + 1
                for _, plr in ipairs(Players:GetPlayers()) do
                    local hrp = plr.Character and plr.Character:FindFirstChild("HumanoidRootPart")
                    if hrp then
                        local dir = (hrp.Position - m.Position)
                        dir = Vector3.new(dir.X, 0, dir.Z).Unit * 8
                        m.AssemblyLinearVelocity = dir
                    end
                end
                task.wait(0.35)
            end
            m:Destroy()
        end)
        table.insert(monsters, m)
    end
end
spawnWave(Vector3.new(0, 1, 0))
Players.PlayerAdded:Connect(function(plr)
    plr.CharacterAdded:Connect(function(char)
        local hum = char:WaitForChild("Humanoid"); hum.MaxHealth = 160; hum.Health = 160
        task.wait(8)
        if waves < maxWaves then
            local hrp = char:WaitForChild("HumanoidRootPart")
            spawnWave(hrp.Position)
        end
    end)
end)
`;

  const fillLua = (o) => LUA
    .replace("__PALETTE__", o.pal.map((c) => "    Color3.fromRGB(" + c.join(", ") + "),").join("\n"))
    .replace("__GRID__", o.grid.map((r) => '        "' + r + '",').join("\n"))
    .replace("__ENEMY_RGB_LUA__", o.f.enemyRgb.join(", "))
    .replace("__OBJECTIVE_LUA__", o.f.objectiveText)
    .replace("__WAVES__", o.f.stats.waves)
    .replace("__WAVES_BASE__", o.f.stats.wavesBase);

  const CS = `using System.Collections;\nusing UnityEngine;\n\npublic class KodrWorldBuilder : MonoBehaviour\n{\n    static Color32[] Palette = new Color32[]\n    {\n__PALETTE__\n    };\n    static string[] Grid = new string[]\n    {\n__GRID__\n    };\n    void Start(){ BuildWorld(); }\n    void BuildWorld(){\n        for(int z=0;z<Grid.Length;z++){ var row=Grid[z];\n            for(int x=0;x<row.Length;x++){ float h = Height(row[x]); if(h<0.05f)continue;\n                var box=GameObject.CreatePrimitive(PrimitiveType.Cube); box.name="cell_"+row[x];\n                box.transform.position=new Vector3(x-row.Length/2f,h/2f,z-Grid.Length/2f);\n                box.transform.localScale=new Vector3(1f,h,1f); box.GetComponent<Renderer>().material.color=Color(row[x]);\n            }}\n        var player=GameObject.CreatePrimitive(PrimitiveType.Capsule); player.name="Player";\n        player.transform.position=new Vector3(0,1f,0); player.AddComponent<CharacterController>();\n    }\n    float Height(char ch){ if(ch=='#')return 1f; if(ch=='W')return 0.5f; if(ch=='D')return 1.5f;\n        if(ch=='C'||ch=='K')return 0.6f; if(ch=='G')return 1.3f; return 0f; }\n    Color Color(char ch){ if(ch=='W')return new Color(0.2f,0.5f,0.75f); if(ch=='K')return new Color(0.96f,0.78f,0.35f);\n        if(ch=='G')return new Color(0.3f,0.95f,0.4f); if(ch=='M')return new Color(0.8f,0.2f,0.2f);\n        return Palette[Mathf.Abs(ch*17)%Palette.Length]; }\n}\n`;
  const GD = `extends Node3D\n\n# Nova-1 generated world builder — attach to a Node3D.\nconst PALETTE = [\n__PALETTE__\n]\nconst GRID = [\n__GRID__\n]\nfunc _ready(): _build_world()\nfunc _height(ch: String) -> float:\n\tmatch ch:\n\t\t"#": return 1.0; "W": return 0.5; "D": return 1.5\n\t\t"C", "K": return 0.6; "G": return 1.3\n\t\t_: return 0.0\nfunc _color(ch: String) -> Color:\n\tmatch ch:\n\t\t"W": return Color(0.2,0.5,0.75); "K": return Color(0.96,0.78,0.35)\n\t\t"G": return Color(0.3,0.95,0.4); "M": return Color(0.8,0.2,0.2)\n\t\t_: return PALETTE[abs(ch.hash()) % PALETTE.size()]\nfunc _build_world():\n\tfor z in range(GRID.size()):\n\t\tfor x in range(GRID[z].length()):\n\t\t\tvar ch = GRID[z][x]\n\t\t\tvar h = _height(ch)\n\t\t\tif h < 0.05: continue\n\t\t\tvar box = CSGBox3D.new()\n\t\t\tbox.size = Vector3(1,h,1)\n\t\t\tbox.position = Vector3(x - GRID[z].length()/2.0, h/2.0, z - GRID.size()/2.0)\n\t\t\tvar m = StandardMaterial3D.new(); m.albedo_color = _color(ch)\n\t\t\tbox.material = m\n\t\t\tadd_child(box)\n\tprint("Nova-1 :: world ready")\n`;
  const CPP = `// Nova-1 generated world builder — Unreal C++\n#pragma once\n#include "CoreMinimal.h"\n#include "GameFramework/Actor.h"\n#include "KodrWorldActor.generated.h"\nUCLASS(BlueprintType)\nclass AKodrWorldActor : public AActor\n{\n    GENERATED_BODY()\npublic:\n    AKodrWorldActor();\n    virtual void OnConstruction(const FTransform& Transform) override;\n    UPROPERTY(EditAnywhere, Category="Kodr") UMaterialInterface* CellMaterial = nullptr;\n};\n// ---- cpp ----\n#include "KodrWorldActor.h"\n#include "Components/InstancedStaticMeshComponent.h"\n#include "Engine/StaticMesh.h"\n#include "UObject/ConstructorHelpers.h"\nstatic const TArray<FLinearColor> KodrPalette = TArray<FLinearColor>{\n__PALETTE__\n};\nstatic const TArray<FString> KodrGrid = TArray<FString>{\n__GRID__\n};\nAKodrWorldActor::AKodrWorldActor(){\n    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));\n    auto* ISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("World")); ISM->SetupAttachment(RootComponent);\n    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));\n    if (Cube.Succeeded()) ISM->SetStaticMesh(Cube.Object);\n}\nvoid AKodrWorldActor::OnConstruction(const FTransform& Transform){\n    Super::OnConstruction(Transform);\n    auto* ISM = FindComponentByClass<UInstancedStaticMeshComponent>(); if(!ISM) return;\n    ISM->ClearInstances();\n    for(int z=0;z<KodrGrid.Num();++z){ const FString& Row = KodrGrid[z];\n        for(int x=0;x<Row.Len();++x){ float H=0.0f;\n            switch(Row[x]){ case TEXT('#')[0]: H=1.0f; break; case TEXT('W')[0]: H=0.5f; break;\n                case TEXT('D')[0]: H=1.5f; break; case TEXT('G')[0]: H=1.3f; break; default: continue; }\n            FTransform T(FVector(float(x-Row.Len()/2), float(z-KodrGrid.Num()/2), H/2.0f));\n            T.SetScale3D(FVector(1,1,H)); ISM->AddInstance(T);\n        }}\n}\n`;

  const fillGeneric = (tpl, o, palLine, gridLine) => tpl
    .replace("__PALETTE__", o.pal.map(palLine).join("\n"))
    .replace("__GRID__", o.grid.map(gridLine).join("\n"));

  const novaDemo = (prompt, engine) => {
    const f = features(prompt);
    const seed = stableInt("nova1_" + prompt);
    const theme = detectTheme(prompt);
    const o = { f, pal: PALETTES[theme].colors, themeName: PALETTES[theme].name, themeKey: theme, grid: null };
    const files = {};
    if (engine === "python") { o.grid = grid(seed, 14, f.density); files["nova_game.py"] = fillPy(o); }
    else if (engine === "roblox") { o.grid = grid(seed, 16, f.density); files["ServerScript_NovaGame.lua"] = fillLua(o); files["_README.txt"] = ROBLOX_NOTE; }
    else if (engine === "unity") { o.grid = grid(seed, 12, f.density); files["KodrWorldBuilder.cs"] = fillGeneric(CS, o, (c) => "        new Color32(" + c.join(", ") + ", 255),", (r) => '        "' + r + '",'); }
    else if (engine === "godot") { o.grid = grid(seed, 12, f.density); files["kodr_world.gd"] = fillGeneric(GD, o, (c) => "\tColor(" + c.join(", ") + ", 1.0),", (r) => '\t"' + r + '",'); }
    else { o.grid = grid(seed, 10, f.density); files["KodrWorldActor.h"] = CPP.split("// ---- cpp ----")[0]; files["KodrWorldActor.cpp"] = fillGeneric(CPP.split("// ---- cpp ----")[1], o, (c) => "        FLinearColor(" + c.map((v) => (v / 255).toFixed(3)).join(", ") + ", 1.0f),", (r) => '        TEXT("' + r + '"),'); }
    return { o, files, main: Object.keys(files)[0] };
  };

  let lastNova = null;
  $("#novaGenerate").onclick = async () => {
    const prompt = $("#novaPrompt").value.trim() || "a lava arena survival";
    const engine = $("#novaEngine").value;
    setStatus("#novaStatus", "Nova-1 is generating…");
    if (mode === "server") {
      const u = accountUser();
      const key = u && u.keys.nova1 && !u.keys.nova1.revoked ? u.keys.nova1.key : null;
      if (!key) { setStatus("#novaStatus", "Sign in and create a Nova-1 key to generate via API.", "err"); return; }
      const { ok, j } = await server.nova(prompt, engine, key);
      if (!ok) { setStatus("#novaStatus", (j.error || "API error") + " — falling back to demo.", "err"); }
      else {
        lastNova = { files: j.files, main: j.main_file, meta: `Nova-1 · ${j.theme} · ${j.arch} · seed ${j.seed} · engine ${engine}` };
        renderNova(j.files, j.main_file, j.code, j.preview_ascii || "", j.meta);
        setStatus("#novaStatus", "Generated via your Nova-1 API key — " + j.usage.calls + " calls used.", "ok");
        return;
      }
    }
    const r = novaDemo(prompt, engine);
    lastNova = { files: r.files, main: r.main };
    renderNova(r.files, r.main, r.files[r.main], asciiOf(r.o.grid), `Nova-1 (demo) · ${PALETTES[r.o.themeKey].name} · ${r.f.enemyName}/${r.f.difficulty}`);
    setStatus("#novaStatus", `Demo output — varied by prompt (${r.f.enemyName}, ${r.f.difficulty}, ${r.f.objective.toLowerCase()}). Run server mode for API keys.`);
  };

  const asciiOf = (g) => g.slice(0, 11).map((row) => "  " + [...row.slice(0, 18)].map((ch) => ({ "#": "█", "W": "≈", "C": "$", "M": "M", "K": "k", "P": "@", "D": "D", "G": "!" }[ch] || ".")).join("")).join("\n");

  function renderNova(files, main, code, ascii, meta) {
    $("#novaMeta").textContent = meta;
    $("#novaActions").hidden = false;
    const out = $("#novaOutput");
    out.textContent = (meta.includes("demo") ? code : code);
    const filesWrap = $("#novaFiles");
    filesWrap.innerHTML = "";
    for (const name of Object.keys(files)) {
      const b = document.createElement("button");
      b.className = "btn btn-ghost btn-sm"; b.textContent = name === main ? "Download " + name : name;
      b.onclick = () => download(name, files[name]);
      filesWrap.appendChild(b);
    }
  }
  $("#novaCopy").onclick = () => { if (lastNova) copyText(Object.values(lastNova.files)[0]); };
  $("#novaDownloadMain").onclick = () => { if (lastNova) download(lastNova.main, lastNova.files[lastNova.main]); };

  /* ---------------------------------- rex3d ---------------------------------- */
  const SOLID_H = { "#": 1, W: 0.5, C: 0.6, M: 0.9, K: 0.5, D: 1.4, G: 1.3, P: 0.2 };
  let lastRex = null;

  const rexDemo = (prompt, size) => {
    const f = features(prompt);
    const seed = stableInt("rex3d_" + prompt);
    const theme = detectTheme(prompt);
    const pal = PALETTES[theme].colors;
    const g = grid(seed, size, f.density);
    const cells = [];
    for (let z = 0; z < g.length; z++) for (let x = 0; x < g[z].length; x++) {
      const ch = g[z][x]; const h = SOLID_H[ch];
      if (h) cells.push({ x, z, h, c: ch === "W" ? [54, 120, 190] : ch === "M" ? f.enemyRgb : ch === "C" ? pal[4] : ch === "K" ? [245, 200, 90] : ch === "G" ? [70, 250, 90] : ch === "P" ? [120, 240, 120] : pal[0] });
    }
    return { cells, pal, theme, themeName: PALETTES[theme].name, g };
  };

  function drawIso(canvas, cells, pal) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0b1020"; ctx.fillRect(0, 0, W, H);
    if (!cells.length) return;
    const xs = cells.map((c) => c.x), zs = cells.map((c) => c.z);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const scale = Math.min(W, H) / (Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs)) * 2.4 + 2);
    const P = (x, z, y) => [W / 2 + (x - cx - (z - cz)) * scale, H * 0.62 + ((x - cx + z - cz) * 0.5 - y) * scale * 0.9];
    cells.sort((a, b) => (a.x + a.z) - (b.x + b.z) || a.h - b.h);
    const shade = (c, k) => c.map((v) => Math.max(0, Math.min(255, (v * k) | 0)));
    for (const c of cells) {
      const s = scale * 1.04;
      const topY = c.h * s * 0.9;
      const [px, py] = P(c.x, c.z, 0);
      ctx.fillStyle = `rgb(${shade(c.c, 1.25).join(",")})`;
      ctx.beginPath();
      ctx.moveTo(px, py - topY); ctx.lineTo(px + s / 2, py - s * 0.25 - topY); ctx.lineTo(px, py - s * 0.5 - topY); ctx.lineTo(px - s / 2, py - s * 0.25 - topY);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = `rgb(${c.c.join(",")})`;
      ctx.beginPath();
      ctx.moveTo(px - s / 2, py - s * 0.25); ctx.lineTo(px, py); ctx.lineTo(px, py - topY); ctx.lineTo(px - s / 2, py - s * 0.25 - topY);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = `rgb(${shade(c.c, 0.72).join(",")})`;
      ctx.beginPath();
      ctx.moveTo(px + s / 2, py - s * 0.25); ctx.lineTo(px, py); ctx.lineTo(px, py - topY); ctx.lineTo(px + s / 2, py - s * 0.25 - topY);
      ctx.closePath(); ctx.fill();
    }
  }

  function rexObj(cells) {
    const colors = {};
    let mtl = [], v = [], f = [];
    const keyOf = (c) => c.c.join(",");
    cells.forEach((c) => { const k = keyOf(c); if (!(k in colors)) { colors[k] = "mat" + Object.keys(colors).length; mtl.push("newmtl " + colors[k] + "\nKd " + c.c.map((x) => (x / 255).toFixed(3)).join(" ")); } });
    let vi = 1;
    for (const c of cells) {
      const s = 1, base = [c.x, 0, c.z];
      const corners = [
        [base[0] - s / 2, 0, base[2] - s / 2], [base[0] + s / 2, 0, base[2] - s / 2], [base[0] + s / 2, 0, base[2] + s / 2], [base[0] - s / 2, 0, base[2] + s / 2],
        [base[0] - s / 2, c.h, base[2] - s / 2], [base[0] + s / 2, c.h, base[2] - s / 2], [base[0] + s / 2, c.h, base[2] + s / 2], [base[0] - s / 2, c.h, base[2] + s / 2],
      ];
      corners.forEach((p) => v.push("v " + p.map((n) => n.toFixed(3)).join(" ")));
      const q = [
        [4, 5, 6, 7], [1, 2, 5, 4], [2, 3, 6, 5], [3, 0, 7, 6], [0, 1, 4, 7], [0, 3, 2, 1],
      ];
      f.push("usemtl " + colors[keyOf(c)]);
      q.forEach(([a, b, bb, ccc]) => f.push("f " + (a + vi) + " " + (b + vi) + " " + (bb + vi)), []);
    }
    return "# Kodr / rex3d demo world\nmtllib rex3d.mtl\n" + v.join("\n") + "\n" + f.join("\n") + "\n";
  }

  function rexStl(cells) {
    const tris = [];
    for (const c of cells) {
      const s = 1, a0 = [c.x - s / 2, 0, c.z - s / 2], b0 = [c.x + s / 2, 0, c.z - s / 2], cl = [c.x - s / 2, 0, c.z + s / 2], dl = [c.x + s / 2, 0, c.z + s / 2];
      const a1 = [a0[0], c.h, a0[2]], b1 = [b0[0], c.h, b0[2]], c1 = [cl[0], c.h, cl[2]], d1 = [dl[0], c.h, dl[2]];
      [[b0, dl, b1], [dl, c1, b1], [a0, cl, c1], [cl, a1, c1], [b1, a1, a0], [b1, b0, a0], [d1, a1, c1], [d1, b1, a1], [b0, c1, dl], [b0, b1, c1], [cl, dl, c1], [dl, d1, c1]]
        .forEach((T) => tris.push(T));
    }
    const buf = new ArrayBuffer(84 + 50 * tris.length);
    const dw = new DataView(buf);
    new TextEncoder().encode("Kodr/rex3d STL").forEach((b, i) => dw.setUint8(i, b));
    dw.setUint32(80, tris.length, true);
    let off = 84;
    for (const T of tris) {
      const [p0, p1, p2] = T;
      const ux = p1[0] - p0[0], uy = p1[1] - p0[1], uz = p1[2] - p0[2];
      const vx = p2[0] - p0[0], vy = p2[1] - p0[1], vz = p2[2] - p0[2];
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
      dw.setFloat32(off, nx, true); dw.setFloat32(off + 4, ny, true); dw.setFloat32(off + 8, nz, true); off += 12;
      for (const p of [p0, p1, p2]) { dw.setFloat32(off, p[0], true); dw.setFloat32(off + 4, p[1], true); dw.setFloat32(off + 8, p[2], true); off += 12; }
      dw.setUint16(off, 0, true); off += 2;
    }
    return new Blob([buf], { type: "model/stl" });
  }

  $("#rexGenerate").onclick = async () => {
    const prompt = $("#rexPrompt").value.trim() || "a small arctic village";
    const size = +$("#rexSize").value;
    $("#rexHint").textContent = "";
    if (mode === "server") {
      const u = accountUser();
      const key = u && u.keys.rex3d && !u.keys.rex3d.revoked ? u.keys.rex3d.key : null;
      if (key) {
        setStatus("#rexStatus", "rex3d is building…");
        const { ok, j } = await server.rex(prompt, size, key);
        if (ok) {
          lastRex = { mesh: j.mesh, meta: `rex3d · ${j.theme} · ${(j.meta || {}).voxels} voxels · ${j.size}×${j.size}`, mime: true };
          drawFromDataUrl(j.mesh.preview_b64);
          wireRexDownloads(j.mesh);
          setStatus("#rexStatus", "Built via rex3d API — " + j.usage.calls + " calls used.", "ok");
          $("#rexMeta").textContent = lastRex.meta; $("#rexActions").hidden = false;
          return;
        }
        setStatus("#rexStatus", (j.error || "API error") + " — falling back to demo.", "err");
      }
    }
    const r = rexDemo(prompt, size);
    lastRex = { demo: r };
    $("#rexMeta").textContent = `rex3d (demo) · ${r.themeName} · ${r.cells.length} voxels · ${size}×${size}`;
    drawIso($("#rexCanvas"), r.cells, r.pal);
    $("#rexActions").hidden = false;
    wireRexDownloads(null);
    setStatus("#rexStatus", `Demo world — ${r.cells.length} voxels, ${r.themeName} palette. OBJ/STL in demo, GLB via API.`);
  };
  const drawFromDataUrl = (b64) => { const img = new Image(); img.onload = () => { const c = $("#rexCanvas").getContext("2d"); c.clearRect(0, 0, c.canvas.width, c.canvas.height); c.drawImage(img, 0, 0, c.canvas.width, c.canvas.height); }; img.src = "data:image/png;base64," + b64; };
  const wireRexDownloads = (mesh) => {
    $("#rexObj").onclick = () => {
      if (mesh && mesh.obj) download("rex3d_world.obj", b64Blob(mesh.obj, "text/plain"));
      else if (lastRex.demo) download("rex3d_world.obj", new Blob([rexObj(lastRex.demo.cells)], { type: "text/plain" }));
    };
    $("#rexStl").onclick = () => {
      if (mesh && mesh.stl) download("rex3d_world.stl", b64Blob(mesh.stl, "model/stl"));
      else if (lastRex.demo) download("rex3d_world.stl", rexStl(lastRex.demo.cells));
    };
    $("#rexGlb").onclick = () => {
      if (mesh && mesh.glb) download("rex3d_world.glb", b64Blob(mesh.glb, "model/gltf-binary"));
      else toast("GLB export is available through the rex3d API — sign in or run server mode.");
    };
  };

  /* ---------------------------------- Prism-1 ---------------------------------- */
  let lastPrism = null;

  const prismDemo = (prompt, style, canvas) => {
    const seed = stableInt("prism1_" + prompt);
    const rng = mulberry(seed);
    const theme = detectTheme(prompt);
    const pal = PALETTES[theme].colors;
    const st = style === "auto" ? detectStyle(prompt) : style;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
    const pick = () => pal[Math.floor(rng() * pal.length)];
    ctx.fillStyle = "#0b1020"; ctx.fillRect(0, 0, W, H);
    if (st === "cyber") {
      ctx.fillStyle = `rgb(${mix(pal[0], [0, 0, 0], 0.6).join(",")})`; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = `rgb(${pal[2].join(",")})`; ctx.lineWidth = 2;
      for (let x = 0; x <= W; x += 22) { ctx.beginPath(); ctx.moveTo(x, H); ctx.lineTo(x - 40, 12); ctx.stroke(); }
      for (let y = 0; y < H * 0.55; y += 26) { ctx.beginPath(); ctx.moveTo(0, H - y); ctx.lineTo(W, H - y); ctx.stroke(); }
      for (let i = 0; i < 30; i++) {
        const bw = 18 + rng() * 40, bh = 40 + rng() * 120;
        const bx = rng() * (W - bw), by = H - bh - rng() * 10;
        ctx.fillStyle = `rgb(${pal[2].join(",")})`; ctx.fillRect(bx, by, bw, bh);
        for (let wy = by + 4; wy < by + bh - 4; wy += 12) for (let wx = bx + 4; wx < bx + bw - 6; wx += 10) if (rng() < 0.72) { ctx.fillStyle = `rgb(${pal[4].join(",")})`; ctx.fillRect(wx, wy, 4, 5); }
      }
    } else if (st === "cosmic") {
      for (let i = 0; i < 320; i++) { const c = pick(); ctx.fillStyle = `rgb(${c.join(",")})`; ctx.beginPath(); ctx.arc(rng() * W, rng() * H * 0.9, 0.6 + rng() * 1.8, 0, 7); ctx.fill(); }
      for (let i = 0; i < 6; i++) {
        const g = ctx.createRadialGradient(rng() * W, rng() * H, 6, rng() * W, rng() * H, 90 + rng() * 110);
        const c = pick(); g.addColorStop(0, `rgb(${c.join(",")})`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      }
      const px = W * 0.72, py = H * 0.3;
      const g2 = ctx.createRadialGradient(px, py, 4, px, py, 74);
      g2.addColorStop(0, "#fff"); g2.addColorStop(0.4, `rgb(${mix(pal[2], [255, 255, 255], 0.3).join(",")})`); g2.addColorStop(1, `rgb(${pal[3].join(",")})`);
      ctx.fillStyle = g2; ctx.beginPath(); ctx.arc(px, py, 72, 0, 7); ctx.fill();
    } else if (st === "sunset") {
      for (let y = 0; y < H; y++) { const t = y / H; ctx.fillStyle = `rgb(${mix(pal[3], [30, 18, 44], t).join(",")})`; ctx.fillRect(0, y, W, 1); }
      const horiz = H * 0.58;
      ctx.fillStyle = "rgb(255,240,210)"; ctx.beginPath(); ctx.arc(W / 2, horiz - 4, 46, 0, 7); ctx.fill();
      ctx.fillRect(0, horiz, W, H - horiz);
      for (let i = 0; i < W; i += 6) { ctx.strokeStyle = "rgb(245,190,140)"; ctx.beginPath(); ctx.moveTo(i, horiz); ctx.lineTo(i + 8, horiz + 4 + Math.abs(Math.sin(i / 18))) ; ctx.stroke(); }
    } else if (st === "sprite") {
      const px = Math.min(W, H) / 12;
      const ox = W / 2 - px * 3.6, oy = H * 0.2;
      const fill = (x, y, w, h, col) => { ctx.fillStyle = `rgb(${col.join(",")})`; ctx.fillRect(ox + x * px, oy + y * px, w * px, h * px); };
      ctx.fillStyle = "#f4f4f6"; ctx.fillRect(0, 0, W, H);
      const head = pal[3], body = pal[2], leg = pal[1], eye = pal[4];
      fill(0.6, 1.2, 6, 3.2, head);
      fill(1.9, 2.2, 1, 1.2, [0, 0, 0]); fill(3.8, 2.2, 1, 1.2, [0, 0, 0]);
      fill(1.2, 4.6, 4.6, 3.2, body);
      fill(1.6, 7.8, 1.6, 3.4, leg); fill(3.8, 7.8, 1.6, 3.4, leg);
    } else if (st === "texture") {
      const cell = 128;
      for (let ty = 0; ty < H / cell; ty++) for (let tx = 0; tx < W / cell; tx++) {
        const base = theme;
        ctx.fillStyle = `rgb(${pal[Math.floor(rng() * pal.length)].join(",")})`; ctx.fillRect(tx * cell, ty * cell, cell, cell);
        for (let i = 0; i < 10; i++) { const c = pick(); ctx.fillStyle = `rgb(${c.join(",")})`; ctx.beginPath(); ctx.arc(tx * cell + rng() * cell, ty * cell + rng() * cell, 6 + rng() * 22, 0, 7); ctx.fill(); }
      }
    } else {
      ctx.fillStyle = `rgb(${pal[0].join(",")})`; ctx.fillRect(0, 0, W, H);
      const sx = W * (0.2 + rng() * 0.6), sy = H * 0.26;
      ctx.fillStyle = `rgb(${mix(pal[2], pal[3], 0.5).join(",")})`; ctx.beginPath(); ctx.arc(sx, sy, 44, 0, 7); ctx.fill();
      let prev = H * 0.55;
      ctx.beginPath(); ctx.moveTo(0, prev);
      for (let x = 0; x <= W; x += W / 12) { prev += (rng() - 0.45) * 40; ctx.lineTo(x, prev); }
      ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
      ctx.fillStyle = `rgb(${pal[3].join(",")})`; ctx.fill();
      ctx.fillStyle = `rgb(${pal[1].join(",")})`; ctx.fillRect(0, H * 0.82, W, H * 0.18);
    }
    return { style: st, theme: PALETTES[theme].name, pal: pal.slice(0, 4) };
  };
  const detectStyle = (t) => {
    const low = t.toLowerCase();
    if (["space", "nebula", "galaxy", "cosmic", "star"].some((w) => low.includes(w))) return "cosmic";
    if (["cyber", "neon", "city", "synthwave", "grid", "hologram"].some((w) => low.includes(w))) return "cyber";
    if (["sunset", "dusk", "dawn", "horizon", "ocean", "beach", "sunrise"].some((w) => low.includes(w))) return "sunset";
    if (["sprite", "character", "creature", "icon", "pixel", "item", "sword"].some((w) => low.includes(w))) return "sprite";
    if (["texture", "pattern", "seamless", "tile", "fabric", "stone", "wall"].some((w) => low.includes(w))) return "texture";
    return "landscape";
  };

  $("#prismGenerate").onclick = async () => {
    const prompt = $("#prismPrompt").value.trim() || "a mountain range at dawn";
    const style = $("#prismStyle").value;
    setStatus("#prismStatus", "Prism-1 is painting…");
    if (mode === "server") {
      const u = accountUser();
      const key = u && u.keys.prism1 && !u.keys.prism1.revoked ? u.keys.prism1.key : null;
      if (key) {
        const { ok, j } = await server.prism(prompt, style, key);
        if (ok) {
          lastPrism = { palette: j.palette_hex, style: j.style };
          drawFromDataUrlPrism(j.image_b64);
          showPalette(j.palette_hex);
          $("#prismMeta").textContent = `Prism-1 · ${j.style} · ${j.theme} · seed ${j.seed} · ${j.size[0]}×${j.size[1]}`;
          $("#prismActions").hidden = false;
          setStatus("#prismStatus", "Painted via your Prism-1 API key — " + j.usage.calls + " calls used.", "ok");
          return;
        }
        setStatus("#prismStatus", (j.error || "API error") + " — falling back to demo.", "err");
      }
    }
    const p = prismDemo(prompt, style, $("#prismCanvas"));
    lastPrism = { palette: p.pal.map(hex), style: p.style };
    showPalette(lastPrism.palette);
    $("#prismMeta").textContent = `Prism-1 (demo) · ${p.style} · ${p.theme} · seeded`;
    $("#prismActions").hidden = false;
    setStatus("#prismStatus", `Painted — ${p.style} in the ${p.theme} palette. Server mode adds 640² PNG + API key.`);
  };
  const drawFromDataUrlPrism = (b64) => { const img = new Image(); img.onload = () => { const c = $("#prismCanvas").getContext("2d"); c.clearRect(0, 0, c.canvas.width, c.canvas.height); c.drawImage(img, 0, 0, c.canvas.width, c.canvas.height); }; img.src = "data:image/png;base64," + b64; };
  const showPalette = (arr) => { $("#prismPalette").innerHTML = arr.map((c) => `<span class="sw" style="background:${c}"></span>`).join(""); };
  $("#prismDownload").onclick = () => { const c = $("#prismCanvas"); const link = document.createElement("a"); link.download = "prism1.png"; link.href = c.toDataURL("image/png"); link.click(); };

  /* ---------------------------------- downloads ---------------------------------- */
  const download = (name, content) => {
    const blob = content instanceof Blob ? content : new Blob([content], { type: "text/plain" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  };
  const b64Blob = (b64, type) => { const bin = atob(b64); const arr = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i); return new Blob([arr], { type }); };
  const copyText = (t) => { navigator.clipboard.writeText(t).then(() => toast("Copied to clipboard")); };

  /* ---------------------------------- Roblox bridge ---------------------------------- */
  const ROBLOX_NOTE = `HOW TO RUN (Roblox Studio)\n1. New place from the Baseplate template.\n2. In ServerScriptService, insert a new Script named NovaGame.\n3. Paste ServerScript_NovaGame.lua into it and press Play.\n4. A world builds in ~1s and enemy waves spawn near your character.`;
  $("#rbxCopy").onclick = () => copyText($("#rbxScript").textContent);
  $("#rbxScript").textContent = fillLua(novaDemo("an icy parkour arena with drones", "roblox").o);

  /* ---------------------------------- mode detection ---------------------------------- */
  const detectMode = async () => {
    try {
      const ctrl = new AbortController();
      const tm = setTimeout(() => ctrl.abort(), 2500);
      const r = await fetch("/api/config", { signal: ctrl.signal, credentials: "include" });
      clearTimeout(tm);
      const j = await r.json();
      mode = r.ok && j && j.offline_engines ? "server" : "demo";
    } catch (e) { mode = "demo"; }
    const badge = $("#modeBadge");
    if (mode === "server") { badge.textContent = "Live · connected to the Kodr API (accounts · per-model keys · usage)"; badge.className = "mode-badge live"; }
    else { badge.textContent = "Demo mode — accounts & keys live in this browser. Run `python server.py` for the self-hosted API."; badge.className = "mode-badge demo"; }
    if (mode === "server") await loadMe();
    else { S.user = (S.session && S.demoUsers[S.session]) || null; setAuthUI(); }
  };

  /* ---------------------------------- wiring ---------------------------------- */
  const init = () => {
    applyTheme(localStorage.getItem("kodr_theme") || "light");
    $("#navSignin").onclick = () => openAuth("login");
    $("#navAccount").onclick = () => (S.user ? openAccount() : openAuth("signup"));
    $("#navSignout").onclick = async () => {
      if (mode === "server") await server.logout();
      else { S.session = null; localStorage.removeItem("kodr_session"); }
      S.user = null; setAuthUI(); closeModals(); toast("Signed out.");
    };
    $$("[data-open-account]").forEach((b) => (b.onclick = () => openAuth(b.dataset.force ? b.dataset.force : "signup")));
    $$("[data-close-account]").forEach((b) => (b.onclick = closeModals));
    $("#authForm").addEventListener("submit", onAuthSubmit);
    $$("#authTabs .auth-tab").forEach((b) => (b.onclick = () => { authForm = b.dataset.aform; renderAuthTabs(); }));
    $("#keysList").addEventListener("click", (e) => {
      const rt = e.target.closest("[data-rotate]"), rv = e.target.closest("[data-revoke]");
      if (rt) onKeyAction(rt.dataset.rotate, "rotate");
      if (rv) onKeyAction(rv.dataset.revoke, "revoke");
    });
    /* play button seeds each model's demo on first focus */
    $("#novaGenerate").click();
    detectMode();
  };
  document.addEventListener("DOMContentLoaded", init);
})();