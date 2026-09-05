(() => {
  "use strict";

  const year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();

  /* ---------- hero terminal typing ---------- */
  const CODE = `local function makeArena(cfg)
  -- lava ring, animated each 30s
  local ring = buildRing(cfg.size, cfg.tile)
  gameOmit:ForEach(enemy) spawn(fighter)
  tween(ring, { shrink = 0.9 }, 30, loop = true)
end
-- wall-jump controller with coyote time
local coyote = 0.12
if time - lastGround <= coyote then
  Jump(math.max(jump, 62))
end`;

  const lineEl = document.getElementById("type-line");
  const cursorEl = lineEl ? lineEl.nextElementSibling : null;

  function typeCode(el, text) {
    let i = 0;
    const step = () => {
      if (document.hidden) { setTimeout(step, 200); return; }
      el.textContent = text.slice(0, i);
      i += 1;
      if (i <= text.length) setTimeout(step, 8);
    };
    step();
  }
  if (lineEl) setTimeout(() => typeCode(lineEl, CODE), 700);

  /* ---------- engine tabs ---------- */
  const SNIPPETS = {
    lua: `-- Roblox · Luau · server-side hit validation
swingRemote.OnServerEvent:Connect(function(player)
  if os.clock() - cd[player] < 0.8 then return end
  cd[player] = os.clock()
  local hit = workspace:Raycast(origin, dir * 10, params)
  if hit then hit.Instance.Parent.Humanoid:TakeDamage(25) end
end)`,
    cs: `// Unity · C# · object pool, zero alloc
GameObject go = pool.Dequeue();
go.transform.SetPositionAndRotation(pos, rot);
go.SetActive(true);
if (go.TryGetComponent<Rigidbody>(out var rb)) rb.velocity = Vector3.zero;`,
    gd: `# Godot · GDScript · coyote-time jump
if Input.is_action_just_pressed("jump"):
    var in_coyote = now - last_grounded < 0.12
    if is_on_floor() or in_coyote:
        velocity.y = jump_velocity
move_and_slide()`,
    cpp: `// Unreal · C++ · damage broadcast
void UHealthComponent::TakeDamage(float Amount)
{
    const float Old = CurrentHealth;
    CurrentHealth = FMath::Clamp(CurrentHealth - Amount, 0.f, MaxHealth);
    OnHealthChanged.Broadcast(this, Old, CurrentHealth);
}`,
  };

  const tabs = document.querySelectorAll(".tab");
  const body = document.getElementById("tab-body");
  if (tabs.length && body) {
    body.textContent = SNIPPETS.lua;
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        body.textContent = SNIPPETS[tab.dataset.tab] || "";
      });
    });
  }

  /* ---------- scroll reveal ---------- */
  const hero = document.querySelector(".hero");
  if (hero) hero.classList.add("in");
  const targets = document.querySelectorAll(".section, .marquee");
  targets.forEach((el) => el.classList.add("reveal"));
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
      },
      { threshold: 0.12 }
    );
    targets.forEach((el) => io.observe(el));
  } else {
    targets.forEach((el) => el.classList.add("in"));
  }

  /* ---------- mobile menu ---------- */
  const burger = document.querySelector(".nav-burger");
  const links = document.querySelector(".nav-links");
  if (burger && links) {
    burger.addEventListener("click", () => {
      const open = links.style.display === "flex";
      links.style.display = open ? "" : "flex";
      links.style.position = "absolute";
      links.style.top = "100%";
      links.style.left = "0";
      links.style.right = "0";
      links.style.flexDirection = "column";
      links.style.background = "rgba(5,6,10,.96)";
      links.style.padding = "1rem 1.4rem";
      links.style.borderBottom = "1px solid #1c2233";
      if (open) { links.style.display = ""; links.style.position = ""; }
    });
  }
})();