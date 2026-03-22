console.log("[CHM] app.js loaded, starting...");
/* ═══════════════════════════════════════════════════════════════════════
   CHM Smart Money Academy — app.js v6.0
   72h Deadlines · SMC Levels · Streak · Penalty Flow · Countdown Timer
   ═══════════════════════════════════════════════════════════════════════ */

// ── CONFIG ────────────────────────────────────────────────────────────────
const API     = "/api";
const tg      = window.Telegram?.WebApp ?? null;
const DEV_UID = 445677777;

// ══════════════════════════════════════════════════════════════════════
// ── SOUND ENGINE v2 — Web Audio API, zero files ──────────────────────
// ══════════════════════════════════════════════════════════════════════
const _sfx = (() => {
  let ctx = null;
  const gc = () => {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  };
  const t = (freq, type, dur, gain = 0.22, delay = 0) => {
    try {
      const c = gc(), o = c.createOscillator(), g = c.createGain();
      o.connect(g); g.connect(c.destination);
      o.type = type; o.frequency.setValueAtTime(freq, c.currentTime + delay);
      g.gain.setValueAtTime(0, c.currentTime + delay);
      g.gain.linearRampToValueAtTime(gain, c.currentTime + delay + 0.01);
      g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + delay + dur);
      o.start(c.currentTime + delay); o.stop(c.currentTime + delay + dur + 0.05);
    } catch(e) {}
  };
  const n = (dur, gain = 0.10) => {
    try {
      const c = gc(), buf = c.createBuffer(1, c.sampleRate * dur, c.sampleRate);
      const d = buf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      const s = c.createBufferSource(), g = c.createGain();
      s.buffer = buf; s.connect(g); g.connect(c.destination);
      g.gain.setValueAtTime(gain, c.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + dur);
      s.start(); s.stop(c.currentTime + dur);
    } catch(e) {}
  };
  return { t, n };
})();

const SOUNDS = {
  tap:          () => _sfx.t(480, "sine", 0.05, 0.11),
  combo10:      () => { _sfx.t(660,"sine",0.08,0.18); _sfx.t(880,"sine",0.08,0.18,0.07); },
  combo50:      () => [440,550,660,880].forEach((f,i)=>_sfx.t(f,"triangle",0.12,0.22,i*.05)),
  combo100:     () => { [440,550,660,770,880,1100].forEach((f,i)=>_sfx.t(f,"sine",0.18,0.28,i*.04)); _sfx.n(0.16,0.04); },
  xp:           () => { _sfx.t(880,"sine",0.07,0.14); _sfx.t(1100,"sine",0.07,0.12,0.08); },
  levelup:      () => { [440,550,660,880,1100,1320].forEach((f,i)=>_sfx.t(f,"triangle",0.28,0.34,i*.07)); _sfx.n(0.26,0.04); },
  questdone:    () => [523,659,784,1047].forEach((f,i)=>_sfx.t(f,"sine",0.22,0.30,i*.08)),
  soulsgain:    () => { _sfx.t(660,"sine",0.09,0.17); _sfx.t(880,"sine",0.09,0.13,0.06); },
  soulslost:    () => { _sfx.t(330,"sawtooth",0.12,0.19); _sfx.t(220,"sawtooth",0.12,0.17,0.07); },
  hit:          () => { _sfx.n(0.07,0.26); _sfx.t(150,"sawtooth",0.09,0.20); },
  catalyst_on:  () => {
    [200,180,160,140,120].forEach((f,i)=>_sfx.t(f,"sawtooth",0.14,0.30,i*.04));
    _sfx.n(0.26,0.10);
    setTimeout(()=>_sfx.t(440,"sine",0.22,0.28),280);
  },
  neutralized:  () => { [880,770,660,550,440,330].forEach((f,i)=>_sfx.t(f,"sine",0.17,0.27,i*.055)); _sfx.n(0.18,0.06); },
  evolution:    () => [440,550,660,880,1100,1320,1760].forEach((f,i)=>_sfx.t(f,"sine",0.30,0.30,i*.06)),
  bosswin:      () => { [440,550,659,880,1100,1320].forEach((f,i)=>_sfx.t(f,"triangle",0.36,0.36,i*.08)); _sfx.n(0.35,0.06); },
  err:          () => _sfx.t(200,"square",0.09,0.13),
  buy:          () => { _sfx.t(880,"sine",0.06,0.16); _sfx.t(1320,"sine",0.06,0.14,0.06); _sfx.t(1760,"sine",0.06,0.12,0.12); },
  bonus:        () => [523,659,784].forEach((f,i)=>_sfx.t(f,"sine",0.14,0.24,i*.07)),
};

let _soundOn = localStorage.getItem("chm_sfx") !== "0";
function playSound(id) {
  if (!_soundOn || !SOUNDS[id]) return;
  try { SOUNDS[id](); } catch(e) {}
}
function toggleSound() {
  _soundOn = !_soundOn;
  localStorage.setItem("chm_sfx", _soundOn ? "1" : "0");
  const btn = document.getElementById("soundBtn");
  if (btn) btn.textContent = _soundOn ? "🔊" : "🔇";
  if (_soundOn) playSound("bonus");
}
window.toggleSound = toggleSound;

// ── GLOBAL STATE ──────────────────────────────────────────────────────────
const state = {
  userId: null,
  sessionToken: null,   // set after /api/user/init; sent with write requests
  userState: null,
  quizData: null,
  currentQuestId: null,
  lessonsMetaCache: {},
  quizStreak: 0,
  countdownInterval: null,
  deadlineInfo: null,
  _catalystInterval: null,   // guard against duplicate setInterval on init() retry
  _actionsInterval: null,    // guard against duplicate setInterval on init() retry
};

// ── SMC TRADER LEVELS (7 levels) ──────────────────────────────────────────
const SMC_LEVELS = [
  { xp: 0,    level: 1, name: "Наблюдатель рынка",       color: "#78716c", glow: "rgba(120,113,108,0.4)" },
  { xp: 300,  level: 2, name: "Охотник за ликвидностью", color: "#00d4ff", glow: "rgba(0,212,255,0.4)"  },
  { xp: 700,  level: 3, name: "Снайпер ордер-блоков",    color: "#a78bfa", glow: "rgba(167,139,250,0.4)" },
  { xp: 1300, level: 4, name: "SMC Практик",             color: "#00e87a", glow: "rgba(0,232,122,0.4)"  },
  { xp: 2100, level: 5, name: "Smart Money Инсайдер",    color: "#f59e0b", glow: "rgba(245,158,11,0.5)"  },
  { xp: 3200, level: 6, name: "Институциональный призрак",color: "#fbbf24", glow: "rgba(251,191,36,0.5)" },
  { xp: 5000, level: 7, name: "Архитектор рынка",        color: "#ff4d6d", glow: "rgba(255,77,109,0.6)"  },
];

const LEVEL_QUOTES = [
  "",
  "Биткоин не ждал тебя в 2017. Не будет ждать и сейчас.",
  "Ты видишь ликвидность там, где другие видят поддержку.",
  "Каждый OB — это след Smart Money. Ты научился его читать.",
  "Рынок манипулятивен. Ты знаешь, как.",
  "Ты торгуешь не по индикаторам — ты торгуешь по логике SM.",
  "Институциональные трейдеры не знают, что ты за ними следишь.",
  "Архитектор рынка — ты понимаешь структуру, которую другие не видят.",
];

function getLevelInfo(xp) {
  let info = SMC_LEVELS[0];
  for (const lvl of SMC_LEVELS) {
    if (xp >= lvl.xp) info = lvl;
  }
  return info;
}

// ── SVG RANK ICONS ────────────────────────────────────────────────────────
let _svgGradientCounter = 0;
function getRankSVG(rankName) {
  const lvl = SMC_LEVELS.find(l => l.name === rankName) || SMC_LEVELS[0];
  const c = lvl.color;
  // Use unique gradient IDs to prevent conflicts when multiple SVGs exist in the DOM
  const uid = ++_svgGradientCounter;
  if (lvl.level === 7) {
    const gid = `rg7_${uid}`;
    return `<svg viewBox="0 0 40 40" fill="none">
      <defs><radialGradient id="${gid}" cx="40%" cy="35%" r="60%">
        <stop offset="0%" stop-color="#ff8fa3"/><stop offset="100%" stop-color="#cc1133"/>
      </radialGradient></defs>
      <circle cx="20" cy="20" r="16" fill="#150508" stroke="${c}" stroke-width="2"/>
      <circle cx="20" cy="20" r="12" fill="url(#${gid})" opacity="0.2"/>
      <path d="M20 8L23 16H32L25 21L28 30L20 25L12 30L15 21L8 16H17Z" fill="url(#${gid})"/>
      <circle cx="20" cy="18" r="3" fill="white" opacity="0.4"/>
    </svg>`;
  }
  if (lvl.level >= 5) {
    return `<svg viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="16" fill="#0a0c10" stroke="${c}" stroke-width="2"/>
      <circle cx="20" cy="20" r="10" fill="${c}" opacity="0.15"/>
      <path d="M20 8 L23 16H32L25 21L28 30L20 25L12 30L15 21L8 16H17Z" fill="${c}" opacity="0.9"/>
      <circle cx="20" cy="19" r="3" fill="white" opacity="0.3"/>
    </svg>`;
  }
  return `<svg viewBox="0 0 40 40" fill="none">
    <circle cx="20" cy="20" r="16" fill="#111420" stroke="${c}" stroke-width="2"/>
    <circle cx="20" cy="20" r="10" fill="${c}" opacity="0.2"/>
    <path d="M20 10 L22.5 17H30L24 21.5L26.5 29L20 24.5L13.5 29L16 21.5L10 17H17.5Z" fill="${c}"/>
  </svg>`;
}

// ── INIT ──────────────────────────────────────────────────────────────────
if (tg) { tg.ready(); tg.expand(); tg.setHeaderColor("#060810"); }

function getUserInfo() {
  if (tg?.initDataUnsafe?.user) {
    const u = tg.initDataUnsafe.user;
    if (u.id) return { id: u.id, username: u.username || null, first_name: u.first_name || null, last_name: u.last_name || null };
  }
  return { id: DEV_UID, username: "dev_user", first_name: "Dev", last_name: null };
}

// ── DOM HELPERS ───────────────────────────────────────────────────────────
const $ = s => document.querySelector(s);
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls)  e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}


// ── SYNTHESIS RITUAL ONBOARDING ───────────────────────────────────────────

// Called from init() — checks server flag first, then runs ritual if needed.
// `onboardingDone` is set from initData.onboarding_complete in init().
let _ritualActive = false;

function initOnboarding(onboardingComplete) {
  // Already done (server flag takes precedence over localStorage)
  if (onboardingComplete || localStorage.getItem("smc_ritual_done")) return;
  _ritualActive = true;
  const overlay = $("#synthRitual");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  _runRitualPhase1();
}

// ── Phase 1: Dark screen + typewriter text ──────────────────────────────
function _runRitualPhase1() {
  const phase = $("#srPhase1");
  if (!phase) return;
  phase.style.display = "flex";
  _typewriter("srText1", "Ты пришёл учиться у рынка.", 40, () => {
    setTimeout(_runRitualPhase2, 1500);
  });
}

// ── Phase 2: Warning text ───────────────────────────────────────────────
function _runRitualPhase2() {
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
  const p1 = $("#srPhase1");
  const p2 = $("#srPhase2");
  if (p1) p1.style.display = "none";
  if (!p2) return;
  p2.style.display = "flex";
  const t1b = $("#srText1b");
  if (t1b) t1b.textContent = "Ты пришёл учиться у рынка.";
  _typewriter("srText2", "Рынок не прощает. Мы тоже.", 45, () => {
    setTimeout(_runRitualPhase3, 2000);
  });
}

// ── Phase 3: Flask appears, waiting for tap ─────────────────────────────
function _runRitualPhase3() {
  const p2 = $("#srPhase2");
  const p3 = $("#srPhase3");
  if (p2) p2.style.display = "none";
  if (!p3) return;
  p3.style.display = "flex";
  p3.style.opacity = "0";
  p3.style.transition = "opacity 2s ease";
  requestAnimationFrame(() => { p3.style.opacity = "1"; });
  // Auto-advance if user doesn't tap the flask within 10 seconds
  setTimeout(() => { if (_ritualActive) onRitualFlaskTap(); }, 10000);
}

// ── Phase 4: Tap on flask → synthesis ──────────────────────────────────
function onRitualFlaskTap() {
  if (!_ritualActive) return;
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("heavy");
  const p3 = $("#srPhase3");
  const p4 = $("#srPhase4");
  if (p3) p3.style.display = "none";
  if (!p4) return;
  p4.style.display = "flex";
  // Flash effect
  const flash = $("#srFlash");
  if (flash) {
    flash.style.animation = "none";
    void flash.offsetWidth;
    flash.classList.add("synth-flash--active");
    setTimeout(() => flash.classList.remove("synth-flash--active"), 700);
  }
  setTimeout(_runRitualPhase5, 1800);
}
window.onRitualFlaskTap = onRitualFlaskTap;

// ── Phase 5: Homunculus born, souls counter ─────────────────────────────
function _runRitualPhase5() {
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  const p4 = $("#srPhase4");
  const p5 = $("#srPhase5");
  if (p4) p4.style.display = "none";
  if (!p5) return;
  p5.style.display = "flex";
  // Animate souls counter from 0 to 50
  let count = 0;
  const numEl = $("#srSoulsNum");
  const interval = setInterval(() => {
    count += 2;
    if (numEl) numEl.textContent = count;
    if (count >= 50) { clearInterval(interval); if (numEl) numEl.textContent = "50"; }
  }, 40);
  setTimeout(_runRitualPhase6, 3500);
}

// ── Phase 6: Tooltips ───────────────────────────────────────────────────
function _runRitualPhase6() {
  const p5 = $("#srPhase5");
  const p6 = $("#srPhase6");
  if (p5) p5.style.display = "none";
  if (!p6) return;
  p6.style.display = "flex";
  // Auto-complete if user doesn't click through tooltips within 12 seconds
  setTimeout(() => { if (_ritualActive) onRitualComplete(); }, 12000);
}

function onRitualTooltip1() {
  const t1 = $("#srTooltip1");
  const t2 = $("#srTooltip2");
  if (t1) t1.style.display = "none";
  if (t2) t2.style.display = "block";
}
window.onRitualTooltip1 = onRitualTooltip1;

async function onRitualComplete() {
  _ritualActive = false;
  const overlay = $("#synthRitual");
  if (overlay) {
    overlay.style.transition = "opacity 0.6s ease";
    overlay.style.opacity = "0";
    setTimeout(() => overlay.classList.add("hidden"), 650);
  }
  localStorage.setItem("smc_ritual_done", "1");
  // Tell server onboarding is complete (awards +50 souls)
  try {
    if (state.userId) {
      const res  = await fetch(`${API}/onboarding/complete`, {
        method:  "POST",
        headers: {"Content-Type": "application/json"},
        body:    JSON.stringify({user_id: state.userId}),
      });
      const data = await res.json();
      if (data.total_souls != null) {
        state.souls = data.total_souls;
        _updateSoulsDisplay(state.souls);
      }
    }
  } catch(e) { console.warn("onboarding/complete error:", e); }
}
window.onRitualComplete = onRitualComplete;

// ── Typewriter helper ───────────────────────────────────────────────────
function _typewriter(elId, text, msPerChar, onDone) {
  const el = $(`#${elId}`);
  if (!el) { if (onDone) onDone(); return; }
  el.textContent = "";
  let i = 0;
  const interval = setInterval(() => {
    el.textContent += text[i];
    i++;
    if (i >= text.length) {
      clearInterval(interval);
      if (onDone) setTimeout(onDone, 100);
    }
  }, msPerChar);
}

// ── CONFETTI ──────────────────────────────────────────────────────────────
const CONFETTI_COLORS = ["#00d4ff", "#fbbf24", "#00e87a", "#a78bfa", "#ff4d6d", "#f97316"];

function launchConfetti(count = 80) {
  const layer = $("#confettiLayer");
  if (!layer) return;
  for (let i = 0; i < count; i++) {
    const piece = document.createElement("div");
    piece.className = "confetti-piece";
    const dur = 1.8 + Math.random() * 1.5;
    const delay = Math.random() * 0.8;
    piece.style.cssText = `
      left: ${Math.random() * 100}%;
      animation-duration: ${dur}s; animation-delay: ${delay}s;
      background: ${CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)]};
      width: ${6 + Math.random() * 8}px; height: ${6 + Math.random() * 8}px;
      border-radius: ${Math.random() > 0.5 ? "50%" : "2px"};
      transform: rotate(${Math.random() * 360}deg);
    `;
    layer.appendChild(piece);
    setTimeout(() => piece.remove(), (dur + delay) * 1000 + 100);
  }
}

// ── XP FLOAT ──────────────────────────────────────────────────────────────
function floatXP(amount, sourceEl) {
  const layer = $("#xpFloatLayer");
  if (!layer) return;
  const rect = sourceEl ? sourceEl.getBoundingClientRect() : { left: window.innerWidth/2, top: window.innerHeight/2, width: 0 };
  const e = document.createElement("div");
  e.className = "xp-float";
  e.textContent = `+${amount} XP`;
  e.style.left = (rect.left + (rect.width||0)/2) + "px";
  e.style.top  = rect.top + "px";
  layer.appendChild(e);
  setTimeout(() => e.remove(), 1700);
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

// ── LEVEL UP SCREEN ───────────────────────────────────────────────────────
function showLevelUp(level, rankName) {
  const overlay = $("#levelUpOverlay");
  if (!overlay) return;
  const lvlInfo = getLevelInfo(state.userState?.xp || 0);
  $("#levelupNum").textContent      = level;
  $("#levelupRankName").textContent = rankName || lvlInfo.name;
  $("#levelupRankIcon").innerHTML   = getRankSVG(rankName || lvlInfo.name);
  $("#levelupQuote").textContent    = LEVEL_QUOTES[level] || "";

  const container = $("#levelupParticles");
  container.innerHTML = "";
  for (let i = 0; i < 24; i++) {
    const p = document.createElement("div");
    p.className = "levelup-particle";
    const angle = (i / 24) * 360;
    const dist  = 80 + Math.random() * 80;
    const color = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)];
    p.style.cssText = `
      --tx: ${Math.cos(angle*Math.PI/180)*dist}px;
      --ty: ${Math.sin(angle*Math.PI/180)*dist}px;
      --dur: ${0.8 + Math.random()*0.6}s;
      background: ${color}; left:50%; top:50%; box-shadow:0 0 6px ${color};
    `;
    container.appendChild(p);
  }
  overlay.classList.remove("hidden");
  launchConfetti(120);
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

document.getElementById("levelupCloseBtn")?.addEventListener("click", () => {
  $("#levelUpOverlay").classList.add("hidden");
});

// ── COUNTDOWN TIMER ───────────────────────────────────────────────────────
function startCountdown(deadlineISO) {
  if (state.countdownInterval) {
    clearInterval(state.countdownInterval);
    state.countdownInterval = null;
  }
  if (!deadlineISO) {
    $("#deadlineCountdown")?.classList.add("hidden");
    return;
  }

  const cdEl = $("#deadlineCountdown");
  const timerEl = $("#countdownTimer");
  if (!cdEl || !timerEl) return;
  cdEl.classList.remove("hidden");

  function update() {
    const now = Date.now();
    const end = new Date(deadlineISO).getTime();
    const diff = end - now;

    if (diff <= 0) {
      timerEl.textContent = "00:00:00";
      cdEl.className = "deadline-countdown urgency-expired";
      clearInterval(state.countdownInterval);
      state.countdownInterval = null;
      showDeadlineExpiredScreen();
      return;
    }

    const hours = Math.floor(diff / 3600000);
    const mins  = Math.floor((diff % 3600000) / 60000);
    const secs  = Math.floor((diff % 60000) / 1000);
    timerEl.textContent = `${String(hours).padStart(2,"0")}:${String(mins).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;

    // Urgency classes
    const hoursLeft = diff / 3600000;
    if (hoursLeft <= 1) {
      cdEl.className = "deadline-countdown urgency-critical";
    } else if (hoursLeft <= 6) {
      cdEl.className = "deadline-countdown urgency-danger";
    } else if (hoursLeft <= 24) {
      cdEl.className = "deadline-countdown urgency-warning";
    } else {
      cdEl.className = "deadline-countdown urgency-normal";
    }
  }

  update();
  state.countdownInterval = setInterval(update, 1000);
}

// ── DEADLINE EXPIRED SCREEN ───────────────────────────────────────────────
function showDeadlineExpiredScreen() {
  const overlay = $("#deadlineExpiredOverlay");
  if (!overlay) return;

  const dlInfo = state.deadlineInfo;
  const moduleIdx = state.userState?.module_index ?? 0;

  // Set penalty amounts from deadline info
  const penaltyAmount = dlInfo?.penalty_amount ?? 5;
  const repurchaseAmount = dlInfo?.repurchase_amount ?? 15;

  const penaltyTxt = $("#penaltyAmountText");
  const repurchaseTxt = $("#repurchaseAmountText");
  if (penaltyTxt) penaltyTxt.textContent = `$${penaltyAmount}`;
  if (repurchaseTxt) repurchaseTxt.textContent = `$${repurchaseAmount}`;

  // Show repurchase option if extensions exhausted
  const canExtend = dlInfo?.can_extend ?? true;
  const penaltyOpt = $("#penaltyOption");
  const repurchaseOpt = $("#repurchaseOption");
  if (canExtend) {
    penaltyOpt?.classList.remove("hidden");
    repurchaseOpt?.classList.add("hidden");
  } else {
    penaltyOpt?.classList.add("hidden");
    repurchaseOpt?.classList.remove("hidden");
  }

  overlay.classList.remove("hidden");
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
}

// Pay penalty handler
document.getElementById("payPenaltyBtn")?.addEventListener("click", async () => {
  const btn = $("#payPenaltyBtn");
  btn.disabled = true;
  btn.textContent = "⏳ Обработка...";

  try {
    const res = await fetch(`${API}/deadline/penalty`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: state.userId,
        module_index: state.userState?.module_index ?? 0,
        payment_type: "penalty",
      }),
    });
    const data = await res.json();
    if (data.ok) {
      $("#deadlineExpiredOverlay").classList.add("hidden");
      state.deadlineInfo = data.deadline_info;
      startCountdown(data.new_deadline_iso);
      showToast("Штраф оплачен. У тебя 48 часов. Не теряй их.", "success");
      await refreshHeader();
      await loadQuests();
    } else {
      showToast(data.message || "Ошибка", "error");
      btn.disabled = false;
      btn.textContent = "Оплатить и продолжить →";
    }
  } catch (e) {
    console.error("payPenalty:", e);
    showToast("Ошибка сети", "error");
    btn.disabled = false;
    btn.textContent = "Оплатить и продолжить →";
  }
});

// Repurchase handler
document.getElementById("repurchaseBtn")?.addEventListener("click", async () => {
  const btn = $("#repurchaseBtn");
  btn.disabled = true;
  btn.textContent = "⏳ Обработка...";

  try {
    const res = await fetch(`${API}/deadline/penalty`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: state.userId,
        module_index: state.userState?.module_index ?? 0,
        payment_type: "repurchase",
      }),
    });
    const data = await res.json();
    if (data.ok) {
      $("#deadlineExpiredOverlay").classList.add("hidden");
      state.deadlineInfo = data.deadline_info;
      startCountdown(data.deadline_info?.deadline_iso);
      showToast("Модуль перекуплен. Новый дедлайн: 72 часа.", "success");
      await refreshHeader();
      await loadQuests();
    } else {
      showToast(data.message || "Ошибка", "error");
      btn.disabled = false;
      btn.textContent = "Перекупить доступ →";
    }
  } catch (e) {
    showToast("Ошибка сети", "error");
    btn.disabled = false;
    btn.textContent = "Перекупить доступ →";
  }
});

// ── TABS ──────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.toggle("active", c.id === `tab-${name}`));
  if (name === "quests")       loadQuests();
  if (name === "leaderboard")  { loadLeaderboard(); loadPersonalLeaderboard(); loadBattlePass(); loadRaid(); }
  if (name === "homunculus")   { loadHomunculus(); loadShop(); loadReferral(); }
  if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
}
window.switchTab = switchTab;

// ── MODALS ────────────────────────────────────────────────────────────────
function openModal(id)  { const sel = id.startsWith('#') ? id : '#'+id; $(sel)?.classList.remove("hidden"); if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light"); }
function closeModal(id) { const sel = id.startsWith('#') ? id : '#'+id; $(sel)?.classList.add("hidden"); }
window.closeModal = closeModal;

// ── MARKDOWN RENDERER ─────────────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return "";
  const div   = document.createElement("div");
  const lines = text.split("\n");
  lines.forEach((line, idx) => {
    if (!line.trim()) { if (idx > 0) div.appendChild(document.createElement("br")); return; }
    const p = document.createElement("span");
    p.style.display = "block";
    const parts = line.split(/\*([^*]+)\*/g);
    parts.forEach((part, i) => {
      if (i % 2 === 1) { const s = document.createElement("strong"); s.textContent = part; p.appendChild(s); }
      else if (part) p.appendChild(document.createTextNode(part));
    });
    if (line.startsWith("• ") || line.match(/^[1-9][️⃣)\\.] /)) p.className = "bullet";
    div.appendChild(p);
  });
  return div.innerHTML;
}

// ── RENDER USER STATE ─────────────────────────────────────────────────────
function renderHeader(s) {
  if (!s) return;

  // Аватар
  const avatarEl = document.getElementById("headerAvatarSvg");
  if (avatarEl) avatarEl.innerHTML = getRankSVG(s.rank || "Наблюдатель рынка").replace(/<svg[^>]*>/,'').replace('</svg>','');

  // Имя и ранг
  const nameEl = document.getElementById("headerUsername");
  if (nameEl) nameEl.textContent = (s.name || "CHM").slice(0,14);
  const rankEl = document.getElementById("headerRankName");
  if (rankEl) rankEl.textContent = s.rank || "Наблюдатель рынка";

  // HUD пиллы
  const soulsEl = document.getElementById("hudSoulsVal");
  if (soulsEl) soulsEl.textContent = Math.floor(s.souls || 0);
  const xpEl = document.getElementById("hudXPVal");
  if (xpEl) xpEl.textContent = s.xp || 0;
  const lvlEl = document.getElementById("hudLevelVal");
  if (lvlEl) lvlEl.textContent = s.level || 1;

  // moduleName
  const modEl = document.getElementById("moduleName");
  if (modEl) modEl.textContent = `Модуль ${(s.module_index ?? 0) + 1}`;

  // Estus flasks
  updateEstusHUD(s.estus_flasks ?? 3, s.estus_max ?? 3);

  // Прогресс-бар (обновляется из renderQuests тоже)
  state.userState = s;
}

function setProgress(completed, total) {
  const pct = total > 0 ? Math.round(completed / total * 100) : 0;
  const bar  = $("#progressBar");
  const glow = $("#progressGlow");
  if (bar)  bar.style.width = pct + "%";
  if (glow) glow.style.left = pct + "%";
  if ($("#progressLabel")) $("#progressLabel").textContent = `${completed}/${total} протоколов`;
  if ($("#progressPct"))   $("#progressPct").textContent = pct + "%";
}

function applyDeadlineInfo(dlInfo) {
  if (!dlInfo) return;
  state.deadlineInfo = dlInfo;

  // Show module subtitle if available
  const subEl = $("#moduleSubtitle");
  if (subEl && state.userState) {
    // Will be set from quests response
  }

  if (dlInfo.deadline_expired) {
    showDeadlineExpiredScreen();
    return;
  }

  if (dlInfo.deadline_iso) {
    startCountdown(dlInfo.deadline_iso);
  } else {
    $("#deadlineCountdown")?.classList.add("hidden");
  }
}

// ── RENDER MODULES ────────────────────────────────────────────────────────
function renderModules(modules) {
  const container = $("#modulesList");
  if (!container) return;
  container.innerHTML = "";
  if (!modules || modules.length === 0) {
    container.innerHTML = '<div style="padding:20px;text-align:center;color:#666">Уроки не загружены. Проверь соединение.</div>';
    return;
  }
  const currentModuleIdx = state.userState?.module_index ?? 0;

  modules.forEach((mod, idx) => {
    const isCurrentOrPast = idx <= currentModuleIdx;
    const isFree = mod.is_free;
    const isLocked = !isFree && idx > currentModuleIdx;

    const card   = el("div", `module-card${isLocked ? " locked" : ""}${idx === currentModuleIdx ? " current" : ""}`);
    const header = el("div", "module-header");

    const titleWrap = el("div", "module-title-wrap");
    const numBadge  = el("div", `module-num-badge${idx < currentModuleIdx ? " done" : idx === currentModuleIdx ? " active" : ""}`,
      idx < currentModuleIdx ? "✓" : `${idx + 1}`
    );
    const titleInfo = el("div", "module-title-info");
    const title     = el("div", "module-title", `${mod.title}`);
    const subtitle  = el("div", "module-subtitle-small", mod.subtitle || "");
    titleInfo.append(title, subtitle);
    titleWrap.append(numBadge, titleInfo);

    const right = el("div", "module-header-right");
    if (isFree) right.appendChild(el("div", "module-free-badge", "БЕСПЛАТНО"));
    if (isLocked) right.appendChild(el("div", "module-lock-icon", "🔒"));
    const chev = el("div", "module-chevron", "▼");
    right.append(chev);
    header.append(titleWrap, right);
    card.append(header);

    const list = el("div", "lesson-list");
    (mod.lessons || []).forEach(key => {
      const meta  = state.lessonsMetaCache[key];
      const name  = meta ? meta.title : key;
      const item  = el("div", `lesson-item${isLocked ? " lesson-locked" : ""}`);
      const lname = el("div", "lesson-name", name);
      const arr   = el("div", "lesson-arrow", isLocked ? "🔒" : "›");
      item.append(lname, arr);
      if (!isLocked) {
        item.addEventListener("click", () => openLesson(key));
      } else {
        item.addEventListener("click", () => showToast("Пройди текущий модуль чтобы открыть этот", "info"));
      }
      list.appendChild(item);
    });

    card.appendChild(list);
    header.addEventListener("click", () => {
      if (!isLocked) {
        card.classList.toggle("open");
        if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
      }
    });

    // Auto-open current module
    if (idx === currentModuleIdx) card.classList.add("open");

    container.appendChild(card);
  });
}

// ── RENDER QUESTS ─────────────────────────────────────────────────────────
function renderQuests(resp) {
  const quests    = resp.quests || [];
  const container = $("#questsList");
  container.innerHTML = "";

  const hdr = $("#questsHeader");
  hdr.innerHTML = "";

  const statDiv = el("div", "q-stat");
  const val = el("div", "q-stat-val", `${resp.completed_count || 0}/${resp.total_count || 0}`);
  const lbl = el("div", "q-stat-lbl", "протоколов завершено");
  statDiv.append(val, lbl);

  const modDiv = el("div", "q-stat");
  modDiv.style.marginLeft = "auto";
  const mval = el("div", "q-stat-val", `#${(resp.module_index ?? 0) + 1}`);
  const mlbl = el("div", "q-stat-lbl", resp.module_title || "");
  modDiv.append(mval, mlbl);
  hdr.append(statDiv, modDiv);

  // Update module subtitle
  const subEl = $("#moduleSubtitle");
  if (subEl) subEl.textContent = resp.module_subtitle || "";

  setProgress(resp.completed_count || 0, resp.total_count || 0);

  // Apply deadline info from quests response
  if (resp.deadline_info) {
    applyDeadlineInfo(resp.deadline_info);
  }

  if (resp.deadline_expired) {
    const expiredBanner = el("div", "deadline-expired-banner");
    expiredBanner.innerHTML = `
      <div class="deb-icon">🔴</div>
      <div class="deb-text">
        <strong>Дедлайн истёк</strong>
        <span>Модуль заблокирован — оплати штраф для продолжения</span>
      </div>
      <button class="deb-btn" onclick="showDeadlineExpiredScreen()">Разблокировать</button>
    `;
    container.appendChild(expiredBanner);
    return;
  }

  if (!quests.length) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="es-icon">⚔️</span>
        <div class="es-title">Нет активных протоколов</div>
        <p>Выполни все протоколы чтобы открыть следующий модуль</p>
      </div>`;
    return;
  }

  quests.forEach(q => {
    const isBoss = q.id.endsWith("_boss");
    const card   = el("div", `quest-card ${q.type}${isBoss ? " boss" : ""}${q.completed ? " completed" : ""}`);

    const iconWrap = el("div", `quest-type-icon ${q.type === "quiz" ? "quiz-icon" : isBoss ? "boss-icon" : "task-icon"}`);
    if (q.type === "quiz") {
      iconWrap.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="7" r="4" stroke="#00d4ff" stroke-width="1.5"/>
        <path d="M3 17C3 14.8 6.1 13 10 13C13.9 13 17 14.8 17 17" stroke="#00d4ff" stroke-width="1.5" stroke-linecap="round"/>
      </svg>`;
    } else if (isBoss) {
      iconWrap.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2L12.5 8H19L13.5 11.5L16 18L10 14.5L4 18L6.5 11.5L1 8H7.5Z" stroke="#fbbf24" stroke-width="1.5" stroke-linejoin="round" fill="rgba(251,191,36,0.15)"/>
      </svg>`;
    } else {
      iconWrap.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="4" y="3" width="12" height="14" rx="2" stroke="#a78bfa" stroke-width="1.5"/>
        <line x1="7" y1="7" x2="13" y2="7" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="7" y1="10" x2="13" y2="10" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>
        <line x1="7" y1="13" x2="10" y2="13" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
      </svg>`;
    }

    const headerRow  = el("div", "quest-header");
    const headerInfo = el("div", "quest-header-info");
    const title  = el("div", "quest-title", q.title);
    const xp     = el("div", "quest-xp", `+${q.xp_reward} XP`);
    headerInfo.append(title, xp);
    headerRow.append(iconWrap, headerInfo);

    const badges = el("div", "quest-badges");
    const typeBadge = el("div", `quest-type-badge quest-type-${isBoss ? "boss" : q.type}`,
      q.type === "quiz" ? "FIELD TEST" : isBoss ? "👑 APEX" : "ПРОТОКОЛ");
    badges.appendChild(typeBadge);

    const hw = state.userState?.homework_status;
    if (q.is_active && q.type === "task") {
      const statuses = {
        pending:  ["⏳ На проверке", "pending"],
        approved: ["✅ Принято",    "approved"],
        revision: ["🔄 На доработке","revision"],
        rejected: ["❌ Не принято", "rejected"],
      };
      const [txt, cls] = statuses[hw] || [];
      if (txt) badges.appendChild(el("div", `quest-status-badge status-${cls}`, txt));
    }

    const desc = el("div", "quest-desc", q.description || "");

    const canResubmit = q.is_active && q.type === "task" && (hw === "revision" || hw === "rejected");
    const btnLabel = q.completed
      ? "✓ Выполнено"
      : q.type === "quiz"
        ? "▶ ЗАПУСТИТЬ FIELD TEST"
        : canResubmit
          ? "🔄 Отправить повторно"
          : "📋 Открыть задание";
    const btn = el("button", "btn-quest", btnLabel);
    btn.disabled = q.completed && !canResubmit;
    btn.addEventListener("click", (e) => {
      if (q.type === "quiz") startQuiz(q.id, q.title, q.xp_reward, e.currentTarget);
      else openTask(q.id, q.title, q.xp_reward, q.description);
    });

    // Phantom hint button (not on boss cards)
    if (!isBoss) {
      const phantomBtn = el("button", "btn-phantom-hint", "👻 Послания призраков");
      phantomBtn.dataset.questId = q.id;
      phantomBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openPhantoms(q.id);
      });
      card.append(headerRow, badges, desc, phantomBtn, btn);
    } else {
      card.append(headerRow, badges, desc, btn);
    }
    container.appendChild(card);
  });
}

// ── RENDER LEADERBOARD ────────────────────────────────────────────────────
function renderLeaderboard(resp) {
  const list      = resp.leaderboard || [];
  const container = $("#leaderboardList");
  const podium    = $("#leaderboardPodium");
  container.innerHTML = "";
  if (podium) podium.innerHTML = "";

  if (!list.length) {
    container.innerHTML = `<div class="empty-state"><span class="es-icon">🏆</span><div class="es-title">Пока никого нет</div><p>Стань первым!</p></div>`;
    return;
  }

  // ── Podium for top-3 ──
  if (podium && list.length >= 1) {
    // order: 2nd (left) | 1st (center) | 3rd (right)
    const podiumOrder = [1, 0, 2]; // indices into list
    const barHeights  = [64, 48, 40]; // index 0=1st place, 1=2nd, 2=3rd
    const crowns      = ["👑", "", ""];
    const medals      = ["🥇", "🥈", "🥉"];

    podiumOrder.forEach((listIdx) => {
      const row = list[listIdx];
      if (!row) return;
      const place = listIdx + 1; // 1, 2, or 3
      const nameShort = (row.name || `User ${row.user_id}`).split(" ")[0].slice(0, 10);
      const initials  = nameShort.slice(0, 2).toUpperCase();

      const div = document.createElement("div");
      div.className = "podium-place";

      div.innerHTML = `
        <div class="podium-avatar">
          ${listIdx === 0 ? `<span class="podium-crown">👑</span>` : ""}
          ${initials}
        </div>
        <div class="podium-name">${nameShort}</div>
        <div class="podium-xp">${row.xp} XP</div>
        <div class="podium-bar">${medals[listIdx]}</div>
      `;
      podium.appendChild(div);
    });
  }

  // ── Full list (all entries, starting from rank 1) ──
  list.forEach((row, i) => {
    const item = el("div", "lb-item");
    const rank = el("div", "lb-rank", i < 3 ? ["🥇","🥈","🥉"][i] : `${i+1}`);
    const info = el("div", "lb-info");
    const name = el("div", "lb-name", row.name || `User ${row.user_id}`);
    const sub  = el("div", "lb-sub", `${row.rank || "Наблюдатель рынка"} · Модуль ${row.module || 1}`);
    const xp   = el("div", "lb-xp", `${row.xp} XP`);
    if (row.streak >= 3) xp.appendChild(el("span", "lb-streak", `🔥${row.streak}`));
    info.append(name, sub);
    item.append(rank, info, xp);
    if (row.user_id === state.userId) {
      item.style.borderColor = "rgba(201,168,76,0.30)";
      item.style.background  = "rgba(201,168,76,0.05)";
    }
    container.appendChild(item);
  });
}

// ── OPEN LESSON ───────────────────────────────────────────────────────────
async function openLesson(key) {
  try {
    const res  = await fetch(`${API}/lesson/${key}`);
    if (!res.ok) throw new Error("404");
    const data = await res.json();

    $("#lessonTitle").textContent = data.title;
    $("#lessonArticle").innerHTML = renderMarkdown(data.article || "");

    const videoEl = $("#lessonVideo");
    if (data.video) { videoEl.href = data.video; videoEl.style.display = "flex"; }
    else              { videoEl.style.display = "none"; }

    const loading = $(".chart-loading");
    const img     = $("#chartImg");
    loading.innerHTML = `<div class="spinner"></div><span>Генерирую график...</span>`;
    loading.style.display = "flex";
    img.style.display = "none";

    openModal("#lessonModal");

    const chartRes = await fetch(`${API}/chart/${key}`);
    if (chartRes.ok) {
      const chartData = await chartRes.json();
      img.onload = () => { loading.style.display = "none"; img.style.display = "block"; };
      img.onerror = () => { loading.innerHTML = "<span>График для этого урока недоступен</span>"; };
      img.src = `data:${chartData.mime};base64,${chartData.image_base64}`;
    } else {
      loading.innerHTML = "<span>График для этого урока недоступен</span>";
    }
  } catch (e) {
    console.error("openLesson:", e);
    showToast("Ошибка загрузки урока", "error");
  }
}
window.openLesson = openLesson;

// ── QUIZ ──────────────────────────────────────────────────────────────────
async function startQuiz(questId, questTitle, xpReward, btnEl) {
  try {
    const res  = await fetch(`${API}/quest/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, quest_id: questId }),
    });
    const data = await res.json();

    if (!data.ok) {
      if (data.error === "deadline_expired") {
        showDeadlineExpiredScreen();
        return;
      }
      showResult("⚠️", "Квиз недоступен", data.message || data.error, null);
      return;
    }

    const questions = data.quiz?.questions || [];
    if (!questions.length) { showToast("Нет вопросов для этого квиза", "error"); return; }

    state.quizData  = { questions, questId, xpReward, current: 0, correct: 0 };
    state.quizStreak = 0;
    renderQuizQuestion();
    openModal("#quizModal");
  } catch (e) {
    console.error("startQuiz:", e);
    showToast("Ошибка запуска квиза", "error");
  }
}

function updateStreakDisplay() {
  const el = $("#quizStreakNum");
  const wrap = $("#quizStreak");
  if (el) el.textContent = state.quizStreak;
  if (wrap) wrap.classList.toggle("hidden", state.quizStreak < 2);
}

function renderQuizQuestion() {
  const { questions, current } = state.quizData;
  const total = questions.length;
  const q     = questions[current];

  $("#quizProgressBar").style.width = Math.round(current / total * 100) + "%";
  $("#quizCounter").textContent = `${current + 1} / ${total}`;
  $("#quizQuestion").textContent = q.question;

  const fb = $("#quizFeedback");
  fb.className = "quiz-feedback hidden";
  fb.textContent = "";
  $("#quizNext").classList.add("hidden");

  updateStreakDisplay();

  const opts = $("#quizOptions");
  opts.innerHTML = "";
  q.options.forEach((opt, i) => {
    const btn = el("button", "quiz-option", opt);
    btn.addEventListener("click", () => onQuizAnswer(i, q.correct_index, btn));
    opts.appendChild(btn);
  });
}

async function onQuizAnswer(chosen, correctIdx, clickedBtn) {
  const { questions, questId, current } = state.quizData;
  const isCorrect = chosen === correctIdx;

  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred(isCorrect ? "success" : "error");

  document.querySelectorAll(".quiz-option").forEach((b, i) => {
    b.disabled = true;
    if (i === correctIdx) b.classList.add("correct");
    if (i === chosen && !isCorrect) b.classList.add("wrong");
  });

  if (isCorrect) {
    state.quizData.correct++;
    state.quizStreak++;
    updateStreakDisplay();
    floatXP(5, clickedBtn);
  } else {
    state.quizStreak = 0;
    updateStreakDisplay();
  }

  const fb = $("#quizFeedback");
  if (isCorrect) {
    fb.className = "quiz-feedback correct-fb";
    fb.textContent = state.quizStreak >= 3 ? `⚡ ${state.quizStreak} СЕРИЯ! ГИПОТЕЗА ПОДТВЕРЖДЕНА!` : "🧬 ГИПОТЕЗА ПОДТВЕРЖДЕНА";
  } else {
    fb.className = "quiz-feedback wrong-fb";
    fb.textContent = `⚠️ АНОМАЛИЯ ОБНАРУЖЕНА. Верный ответ: ${questions[current].options[correctIdx]}`;
  }

  try {
    const res = await fetch(`${API}/quiz/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, quest_id: questId, question_index: current, is_correct: isCorrect, session_token: state.sessionToken }),
    });
    const data = await res.json();

    if (data.finished) {
      setTimeout(() => { closeModal("#quizModal"); onQuizFinished(data); }, 1200);
      return;
    }
  } catch (e) { console.error("quiz answer:", e); }

  state.quizData.current++;
  if (state.quizData.current >= questions.length) { setTimeout(() => closeModal("#quizModal"), 1200); return; }

  const nextBtn = $("#quizNext");
  nextBtn.textContent = state.quizData.current >= questions.length - 1 ? "Завершить →" : "Следующий вопрос →";
  nextBtn.classList.remove("hidden");
}

function quizNextQuestion() { renderQuizQuestion(); }
window.quizNextQuestion = quizNextQuestion;
function abortQuiz() { state.quizData = null; closeModal("#quizModal"); }
window.abortQuiz = abortQuiz;

function onQuizFinished(data) {
  if (data.passed) {
    floatXP(data.xp_earned || 0, null);
    let msg = `Результат: ${data.correct}/${data.total} (${data.score}%)`;
    if (data.module_advanced) msg += "\n🎉 Новый модуль разблокирован!";
    showResult("🧬", "FIELD TEST ПРОЙДЕН!", msg, data.xp_earned);
    launchConfetti(80);
    if (data.leveled_up) {
      setTimeout(() => showLevelUp(data.new_level, data.rank), 1500);
    }
    loadQuests();
    refreshHeader();
    // Mystery Box after quest
    if (data.mystery_box_available && data.mystery_box_quest) {
      setTimeout(() => showMysteryBox(data.mystery_box_quest), 1800);
    }
    // Refresh homunculus stats after quiz completion
    setTimeout(() => {
      showToast("⚗️ Гомункул впитывает знания!", "success");
      loadHomunculus();
    }, 2200);
  } else {
    showResult("⚠️", "ГИПОТЕЗА НЕ ПОДТВЕРЖДЕНА", `Результат: ${data.correct}/${data.total} (${data.score}%)\nНужно набрать ${data.required}%`, null);
    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
    setTimeout(() => showToast("⚠️ Нужно пройти протокол заново", "error"), 1200);
  }
}

// ── PHOTO UPLOAD ───────────────────────────────────────────────────────────
let _hwPhotoBase64 = null;

// Compress via Canvas → JPEG. Uses createObjectURL to avoid loading
// the entire file into JS heap (prevents iOS WKWebView crash on large photos).
function compressAndSetPhoto(file) {
  const objectUrl = URL.createObjectURL(file);
  const tmpImg = new Image();

  tmpImg.onload = () => {
    const MAX = 900;
    let w = tmpImg.naturalWidth, h = tmpImg.naturalHeight;
    if (w > MAX || h > MAX) {
      if (w >= h) { h = Math.round(h * MAX / w); w = MAX; }
      else        { w = Math.round(w * MAX / h); h = MAX; }
    }
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(tmpImg, 0, 0, w, h);
    URL.revokeObjectURL(objectUrl); // free memory immediately
    _hwPhotoBase64 = canvas.toDataURL("image/jpeg", 0.82);

    const prevImg = $("#photoPreviewImg");
    if (prevImg) {
      prevImg.onload = () => {
        $("#photoPreviewWrap")?.classList.remove("hidden");
        $("#photoDropArea")?.classList.add("hidden");
      };
      prevImg.src = _hwPhotoBase64;
    }
  };

  tmpImg.onerror = () => {
    URL.revokeObjectURL(objectUrl);
    showToast("Не удалось прочитать фото. Попробуй сделать скриншот и загрузить его.", "error");
  };

  tmpImg.src = objectUrl;
}

function onPhotoSelected(input) {
  const file = input.files[0];
  if (!file) return;
  compressAndSetPhoto(file);
}

function removePhoto() {
  _hwPhotoBase64 = null;
  $("#photoPreviewWrap")?.classList.add("hidden");
  $("#photoDropArea")?.classList.remove("hidden");
  const input = $("#hwPhotoInput");
  if (input) input.value = "";
}

window.onPhotoSelected = onPhotoSelected;
window.removePhoto = removePhoto;

// ── TASK ──────────────────────────────────────────────────────────────────
function openTask(questId, title, xpReward, description) {
  state.currentQuestId = questId;
  _hwPhotoBase64 = null;

  $("#taskTitle").textContent = title;
  $("#taskXp").textContent    = `+${xpReward} XP`;
  $("#taskDesc").textContent  = description || "";

  // Reset status
  const statusEl = $("#taskStatus");
  statusEl.className = "task-status hidden";

  // Reset submit button
  const submitBtn = $("#taskSubmitBtn");
  submitBtn.disabled = false;
  submitBtn.textContent = "Отправить на проверку";
  submitBtn.classList.remove("hidden");

  // Reset photo upload
  removePhoto();
  const hwInput = $("#hwPhotoInput");
  if (hwInput) hwInput.value = "";

  // Reset checkboxes
  ["check1","check2","check3","check4"].forEach(id => {
    const cb = $(`#${id}`);
    if (cb) cb.checked = false;
  });

  // Show/hide teacher comment based on current homework status
  const hw = state.userState?.homework_status;
  const commentBlock = $("#teacherCommentBlock");
  const commentText  = $("#teacherCommentText");
  const hwComment    = state.userState?.homework_comment || "";

  if (commentBlock) {
    if ((hw === "revision" || hw === "rejected") && hwComment) {
      commentText.textContent = hwComment;
      commentBlock.classList.remove("hidden");
    } else {
      commentBlock.classList.add("hidden");
    }
  }

  // Show/hide upload section based on status
  const uploadSection = $("#taskPhotoUpload");
  const selfCheck     = $("#taskSelfCheck");
  if (hw === "pending") {
    // Already submitted, waiting
    if (uploadSection) uploadSection.classList.add("hidden");
    if (selfCheck)     selfCheck.classList.add("hidden");
    statusEl.className = "task-status pending";
    statusEl.textContent = "⏳ Ожидает проверки преподавателем";
    submitBtn.classList.add("hidden");
  } else if (hw === "approved") {
    if (uploadSection) uploadSection.classList.add("hidden");
    if (selfCheck)     selfCheck.classList.add("hidden");
    statusEl.className = "task-status approved";
    statusEl.textContent = "✅ Задание принято!";
    submitBtn.classList.add("hidden");
  } else {
    if (uploadSection) uploadSection.classList.remove("hidden");
    if (selfCheck)     selfCheck.classList.remove("hidden");
  }

  openModal("#taskModal");
}

// Open the send-preview confirmation modal
function submitCurrentTask() {
  if (!state.currentQuestId) return;

  const titleEl   = document.getElementById("sendPreviewTitle");
  const imgEl     = document.getElementById("sendPreviewImg");
  const noPhotoEl = document.getElementById("sendPreviewNoPhoto");
  const metaEl    = document.getElementById("sendPreviewMeta");
  const confirmBtn = document.getElementById("sendPreviewConfirmBtn");

  if (titleEl) titleEl.textContent = $("#taskTitle")?.textContent || "";

  if (_hwPhotoBase64) {
    if (imgEl)     { imgEl.src = _hwPhotoBase64; imgEl.classList.remove("hidden"); }
    if (noPhotoEl) noPhotoEl.classList.add("hidden");
    if (metaEl) {
      const kb = Math.round(_hwPhotoBase64.length * 0.75 / 1024);
      metaEl.textContent = `📎 Скриншот прикреплён · ${kb} KB`;
    }
  } else {
    if (imgEl)     { imgEl.src = ""; imgEl.classList.add("hidden"); }
    if (noPhotoEl) noPhotoEl.classList.remove("hidden");
    if (metaEl)    metaEl.textContent = "";
  }

  if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = "📤 Отправить"; }
  openModal("#sendPreviewModal");
}

function closeSendPreview() {
  closeModal("#sendPreviewModal");
}

let _isSubmitting = false;
async function doSubmitTask() {
  if (_isSubmitting) return;
  _isSubmitting = true;
  const confirmBtn = document.getElementById("sendPreviewConfirmBtn");
  if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = "⏳ Отправляю..."; }

  try {
    const body = {
      user_id:       state.userId,
      quest_id:      state.currentQuestId,
      session_token: state.sessionToken,
    };
    if (_hwPhotoBase64) body.photo = _hwPhotoBase64;

    const res  = await fetch(`${API}/quest/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    closeSendPreview();

    if (data.ok) {
      _isSubmitting = false;
      const statusEl = $("#taskStatus");
      statusEl.className = "task-status pending";
      statusEl.textContent = "⏳ Задание отправлено! Преподаватель проверит в течение 24 часов.";
      const submitBtn = $("#taskSubmitBtn");
      submitBtn.textContent = "✓ Отправлено";
      submitBtn.classList.add("hidden");
      $("#taskPhotoUpload")?.classList.add("hidden");
      $("#taskSelfCheck")?.classList.add("hidden");
      showToast("Задание отправлено на проверку!", "success");
      if (state.userState) state.userState.homework_status = "pending";
      loadQuests();
    } else if (data.error === "deadline_expired") {
      _isSubmitting = false;
      closeModal("#taskModal");
      showDeadlineExpiredScreen();
    } else {
      _isSubmitting = false;
      if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = "📤 Отправить"; }
      showToast(data.message || "Ошибка отправки", "error");
    }
  } catch (e) {
    _isSubmitting = false;
    console.error("doSubmitTask:", e);
    if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = "📤 Отправить"; }
    showToast("Ошибка сети", "error");
  }
}

window.submitCurrentTask = submitCurrentTask;
window.closeSendPreview   = closeSendPreview;
window.doSubmitTask       = doSubmitTask;

// ── RESULT MODAL ──────────────────────────────────────────────────────────
function showResult(emoji, title, text, xp) {
  $("#resultEmoji").textContent = emoji;
  $("#resultTitle").textContent = title;
  $("#resultText").textContent  = text;
  const xpEl = $("#resultXp");
  if (xp) { xpEl.textContent = `+${xp} MP`; xpEl.classList.remove("hidden"); }
  else      xpEl.classList.add("hidden");
  openModal("#resultModal");
}

function onResultClose() { closeModal("#resultModal"); }
window.onResultClose = onResultClose;

// ── CHART LIGHTBOX ────────────────────────────────────────────────────────
const cl = { scale: 1, panX: 0, panY: 0, startPanX: 0, startPanY: 0,
             startDist: 0, startScale: 1, lastTap: 0, dragging: false };

function openChartLightbox(src) {
  const lb  = document.getElementById("chartLightbox");
  const img = document.getElementById("clImg");
  if (!lb || !img || !src) return;
  img.src = src;
  cl.scale = 1; cl.panX = 0; cl.panY = 0;
  applyClTransform();
  lb.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeChartLightbox() {
  document.getElementById("chartLightbox")?.classList.add("hidden");
  document.body.style.overflow = "";
}

function applyClTransform() {
  const img = document.getElementById("clImg");
  if (img) img.style.transform = `translate(${cl.panX}px, ${cl.panY}px) scale(${cl.scale})`;
}

function initChartLightbox() {
  const vp = document.getElementById("clViewport");
  if (!vp) return;

  document.getElementById("clCloseBtn")?.addEventListener("click", closeChartLightbox);

  // Permanent click handler on chart preview image
  document.getElementById("chartImg")?.addEventListener("click", function () {
    if (this.src && !this.src.endsWith("#")) openChartLightbox(this.src);
  });

  vp.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      cl.startDist  = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                                 e.touches[0].clientY - e.touches[1].clientY);
      cl.startScale = cl.scale;
    } else if (e.touches.length === 1) {
      const now = Date.now();
      if (now - cl.lastTap < 280) {                // double-tap
        cl.scale = cl.scale > 1.05 ? 1 : 2.5;
        cl.panX  = 0; cl.panY = 0;
        applyClTransform();
        cl.lastTap = 0;
        return;
      }
      cl.lastTap   = now;
      cl.startPanX = e.touches[0].clientX - cl.panX;
      cl.startPanY = e.touches[0].clientY - cl.panY;
      cl.dragging  = true;
    }
  }, { passive: true });

  vp.addEventListener("touchmove", (e) => {
    e.preventDefault();
    if (e.touches.length === 2) {
      const dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                              e.touches[0].clientY - e.touches[1].clientY);
      cl.scale = Math.min(5, Math.max(1, cl.startScale * dist / cl.startDist));
      if (cl.scale <= 1) { cl.panX = 0; cl.panY = 0; }
      applyClTransform();
    } else if (e.touches.length === 1 && cl.dragging && cl.scale > 1.05) {
      cl.panX = e.touches[0].clientX - cl.startPanX;
      cl.panY = e.touches[0].clientY - cl.startPanY;
      applyClTransform();
    }
  }, { passive: false });

  vp.addEventListener("touchend", () => {
    cl.dragging = false;
    if (cl.scale <= 1) { cl.scale = 1; cl.panX = 0; cl.panY = 0; applyClTransform(); }
  });

  // Tap backdrop (un-zoomed state) → close
  vp.addEventListener("click", (e) => {
    if (e.target === vp && cl.scale <= 1.05) closeChartLightbox();
  });

  // Mouse wheel zoom (desktop)
  vp.addEventListener("wheel", (e) => {
    e.preventDefault();
    cl.scale = Math.min(5, Math.max(1, cl.scale + (e.deltaY > 0 ? -0.2 : 0.2)));
    if (cl.scale <= 1) { cl.panX = 0; cl.panY = 0; }
    applyClTransform();
  }, { passive: false });
}

// ── TOAST ─────────────────────────────────────────────────────────────────
function _getToastContainer() {
  let c = document.getElementById("_toastContainer");
  if (!c) {
    c = document.createElement("div");
    c.id = "_toastContainer";
    c.className = "toast-container";
    document.body.appendChild(c);
  }
  return c;
}

function showToast(msg, type = "info", icon = "", sub = "") {
  if (type === "success") playSound("xp"); else if (type === "error") playSound("err");
  const container = _getToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  if (icon) {
    const ic = document.createElement("span");
    ic.className = "toast-icon"; ic.textContent = icon;
    toast.appendChild(ic);
  }
  const txt = document.createElement("span");
  txt.textContent = msg;
  toast.appendChild(txt);
  if (sub) {
    const s = document.createElement("span");
    s.className = "toast-sub"; s.textContent = sub;
    toast.appendChild(s);
  }
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("removing");
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// ── DAILY BONUS DISPLAY ───────────────────────────────────────────────────
function showDailyBonus(xp, streak) {
  if (!xp) return;
  const textEl = $("#dailyBonusText");
  const streakEl = $("#dailyStreakDisplay");
  if (textEl) textEl.textContent = `+${xp} MP · ЕЖЕДНЕВНАЯ АКТИВАЦИЯ`;
  if (streakEl) {
    if (streak >= 2) {
      streakEl.innerHTML = `<div class="streak-info">⚡ СТРИК: <strong>${streak} дней</strong></div>`;
      if (streak === 7) streakEl.innerHTML += `<div class="streak-milestone">🏅 Бейдж «Неделя без пропусков» получен!</div>`;
      if (streak === 30) streakEl.innerHTML += `<div class="streak-milestone">🏆 Бейдж «Железная воля» получен!</div>`;
    }
  }
  setTimeout(() => openModal("#dailyBonusModal"), 800);
}

// ── API CALLS ─────────────────────────────────────────────────────────────
async function loadQuests() {
  if (!state.userId) { console.warn("quests fetch skipped: userId not set"); return; }
  try {
    const res  = await fetch(`${API}/quests/${state.userId}`);
    const data = await res.json();
    renderQuests(data);
  } catch (e) { console.error("loadQuests:", e); }
}

async function loadLeaderboard() {
  try {
    const res  = await fetch(`${API}/leaderboard?limit=20`);
    const data = await res.json();
    renderLeaderboard(data);
  } catch (e) { console.error("loadLeaderboard:", e); }
}

async function refreshHeader() {
  if (!state.userId) { console.warn("quests fetch skipped: userId not set"); return; }
  try {
    const res = await fetch(`${API}/user/${state.userId}`);
    const s   = await res.json();
    renderHeader(s);
  } catch (e) {}
}
window.showDeadlineExpiredScreen = showDeadlineExpiredScreen;

// ── FETCH WITH TIMEOUT ────────────────────────────────────────────────────
function fetchWithTimeout(url, options, timeoutMs = 20000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

// ── LOADING ERROR UI ──────────────────────────────────────────────────────
function showLoadingError(msg) {
  const el = $("#moduleName");
  if (el) el.textContent = "Ошибка загрузки";
  const progLabel = $("#progressLabel");
  if (progLabel) progLabel.textContent = msg || "Нет соединения с сервером";
  // Show retry button inside progress area
  const retryWrap = $("#retryWrap");
  if (retryWrap) {
    retryWrap.style.display = "flex";
  } else {
    const bar = $("#progressBar")?.parentElement;
    if (bar) {
      const btn = document.createElement("button");
      btn.id = "retryWrap";
      btn.className = "btn-primary";
      btn.style.cssText = "margin-top:12px;width:100%;font-size:14px;";
      btn.textContent = "Повторить";
      btn.onclick = () => { btn.style.display = "none"; init(); };
      bar.appendChild(btn);
    }
  }
}

// ══════════════════════════════════════════════════════════════════════
// ── ACTIONS POOL ─────────────────────────────────────────────────────

async function loadActionsPool() {
  if (!state.userId) return;
  try {
    const d = await fetch(`${API}/actions/${state.userId}`).then(r => r.json());
    state.actionsPool = d;
    renderActionsHUD(d);
  } catch(e) {}
}

function renderActionsHUD(d) {
  const el = document.getElementById("actionsHUD");
  if (!el) return;

  const left  = d.left ?? 0;
  const total = d.daily_total ?? 1;
  const chance = d.catalyst_chance_pct ?? 0;

  // Кружочки-действия (● = доступно, ○ = потрачено)
  const dots = Array.from({length: total}, (_, i) =>
    `<span class="action-dot ${i < left ? 'action-dot-ready' : 'action-dot-used'}"></span>`
  ).join('');

  el.innerHTML = `
    <div class="actions-dots">${dots}</div>
    <span id="actionsLeft" class="actions-label">${left}/${total}</span>
    ${chance > 0 ? `<div class="cat-chance-hint">⚗️ Катализатор: ${chance}%</div>` : ''}`;
}

// ── CATALYST UI ──────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════

async function loadCatalyst() {
  if (!state.userId) return;
  try {
    const [catR, myR] = await Promise.all([
      fetch(`${API}/catalyst/status`),
      fetch(`${API}/catalyst/my/${state.userId}`),
    ]);
    const [cat, my] = await Promise.all([catR.json(), myR.json()]);
    renderCatalyst(cat, my);
    // Показать/скрыть быструю кнопку в хедере
    const qaBtn = document.getElementById("qaCatalyst");
    if (qaBtn) qaBtn.style.display = cat.active ? "flex" : "none";
  } catch(e) { console.warn("catalyst:", e); }
}

function renderCatalyst(cat, my) {
  const wrap = document.getElementById("catalystWrap");
  if (!wrap) return;

  const isMe = cat.active && cat.user_id === state.userId;
  const iso = my?.isotopes ?? 0;
  const atkLeft = my?.attempts_left ?? 0;
  const atkMax = my?.max_attempts ?? 1;

  if (!cat.active) {
    const pool = state.actionsPool || {};
    const chance = pool.catalyst_chance_pct || 0;
    const hasActions = (pool.left || 0) > 0;
    const chanceCap = (state.userState?.level || 1) * 15;

    wrap.innerHTML = `
    <div class="cat-card cat-idle">
      <div class="cat-card-header">
        <span class="cat-icon">⚗️</span>
        <div class="cat-card-title-block">
          <span class="cat-card-title">КАТАЛИЗАТОР РАСПАДА</span>
          <span class="cat-card-subtitle">Система в равновесии</span>
        </div>
        <div class="cat-iso-chip ${iso > 0 ? 'cat-iso-has' : ''}"
          ${iso > 0 ? 'onclick="doActivateCatalyst()"' : ''}>
          🧪 ${iso > 0 ? `${iso} изотоп${iso > 1 ? 'а' : ''}` : 'Нет изотопов'}
        </div>
      </div>
      <div id="catRecordsZone"></div>
      <div class="cat-roll-section">
        <div class="cat-roll-chance">
          <span>⚗️ Твой шанс стать Катализатором</span>
          <span class="cat-roll-pct">${chance}%</span>
        </div>
        <div class="cat-roll-bar-bg">
          <div class="cat-roll-bar" style="width:${Math.min(100, chance / chanceCap * 100)}%"></div>
        </div>
        <button class="cat-roll-btn ${!hasActions ? 'cat-roll-disabled' : ''}"
          ${!hasActions ? 'disabled' : ''}
          onclick="doCatalystRoll()">
          ${hasActions
            ? `🎲 Бросить кости (+10% к шансу) — 1 действие`
            : `❌ Нет действий`}
        </button>
        <p class="cat-roll-hint">Шанс копится между днями. Максимум: ${chanceCap}%</p>
      </div>
      <div class="cat-hint">Получи Нестабильный Изотоп: победи Босса или войди в топ-3 ежедневного вызова</div>
    </div>`;
    _loadCatRecords();
    return;
  }

  const hpPct = cat.hp_pct || 0;
  const hpCol = hpPct > 60 ? '#00e87a' : hpPct > 25 ? '#f59e0b' : '#ff4d6d';
  const atkPct = atkMax > 0 ? Math.round(atkLeft / atkMax * 100) : 0;

  wrap.innerHTML = `
  <div class="cat-card cat-active-card ${isMe ? 'cat-is-me' : ''}">

    <div class="cat-active-top">
      <span class="cat-live-badge">⚗️ РЕАКЦИЯ АКТИВНА</span>
      <span class="cat-time-left">${cat.hours_left || 0}ч осталось</span>
    </div>

    <div class="cat-who ${isMe ? 'cat-who-me' : ''}">
      ${isMe ? '⚠️ ТЫ КАТАЛИЗАТОР' : `💀 ${cat.username || 'Неизвестный'}`}
    </div>

    <div class="cat-drain-line">
      <span>Дренаж: 0.01 ⚡/ч с онлайн-игроков</span>
      <span class="cat-drained-total">${(cat.total_drained || 0).toFixed(2)} собрано</span>
    </div>

    <div class="cat-hp-block">
      <div class="cat-hp-top">
        <span>HP Катализатора</span>
        <span style="color:${hpCol};font-weight:700">${cat.hp} / ${cat.max_hp}</span>
      </div>
      <div class="cat-hp-bg">
        <div class="cat-hp-fill" style="width:${hpPct}%;background:${hpCol}"></div>
      </div>
    </div>

    ${!isMe ? `
    <div class="cat-atk-block">
      <div class="cat-atk-top">
        <span>Твои попытки</span>
        <span class="${atkLeft > 0 ? 'cat-green' : 'cat-red'}">${atkLeft}/${atkMax} (${atkLeft > 0 ? 'есть' : 'исчерпаны'})</span>
      </div>
      <div class="cat-atk-bar-bg"><div class="cat-atk-bar" style="width:${atkPct}%"></div></div>
      <button class="cat-atk-btn ${atkLeft <= 0 ? 'cat-atk-disabled' : ''}"
        id="catAtkBtn" onclick="doAttackCatalyst()" ${atkLeft <= 0 ? 'disabled' : ''}>
        ${atkLeft > 0
          ? `⚡ НЕЙТРАЛИЗОВАТЬ (−${state.userState?.level || 1} HP)`
          : '❌ Нет попыток — восст. в 00:00 UTC'}
      </button>
      <p class="cat-atk-hint">Финальный удар → +30% буфера + Нестабильный Изотоп</p>
    </div>` : `
    <div class="cat-me-block">
      <div class="cat-me-row">
        <span>🔒 Гарантированно</span>
        <span class="cat-green">${(cat.drained_secure || 0).toFixed(3)} ⚡</span>
      </div>
      <div class="cat-me-row">
        <span>⚠️ Под риском (буфер)</span>
        <span style="color:#f59e0b">${(cat.drained_buffer || 0).toFixed(3)} ⚡</span>
      </div>
      <div class="cat-me-tip">Выживи 24ч → буфер × 1.5 + ачивка</div>
    </div>`}
  </div>`;
}

async function _loadCatRecords() {
  try {
    const d = await fetch(`${API}/catalyst/records`).then(r=>r.json());
    const z = document.getElementById("catRecordsZone");
    if (!z || !d.records?.length) return;
    const medals = ["🥇","🥈","🥉"];
    z.innerHTML = `<div class="cat-rec-title">Рекорды выживания</div>` +
      d.records.slice(0,3).map((r,i)=>`
        <div class="cat-rec-row">
          <span>${medals[i]}</span>
          <span class="cat-rec-name">${r.username}</span>
          <span class="cat-rec-time">${Math.floor(r.duration_minutes/60)}ч ${r.duration_minutes%60}м</span>
          <span class="cat-rec-soul">${r.drained_total}⚡</span>
        </div>`).join("");
  } catch(e) {}
}

async function doCatalystRoll() {
  if (!state.actionsPool?.left) {
    showToast("Нет действий", "error"); return;
  }
  try {
    const d = await fetch(`${API}/catalyst/roll`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId}),
    }).then(r => r.json());

    if (!d.ok) { showToast(d.message || "Нет действий", "error"); return; }

    playSound(d.became_catalyst ? "catalyst_on" : "tap");
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred(d.became_catalyst ? "heavy" : "light");
    showToast(d.message, d.became_catalyst ? "success" : "info");

    if (state.actionsPool) {
      state.actionsPool.left = d.actions_left;
      state.actionsPool.catalyst_chance_pct = d.chance_pct;
    }
    renderActionsHUD(state.actionsPool || {});
    if (d.became_catalyst) {
      setTimeout(loadCatalyst, 500);
    } else {
      loadCatalyst();
    }
  } catch(e) { showToast("Ошибка", "error"); }
}
window.doCatalystRoll = doCatalystRoll;

async function doActivateCatalyst() {
  const my = await fetch(`${API}/catalyst/my/${state.userId}`).then(r=>r.json());
  if (!my.isotopes) { showToast("Нужен Нестабильный Изотоп!", "error"); return; }
  if (!confirm("Использовать Нестабильный Изотоп?\n\nТы станешь Катализатором на 24ч.\nВсе игроки получат уведомление и смогут атаковать тебя.\n\nПродолжить?")) return;
  try {
    const d = await fetch(`${API}/catalyst/activate`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({user_id:state.userId})
    }).then(r=>r.json());
    if (d.ok) {
      playSound("catalyst_on");
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("warning");
      showToast(d.message,"warning");
      loadCatalyst();
    } else {
      showToast(d.message||d.error,"error");
    }
  } catch(e){ showToast("Ошибка","error"); }
}
window.doActivateCatalyst = doActivateCatalyst;

async function doAttackCatalyst() {
  const btn = document.getElementById("catAtkBtn");
  if (btn) btn.disabled = true;
  try {
    const d = await fetch(`${API}/catalyst/attack`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({user_id:state.userId})
    }).then(r=>r.json());
    if (d.ok) {
      playSound(d.slain ? "neutralized" : "hit");
      if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred(d.slain?"heavy":"medium");
      showToast(d.message, d.slain?"success":"info");
      if (d.slain) {
        const wrap = document.getElementById("catalystWrap");
        if (wrap) wrap.style.animation = "catExplode 0.7s ease forwards";
        setTimeout(()=>{ if(wrap) wrap.style.animation=""; loadCatalyst(); }, 800);
      } else {
        setTimeout(loadCatalyst, 400);
      }
    } else {
      showToast(d.message||"Нет попыток","error");
      if (btn) btn.disabled = false;
    }
  } catch(e){ showToast("Ошибка","error"); if(btn) btn.disabled=false; }
}
window.doAttackCatalyst = doAttackCatalyst;

// ── INITIAL LOAD ──────────────────────────────────────────────────────────
async function init() {
  console.log("[CHM] init() called, userId will be:", getUserInfo()?.id);
  const info = getUserInfo();
  state.userId = info.id;

  const sb = document.getElementById("soundBtn");
  if (sb) sb.textContent = _soundOn ? "🔊" : "🔇";

  // Immediate visual proof that new JS is running
  const _dbgLabel = $("#progressLabel");
  if (_dbgLabel) _dbgLabel.textContent = "v6 | запуск…";

  // Show a "slow start" hint after 4s if still waiting (cold start can take 30-60s)
  const slowTimer = setTimeout(() => {
    const el = $("#moduleName");
    if (el && el.textContent === "Загрузка...") {
      el.textContent = "Сервер запускается…";
    }
    const progLabel = $("#progressLabel");
    const t = progLabel?.textContent || "";
    if (progLabel && (t === "0/0 квестов" || t.startsWith("v6"))) {
      progLabel.textContent = "Ожидание ответа сервера (~30 сек)…";
    }
  }, 4000);

  try {
    let initData = {};
    try {
      if (_dbgLabel) _dbgLabel.textContent = "v6 | init…";
      const initRes = await fetchWithTimeout(`${API}/user/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: info.id,
          username: info.username,
          first_name: info.first_name,
          last_name: info.last_name,
          init_data: tg?.initData || "",
        }),
      }, 90000); // 90s — Render.com free tier cold start
      if (_dbgLabel) _dbgLabel.textContent = `v6 | init ${initRes.status}`;
      const parsed = await initRes.json();
      // Only use initData when the server confirmed success
      if (parsed.ok) {
        initData = parsed;
        // Store validated user_id (may differ from initDataUnsafe if spoofed)
        if (initData.user_id) state.userId = initData.user_id;
        // Store session token for subsequent authenticated requests
        if (initData.session_token) {
          state.sessionToken = initData.session_token;
          localStorage.setItem(`smc_session_${state.userId}`, initData.session_token);
        }
        // Show Synthesis Ritual onboarding only on confirmed success
        initOnboarding(initData.onboarding_complete || false);
      } else {
        console.warn("user/init non-ok:", parsed);
      }
    } catch (initErr) {
      // init endpoint timed out or failed — continue loading data anyway
      console.warn("user/init failed, continuing:", initErr);
      if (_dbgLabel) _dbgLabel.textContent = `v6 | init err: ${String(initErr?.message||initErr).slice(0,60)}`;
    }

    const userId = state.userId || DEV_UID;
    state.userId = userId;
    if (_dbgLabel) _dbgLabel.textContent = `v6 | загрузка данных uid=${userId}…`;
    const LOAD_TIMEOUT = 60000; // 60s to handle Render.com cold starts
    const [userRes, modulesRes, questsRes, metaRes, lbRes] = await Promise.all([
      fetchWithTimeout(`${API}/user/${userId}`, {}, LOAD_TIMEOUT),
      fetchWithTimeout(`${API}/modules`, {}, LOAD_TIMEOUT),
      fetchWithTimeout(`${API}/quests/${userId}`, {}, LOAD_TIMEOUT),
      fetchWithTimeout(`${API}/lessons/meta`, {}, LOAD_TIMEOUT),
      fetchWithTimeout(`${API}/leaderboard`, {}, LOAD_TIMEOUT),
    ]);

    // Check HTTP status before parsing JSON — error responses may be HTML
    for (const [res, name] of [[userRes, "user"], [modulesRes, "modules"], [questsRes, "quests"], [metaRes, "meta"], [lbRes, "leaderboard"]]) {
      if (!res.ok) throw new Error(`HTTP ${res.status} on /api/${name}`);
    }

    const [userData, modulesData, questsData, metaData, lbData] = await Promise.all([
      userRes.json(), modulesRes.json(), questsRes.json(), metaRes.json(), lbRes.json(),
    ]);

    clearTimeout(slowTimer);

    state.userState = userData; // set BEFORE any render* calls

    console.log("[DEBUG] userData:", userData);
    console.log("[DEBUG] modulesData:", modulesData);
    console.log("[DEBUG] questsData:", questsData);
    console.log("[DEBUG] metaData keys:", Object.keys(metaData || {}).length);

    Object.assign(state.lessonsMetaCache, metaData);

    renderHeader(userData);
    renderModules(modulesData.modules || []);
    renderQuests(questsData);
    renderLeaderboard(lbData);
    setProgress(questsData.completed_count || 0, questsData.total_count || 0);

    // Apply deadline info
    if (questsData.deadline_info) {
      applyDeadlineInfo(questsData.deadline_info);
    }

    // Show daily bonus if applicable
    if (initData.daily_bonus_xp > 0) {
      showDailyBonus(initData.daily_bonus_xp, initData.streak);
    }

    // Evolution badge from init response (only show when user actually evolved)
    if (initData.evolution?.evolved) showToast(`⚗️ Эволюция! ${initData.evolution.info?.name || "Новая стадия"}`, "info");

    // ── SOULS SYSTEM: update HUD from init response ─────────────────────
    if (initData.souls_state) {
      updateSoulsHUD(initData.souls_state);
      // Check hollow status
      if (initData.hollow) {
        applyHollowState(initData.hollow);
      }
      // Show daily souls bonus
      if (initData.daily_souls_bonus > 0) {
        spawnSoulParticle(`+${initData.daily_souls_bonus} ⚡`, true);
      }
      // Show dropped souls banner if any
      if (initData.souls_state.dropped_souls > 0 && initData.souls_state.can_retrieve) {
        showDroppedSoulsBanner(initData.souls_state.dropped_souls);
      }
    }

    // Apply cached market pulse to heartbeat bar if already available
    if (initData.market_pulse?.pet_mood) _applyMarketMood(initData.market_pulse);

    // Start live heartbeat canvas + polling
    startMarketPulse();

    // Check for dream (after a short delay so UI is settled)
    setTimeout(checkDream, 2000);

    // Phase 3: check daily challenge badge
    setTimeout(_checkDailyBadge, 1500);

    // Catalyst (prevent duplicate intervals on init() retry)
    loadCatalyst();
    if (state._catalystInterval) clearInterval(state._catalystInterval);
    state._catalystInterval = setInterval(loadCatalyst, 90000); // каждые 1.5 минуты
    loadActionsPool();
    if (state._actionsInterval) clearInterval(state._actionsInterval);
    state._actionsInterval = setInterval(loadActionsPool, 30000); // каждые 30 сек

    // Live Signal
    checkLiveSignal();
    if (state._liveSignalInterval) clearInterval(state._liveSignalInterval);
    state._liveSignalInterval = setInterval(checkLiveSignal, 120000);

    // Raid
    loadRaid();

    console.log("[CHM] init complete. userId=", state.userId, "modules=", modulesData?.modules?.length);

  } catch (e) {
    clearTimeout(slowTimer);
    console.error("init error:", e);
    const isTimeout = e?.name === "AbortError";
    const isHttp    = e?.message?.startsWith("HTTP ");
    let msg;
    // Show raw error in progress label for debugging
    {
      const progLabel = document.getElementById("progressLabel");
      if (progLabel) progLabel.textContent = `v6 ERR: ${String(e?.message || e).slice(0, 100)}`;
    }
    if (isTimeout) msg = "Сервер не отвечает. Нажми «Повторить» через 30 сек.";
    else if (isHttp) msg = `Ошибка сервера (${e.message}). Попробуй ещё раз.`;
    else msg = "Ошибка загрузки данных. Попробуй ещё раз.";
    showLoadingError(msg);
  }
}

// ── HOMUNCULUS SYSTEM ────────────────────────────────────────────────────────

let _homTapBatch    = 0;
let _homMaxCombo    = 0;
let _homBatchTimer  = null;
let _homComboTimer  = null;
let _homLastTapTime = 0;
let _homComboCount  = 0;

async function loadHomunculus() {
  if (!state.userId) return;
  try {
    const res  = await fetch(`${API}/homunculus/${state.userId}`);
    const data = await res.json();
    if (data.ok !== false) renderHomunculus(data);
  } catch (e) { console.error("loadHomunculus:", e); }
}

function renderHomunculus(data) {
  const stage  = data.stage || 1;
  const status = data.status || "active";

  const stageBadge = document.getElementById("homStageBadge");
  if (stageBadge) stageBadge.textContent = `СТ.${stage}`;

  const stageName = document.getElementById("homStageName");
  if (stageName) stageName.textContent = data.stage_name || "Реагент";

  const statusBadge = document.getElementById("homStatusBadge");
  if (statusBadge) {
    const statusMap = { active:"Активен", hungry:"Голоден", dying:"Умирает", dead:"Мёртв", enraged:"Ярость!" };
    statusBadge.textContent = statusMap[status] || status;
    statusBadge.className   = `hom-status-badge hom-status--${status}`;
  }

  // Show correct stage SVG
  for (let i = 1; i <= 7; i++) {
    const svg = document.getElementById(`homSvg${i}`);
    if (svg) svg.style.display = (i === stage) ? "" : "none";
  }

  const deadOverlay = document.getElementById("homDeadOverlay");
  if (deadOverlay) deadOverlay.style.display = status === "dead" ? "flex" : "none";

  const creature = document.getElementById("homCreature");
  if (creature) {
    creature.className = "hom-creature";
    if (status === "enraged") creature.classList.add("hom-creature--enraged");
    else if (status === "dying")  creature.classList.add("hom-creature--dying");
    else if (status === "hungry") creature.classList.add("hom-creature--hungry");
    else if (status === "dead")   creature.classList.add("hom-creature--dead");
  }

  const aura = document.getElementById("homAura");
  if (aura) {
    const auraColors = { active:"#a855f7", hungry:"#f59e0b", dying:"#ef4444", dead:"#6b7280", enraged:"#dc2626" };
    aura.style.background = `radial-gradient(circle, ${(auraColors[status]||"#a855f7")}30 0%, transparent 70%)`;
  }

  const enrageNotice = document.getElementById("homEnrageNotice");
  if (enrageNotice) enrageNotice.style.display = status === "enraged" ? "block" : "none";

  const reviveSection = document.getElementById("homReviveSection");
  if (reviveSection) reviveSection.style.display = status === "dead" ? "block" : "none";

  const multVal = document.getElementById("homMultVal");
  if (multVal) multVal.textContent = `×${(data.total_mult || 1).toFixed(1)}`;

  const tapsVal = document.getElementById("homTapsVal");
  if (tapsVal) tapsVal.textContent = data.taps_today || 0;

  const comboMaxVal = document.getElementById("homComboMaxVal");
  if (comboMaxVal) comboMaxVal.textContent = data.combo_best || 0;

  const soulsFed = document.getElementById("homSoulsFed");
  if (soulsFed) soulsFed.textContent = data.souls_fed || 0;

  const soulsReq   = document.getElementById("homSoulsReq");
  const evoBar     = document.getElementById("homEvoBar");
  const moduleNote = document.getElementById("homModuleNote");

  if (data.next_stage) {
    const req = data.next_stage.souls_req || 0;
    if (soulsReq) soulsReq.textContent = req;
    if (evoBar) evoBar.style.width = (req > 0 ? Math.min(100, ((data.souls_fed||0)/req)*100) : 100) + "%";
    if (moduleNote && data.next_stage.modules_req != null) {
      const curMod = data.module_index || 0;
      const reqMod = data.next_stage.modules_req;
      moduleNote.textContent = curMod >= reqMod
        ? "✅ Модулей достаточно"
        : `📚 Нужно пройти ещё ${reqMod - curMod} модул(ей)`;
    }
  } else {
    if (soulsReq) soulsReq.textContent = "MAX";
    if (evoBar) evoBar.style.width = "100%";
    if (moduleNote) moduleNote.textContent = "🏆 Максимальная стадия!";
  }
}

let _tapInProgress = false;

async function onHomunculusTap(e) {
  if (!state.userId || _tapInProgress) return;

  // Проверяем есть ли действия локально (без запроса)
  if (state.actionsPool && state.actionsPool.left <= 0) {
    _showNoActions();
    return;
  }

  _tapInProgress = true;

  // Combo tracking
  const now = Date.now();
  if (now - _homLastTapTime < 300) {
    _homComboCount++;
  } else {
    _homComboCount = 1;
  }
  _homLastTapTime = now;
  _updateHomComboBar(_homComboCount);

  // Анимация
  const creature = document.getElementById("homCreature");
  if (creature) {
    creature.classList.remove("hom-squish");
    void creature.offsetWidth;
    creature.classList.add("hom-squish");
    setTimeout(() => creature.classList.remove("hom-squish"), 200);
  }
  _spawnHomFloat(e, "✦");
  playSound("tap");
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");

  // Немедленный запрос (не батч!)
  try {
    const res = await fetch(`${API}/homunculus/tap`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        user_id: state.userId, tap_count: 1, max_combo: _homComboCount,
        session_token: state.sessionToken
      }),
    });
    const data = await res.json();

    if (data.error === "no_actions") {
      _showNoActions(data.message);
      _tapInProgress = false;
      return;
    }

    if (data.ok !== false) {
      if (data.souls_earned != null) {
        state.souls = (state.souls || 0) + data.souls_earned;
        _updateSoulsDisplay(state.souls);
        if (data.souls_earned > 0) {
          _spawnHomFloat(e, `+${data.souls_earned.toFixed ? data.souls_earned.toFixed(2) : data.souls_earned}`);
          playSound("soulsgain");
        }
      }
      // Обновить пул действий
      if (data.actions_left != null) {
        if (!state.actionsPool) state.actionsPool = {};
        state.actionsPool.left = data.actions_left;
        state.actionsPool.daily_total = data.actions_total;
        renderActionsHUD(state.actionsPool);
      }
      renderHomunculus(data);
      if (data.evolved) {
        playSound("evolution");
        _triggerHomunculusEvolution(data.stage, data.stage_name);
      }
    } else {
      console.warn("hom tap:", data.error);
    }
  } catch(err) {
    console.error("tap error:", err);
  }

  _tapInProgress = false;
}
window.onHomunculusTap = onHomunculusTap;

function _showNoActions(msg) {
  showToast(msg || "Действий не осталось. Сброс в 00:00 UTC.", "info");
  const timer = document.getElementById("actionsResetTimer");
  if (timer) {
    timer.style.display = "block";
    const now = new Date();
    const midnight = new Date();
    midnight.setUTCHours(24, 0, 0, 0);
    const h = Math.floor((midnight - now) / 3600000);
    const m = Math.floor(((midnight - now) % 3600000) / 60000);
    timer.textContent = `⏰ Новые действия через ${h}ч ${m}м`;
  }
}

function _updateHomComboBar(combo) {
  const bar   = document.getElementById("homComboBar");
  const label = document.getElementById("homComboLabel");
  const badge = document.getElementById("homCombo");
  const text  = document.getElementById("homComboText");

  if (bar)   bar.style.width = Math.min(100, (combo / 100) * 100) + "%";
  if (label) label.textContent = `Комбо: ${combo}`;

  const threshold = combo >= 100 ? 100 : combo >= 50 ? 50 : combo >= 25 ? 25 : combo >= 10 ? 10 : 0;
  if (threshold >= 100) playSound("combo100"); else if (threshold >= 50) playSound("combo50"); else if (threshold >= 10) playSound("combo10");
  if (threshold > 0 && badge && text) {
    text.textContent = `×${threshold} COMBO!`;
    badge.style.display = "block";
    clearTimeout(_homComboTimer);
    _homComboTimer = setTimeout(() => { if (badge) badge.style.display = "none"; }, 1500);
  }
}

function _spawnHomFloat(e, text) {
  const wrap = document.getElementById("homFloatRewards");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = "hom-float-reward";
  el.textContent = text;
  if (e && e.clientX) {
    const rect = wrap.getBoundingClientRect();
    el.style.left = (e.clientX - rect.left) + "px";
    el.style.top  = (e.clientY - rect.top) + "px";
  } else {
    el.style.left = "50%";
    el.style.top  = "40%";
  }
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 900);
}

function _triggerHomunculusEvolution(stage, stageName) {
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  showToast(`⚗️ Гомункул эволюционировал! ${stageName} (Ст.${stage})`, "success");
  const flash = document.createElement("div");
  flash.className = "hom-evolution-flash";
  document.body.appendChild(flash);
  setTimeout(() => flash.remove(), 900);
}

async function homunculusRevive() {
  if (!state.userId) return;
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("heavy");
  try {
    const res  = await fetch(`${API}/homunculus/revive`, {
      method:  "POST",
      headers: {"Content-Type": "application/json"},
      body:    JSON.stringify({user_id: state.userId}),
    });
    const data = await res.json();
    if (data.ok === false) { showToast(data.error || "Недостаточно душ", "error"); return; }
    showToast("⚗️ Гомункул возрождён!", "success");
    renderHomunculus(data);
  } catch(e) { console.error("homunculusRevive:", e); }
}
window.homunculusRevive = homunculusRevive;


// ═══════════════════════════════════════════════════════════════════════════
// ── FEVER / FRENZY TAP SYSTEM ─────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════

const _tapTs = [];
let _feverActive  = false;
let _frenzyActive = false;
let _feverTimer   = null;
let _frenzyTimer  = null;
let _frenzyRaf    = null;

function _tapComboColor(combo) {
  if (combo >= 10) return "rainbow";
  if (combo >= 5)  return "#ef4444";
  if (combo >= 3)  return "#f97316";
  if (combo >= 2)  return "#fbbf24";
  return "#fff";
}

function _spawnTapRipple(e, stageEl) {
  if (!e || !stageEl) return;
  const rect = stageEl.getBoundingClientRect();
  const el = document.createElement("div");
  el.className = "tap-ripple";
  el.style.left   = (e.clientX - rect.left) + "px";
  el.style.top    = (e.clientY - rect.top)  + "px";
  el.style.width  = "48px";
  el.style.height = "48px";
  stageEl.appendChild(el);
  setTimeout(() => el.remove(), 540);
}

function _spawnScreenFlash() {
  const el = document.createElement("div");
  el.className = "screen-flash";
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 130);
}

function _trackTapVelocity() {
  const now = Date.now();
  _tapTs.push(now);
  while (_tapTs.length && now - _tapTs[0] > 3000) _tapTs.shift();
  const tap2s = _tapTs.filter(t => now - t <= 2000).length;
  const tap3s = _tapTs.length;
  if (tap3s >= 10 && !_frenzyActive) _enterFrenzy();
  else if (tap2s >= 5 && !_feverActive && !_frenzyActive) _enterFever();
  if (_feverActive) _updateFeverCounter(tap2s);
}

function _enterFever() {
  if (_feverActive) return;
  _feverActive = true;
  document.body.classList.add("fever-mode");
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
  showToast("⚡ RESONANCE MODE! Активируй Cipher быстрее!", "success");
  const fc = document.createElement("div");
  fc.className = "fever-counter"; fc.id = "feverCounter"; fc.textContent = "5";
  document.body.appendChild(fc);
  clearTimeout(_feverTimer);
  _feverTimer = setTimeout(_exitFever, 5000);
}

function _exitFever() {
  _feverActive = false;
  document.body.classList.remove("fever-mode");
  document.getElementById("feverCounter")?.remove();
}

function _enterFrenzy() {
  if (_frenzyActive) return;
  _exitFever();
  _frenzyActive = true;
  document.body.classList.add("frenzy-mode");
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  showToast("CRITICAL RESONANCE! x10 DATA — 8 сек", "success", "💠");
  const banner = document.createElement("div");
  banner.className = "frenzy-banner"; banner.id = "frenzyBanner";
  banner.textContent = "💠 CRITICAL RESONANCE — x10 DATA 💠";
  document.body.appendChild(banner);
  _startCoinRain();
  clearTimeout(_frenzyTimer);
  _frenzyTimer = setTimeout(_exitFrenzy, 8000);
}

function _exitFrenzy() {
  _frenzyActive = false;
  document.body.classList.remove("frenzy-mode");
  document.getElementById("frenzyBanner")?.remove();
  _stopCoinRain();
}

function _updateFeverCounter(n) {
  const el = document.getElementById("feverCounter");
  if (!el) return;
  el.textContent = `x${n}`;
  el.style.animation = "none"; void el.offsetWidth;
  el.style.animation = "counterPop 0.2s ease-out";
}

function _startCoinRain() {
  const cv = document.createElement("canvas");
  cv.className = "frenzy-rain-canvas"; cv.id = "frenzyCanvas";
  cv.width = window.innerWidth; cv.height = window.innerHeight;
  document.body.appendChild(cv);
  const ctx = cv.getContext("2d");
  const coins = Array.from({length: 28}, () => ({
    x: Math.random() * cv.width, y: -40 - Math.random() * 200,
    spd: 2 + Math.random() * 3, rot: Math.random() * 360,
    rs: (Math.random() - 0.5) * 8, sz: 14 + Math.random() * 10,
  }));
  function draw() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    coins.forEach(c => {
      c.y += c.spd; c.rot += c.rs;
      if (c.y > cv.height + 30) { c.y = -20; c.x = Math.random() * cv.width; }
      ctx.save();
      ctx.translate(c.x, c.y); ctx.rotate(c.rot * Math.PI / 180);
      ctx.font = `${c.sz}px serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("🪙", 0, 0);
      ctx.restore();
    });
    _frenzyRaf = requestAnimationFrame(draw);
  }
  draw();
}

function _stopCoinRain() {
  if (_frenzyRaf) cancelAnimationFrame(_frenzyRaf);
  document.getElementById("frenzyCanvas")?.remove();
}

// Hook fever/frenzy + ripple + flash into existing onHomunculusTap
const _origOnHomunculusTap = onHomunculusTap;
window.onHomunculusTap = function(e) {
  _trackTapVelocity();
  _spawnTapRipple(e, document.getElementById("homCreatureWrap"));
  _spawnScreenFlash();
  _origOnHomunculusTap(e);
};

// Override float reward to use combo color
function _spawnFloatRewardColored(text, px, py, combo) {
  const container = document.getElementById("homFloatRewards");
  if (!container) return;
  const el = document.createElement("div");
  const color = _tapComboColor(combo || 1);
  const isRainbow = color === "rainbow";
  el.className = "float-reward" + (combo >= 3 ? " float-reward--combo" : "");
  el.textContent = text;
  el.style.left = (px - 10) + "%";
  el.style.top  = py + "%";
  if (!isRainbow) el.style.color = color;
  else el.style.background = "linear-gradient(90deg,#ff3366,#ff8c42,#fbbf24,#10b981,#a855f7)";
  if (isRainbow) { el.style.webkitBackgroundClip = "text"; el.style.webkitTextFillColor = "transparent"; }
  container.appendChild(el);
  setTimeout(() => el.remove(), 950);
}

// ═══════════════════════════════════════════════════════════════════════════
// ── MARKET HEARTBEAT (Live BTC pulse canvas) ──────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════

let _pulsePoints     = [];
let _pulseSpeed      = 1.0;
let _pulseRaf        = null;
let _pulseOffset     = 0;
let _lastPulseFetch  = 0;

function startMarketPulse() {
  _fetchMarketPulse();
  setInterval(_fetchMarketPulse, 30_000);
  _drawHeartbeat();
}

async function _fetchMarketPulse() {
  const now = Date.now();
  if (now - _lastPulseFetch < 25_000) return;
  _lastPulseFetch = now;
  try {
    const res  = await fetch(`${API}/market/pulse`);
    const data = await res.json();
    if (!data.pet_mood) return;
    _applyMarketMood(data);
  } catch (e) { console.warn("pulse fetch:", e); }
}

function _applyMarketMood(data) {
  const mood = data.pet_mood || {};
  // Pulse speed (volatility → speed)
  _pulseSpeed = mood.pulse_speed || 1.0;
  // Update homunculus aura color based on market if tab active
  if (document.getElementById("tab-homunculus")?.classList.contains("active")) {
    const aura = document.getElementById("homAura");
    if (aura && mood.aura) {
      aura.style.background = `radial-gradient(circle, ${mood.aura}30 0%, transparent 70%)`;
    }
  }
}

function _drawHeartbeat() {
  const canvas = document.getElementById("hbCanvas");
  if (!canvas) { _pulseRaf = requestAnimationFrame(_drawHeartbeat); return; }
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const mid = H / 2;
  const speed = _pulseSpeed;

  // Generate ECG-like wave points on demand
  function _ecgY(x) {
    // Combines a sine base with a sharp spike every ~80px (the "heartbeat")
    const phase = (x + _pulseOffset * speed * 80) % 80;
    let y = Math.sin(x * 0.08 + _pulseOffset * speed) * 4;  // baseline wobble
    if (phase < 20) {
      // Sharp ECG spike shape
      if (phase < 5)       y += phase * 2.5;
      else if (phase < 8)  y += (8 - phase) * 8;
      else if (phase < 12) y += (phase - 8) * 6;
      else if (phase < 16) y -= (phase - 12) * 3;
      else                 y -= (16 - phase) * 0.5;
    }
    return mid - y * (3 + speed * 2);
  }

  ctx.clearRect(0, 0, W, H);

  // Glow
  const grad = ctx.createLinearGradient(0, 0, W, 0);
  grad.addColorStop(0,   "rgba(168,85,247,0)");
  grad.addColorStop(0.3, "rgba(168,85,247,0.6)");
  grad.addColorStop(0.7, "rgba(255,140,66,0.8)");
  grad.addColorStop(1,   "rgba(255,140,66,0)");
  ctx.strokeStyle = grad;
  ctx.lineWidth = 2;
  ctx.shadowColor = "#a855f7";
  ctx.shadowBlur  = 6;

  ctx.beginPath();
  for (let x = 0; x < W; x++) {
    const y = _ecgY(x);
    x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.stroke();

  _pulseOffset += 0.012;
  _pulseRaf = requestAnimationFrame(_drawHeartbeat);
}

// ═══════════════════════════════════════════════════════════════════════════
// ── ORACLE SYSTEM ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════

let _oracleData = null;

async function showOracle() {
  if (!state.userId) return;
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
  openModal("oracleModal");

  // Animate eye opening
  const eyeEl = document.getElementById("oracleEyeLarge");
  if (eyeEl) {
    eyeEl.style.animation = "none"; void eyeEl.offsetWidth;
    eyeEl.style.animation = "oracleReveal 1.2s cubic-bezier(0.34,1.56,0.64,1) forwards";
  }

  if (!_oracleData) {
    try {
      const res = await fetch(`${API}/oracle/daily?user_id=${state.userId}`);
      _oracleData = await res.json();
    } catch (e) {
      document.getElementById("oracleText").innerHTML =
        "<div class='oracle-loading'>Оракул временно недоступен...</div>";
      return;
    }
  }

  const d = _oracleData;

  // Prophecy text (new field with legacy fallback)
  const textEl = document.getElementById("oracleText");
  if (textEl) textEl.innerHTML = `«${d.prophecy || d.text || "Рынок молчит..."}»`;

  // Sentiment badge
  const badge = document.getElementById("oracleConceptBadge");
  if (badge) {
    const sentMap = {
      bullish: "🟢 Бычий сигнал",
      bearish: "🔴 Медвежий сигнал",
      neutral: "⚪ Нейтральный рынок",
    };
    badge.textContent = sentMap[d.sentiment] || (d.concept ? `📊 ${d.concept}` : "🧬 SMC");
    badge.className = `oracle-concept-badge oracle-sentiment--${d.sentiment || "neutral"}`;
  }

  // Price + 24h change line
  const priceEl = document.getElementById("oraclePriceLine");
  if (priceEl) {
    const p = d.price || d.btc_price;
    const ch = d.change_24h || "";
    if (p) priceEl.textContent = `BTC/USDT $${p.toLocaleString("en-US")}  ${ch}  · 4H SMC`;
  }

  // Inline concept quiz
  const qEl = document.getElementById("oracleQuestion");
  if (qEl && d.concept) {
    const qData = _getOracleQuiz(d.concept);
    if (qData) {
      document.getElementById("oracleQText").textContent = qData.q;
      const choicesEl = document.getElementById("oracleQChoices");
      choicesEl.innerHTML = "";
      qData.choices.forEach((c, i) => {
        const btn = document.createElement("button");
        btn.className = "oracle-choice";
        btn.textContent = c;
        btn.onclick = () => _onOracleAnswer(i, qData.correct, btn, choicesEl);
        choicesEl.appendChild(btn);
      });
      qEl.classList.remove("hidden");
    }
  }
}
window.showOracle = showOracle;

function _getOracleQuiz(concept) {
  const quizzes = {
    "FVG": {
      q: "Что произойдёт с FVG со временем по SMC?",
      choices: ["Цена вернётся заполнить дисбаланс", "FVG усилится", "Уровень исчезнет", "Цена пробьёт уровень и не вернётся"],
      correct: 0,
    },
    "OB": {
      q: "Когда ордер-блок теряет силу?",
      choices: ["Когда цена торгуется внутри него и закрывается выше/ниже", "Через 24 часа", "После 3 касаний", "OB всегда остаётся валидным"],
      correct: 0,
    },
    "Ликвидность": {
      q: "Для чего Smart Money нужна ликвидность розничных стопов?",
      choices: ["Для исполнения крупных ордеров по лучшей цене", "Для создания тренда", "Для манипуляции индикаторами", "Для снижения волатильности"],
      correct: 0,
    },
  };
  return quizzes[concept] || null;
}

async function _onOracleAnswer(idx, correct, btn, container) {
  const btns = container.querySelectorAll(".oracle-choice");
  btns.forEach(b => b.disabled = true);
  const isCorrect = idx === correct;
  btn.classList.add(isCorrect ? "correct" : "wrong");
  btns[correct].classList.add("correct");

  if (tg?.HapticFeedback) {
    tg.HapticFeedback.notificationOccurred(isCorrect ? "success" : "error");
  }

  try {
    const res  = await fetch(`${API}/oracle/answer`, {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, correct: isCorrect}),
    });
    const data = await res.json();
    if (isCorrect) {
      showToast(`✅ Верно! +25 Ð DATA! Oracle: ${data.oracle_correct}/5`, "success");
      _spawnCoinBurst(5);
      if (data.evolution?.evolved) {
        setTimeout(() => _showEvolutionModal(data.evolution), 1500);
      }
    } else {
      showToast("❌ Неверно. Изучи материал и попробуй снова.", "error");
    }
  } catch (e) { console.error("oracle answer:", e); }
}

// ═══════════════════════════════════════════════════════════════════════════
// ── DREAM SYSTEM ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════

async function checkDream() {
  if (!state.userId) return;
  try {
    const res  = await fetch(`${API}/pet/dream/${state.userId}`);
    const data = await res.json();
    if (data.ok && data.has_dream) {
      setTimeout(() => _showDreamModal(data), 1200);
    }
  } catch (e) { console.warn("dream check:", e); }
}

function _showDreamModal(data) {
  const d = data.dream;
  document.getElementById("dreamSetup").textContent = d.setup;
  document.getElementById("dreamOfflineText").textContent =
    `Cipher анализировал рынок ${data.offline_hours} ч. без тебя. Тема: ${data.concept_meta?.name || data.concept}`;
  document.getElementById("dreamQuestion").textContent = d.question;

  const choicesEl = document.getElementById("dreamChoices");
  choicesEl.innerHTML = "";
  d.choices.forEach((c, i) => {
    const btn = document.createElement("button");
    btn.className = "dream-choice";
    btn.textContent = c;
    btn.onclick = () => _onDreamAnswer(i, d.correct, btn, choicesEl, data);
    choicesEl.appendChild(btn);
  });

  document.getElementById("dreamResult").classList.add("hidden");
  document.getElementById("dreamResult").innerHTML = "";
  openModal("dreamModal");
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

async function _onDreamAnswer(idx, correct, btn, container, data) {
  const btns = container.querySelectorAll(".dream-choice");
  btns.forEach(b => b.disabled = true);
  const isCorrect = idx === correct;
  btn.classList.add(isCorrect ? "correct" : "wrong");
  btns[correct].classList.add("correct");

  if (tg?.HapticFeedback) {
    tg.HapticFeedback.notificationOccurred(isCorrect ? "success" : "error");
  }

  const resEl = document.getElementById("dreamResult");
  resEl.classList.remove("hidden");

  try {
    const res = await fetch(`${API}/pet/dream/answer`, {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, correct: isCorrect, concept: data.concept}),
    });
    const r = await res.json();
    if (isCorrect) {
      resEl.innerHTML = `✅ <strong>ГИПОТЕЗА ПОДТВЕРЖДЕНА!</strong> Гомункул пробуждается!`;
      // Refresh homunculus stats
      setTimeout(loadHomunculus, 800);
    } else {
      const meta = data.concept_meta || {};
      resEl.innerHTML = `❌ <strong>АНОМАЛИЯ ОБНАРУЖЕНА.</strong> Изучи протокол "${meta.name || data.concept}" для рекалибровки.<br>
        <button class="btn-primary" style="margin-top:10px;font-size:12px" onclick="closeModal('dreamModal');switchTab('lessons')">
          Открыть уроки
        </button>`;
    }
  } catch (e) { console.error("dream answer:", e); }
}

// ═══════════════════════════════════════════════════════════════════════════
// ── EVOLUTION SYSTEM ──────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════

async function showEvolutionInfo() {
  if (!state.userId) return;
  try {
    const [stagesRes, homRes] = await Promise.all([
      fetch(`${API}/homunculus/stages`),
      fetch(`${API}/homunculus/${state.userId}`),
    ]);
    const stages = await stagesRes.json();
    const hom    = await homRes.json();
    _renderHomunculusStagesList(stages, hom.stage || 1);
    const titleEl = document.getElementById("evoModalTitle");
    if (titleEl) titleEl.textContent = "Стадии Гомункула";
    const bigEl = document.getElementById("evoEmojiBig");
    if (bigEl) bigEl.textContent = "⚗️";
    const nameEl = document.getElementById("evoModalName");
    if (nameEl) nameEl.textContent = hom.stage_name || "";
    openModal("evolutionModal");
  } catch (e) { console.warn("evo info:", e); }
}
window.showEvolutionInfo = showEvolutionInfo;

function _renderHomunculusStagesList(stages, currentStage) {
  const listEl = document.getElementById("evoStagesList");
  if (!listEl) return;
  const stageIcons = ["⚗️","🧪","👶","🐉","🔥","👑","💎"];
  listEl.innerHTML = (stages || []).map((s, i) => {
    let cls = "evo-stage-row";
    if (s.id < currentStage)  cls += " done";
    if (s.id === currentStage) cls += " current";
    return `<div class="${cls}">
      <span class="evo-stage-emoji">${stageIcons[i] || "⚗️"}</span>
      <span><strong>Ст.${s.id} ${s.name}</strong> — ${s.souls_req} душ / ${s.modules_req} мод.</span>
      ${s.id === currentStage ? "<span style='margin-left:auto'>← Сейчас</span>" : ""}
      ${s.id < currentStage   ? "<span style='margin-left:auto'>✓</span>" : ""}
    </div>`;
  }).join("");
}

function _spawnEvolutionParticles() {
  const container = document.getElementById("evoParticles");
  if (!container) return;
  container.innerHTML = "";
  const emojis = ["⚗️","✨","💎","🌑","🔥","〜","⚡"];
  for (let i = 0; i < 20; i++) {
    const el = document.createElement("div");
    el.style.cssText = `
      position:absolute; font-size:${12+Math.random()*14}px;
      left:${Math.random()*100}%; top:${Math.random()*100}%;
      animation: floatUp ${0.6+Math.random()*0.8}s ease-out forwards;
      animation-delay: ${Math.random()*0.4}s;
    `;
    el.textContent = emojis[Math.floor(Math.random()*emojis.length)];
    container.appendChild(el);
    setTimeout(() => el.remove(), 1500);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ── SOULS SYSTEM (Dark Souls × SMC) — Phase 1 ────────────────────────────
// ══════════════════════════════════════════════════════════════════════════

/**
 * Update the souls HUD (counter + flasks) from a souls_state object.
 * @param {object} s - souls_state from /api/souls/{user_id} or /api/user/init
 */
function updateSoulsHUD(s) {
  if (!s) return;
  const soulsEl = document.getElementById("hudSoulsVal");
  if (soulsEl) soulsEl.textContent = Math.floor(s.souls ?? 0);
  updateEstusHUD(s.estus_flasks ?? 3, s.estus_max ?? 3);
}

/**
 * Update the Estus flask icons in the HUD.
 * @param {number} current - flasks remaining
 * @param {number} max - maximum flasks
 */
function updateEstusHUD(current, max) {
  for (let i = 0; i < 3; i++) {
    const flask = document.getElementById(`flask${i}`);
    if (!flask) continue;
    flask.classList.toggle("empty", i >= current);
  }
}

/**
 * Spawn a floating soul particle (+N ⚡ or -N ⚡).
 * @param {string} text - e.g. "+5 ⚡"
 * @param {boolean} gaining - true for gain, false for loss
 */
function spawnSoulParticle(text, gaining = true) {
  const layer = document.getElementById("soulsFloatLayer");
  if (!layer) return;
  const p = document.createElement("div");
  p.className = "soul-particle" + (gaining ? "" : " losing");
  p.textContent = text;
  // Random position in center area
  p.style.left = (35 + Math.random() * 30) + "%";
  p.style.top  = (30 + Math.random() * 20) + "%";
  layer.appendChild(p);
  setTimeout(() => p.remove(), 1300);
}

/**
 * Apply hollow state visuals to the page body.
 * @param {object} hollowData - from check_hollow API response
 */
function applyHollowState(hollowData) {
  if (!hollowData) return;
  if (hollowData.is_hollow || hollowData.became_hollow) {
    document.body.classList.add("is-hollow");
    if (hollowData.became_hollow) {
      // Show the hollow overlay with a delay
      setTimeout(() => {
        const overlay = document.getElementById("hollowOverlay");
        if (overlay) overlay.classList.remove("hidden");
      }, 800);
    }
  } else {
    document.body.classList.remove("is-hollow");
  }
}

/**
 * Show the dropped souls banner below the header.
 * @param {number} amount - number of dropped souls
 */
function showDroppedSoulsBanner(amount) {
  // Remove existing banner if any
  const existing = document.querySelector(".souls-dropped-banner");
  if (existing) existing.remove();

  const banner = document.createElement("div");
  banner.className = "souls-dropped-banner";
  banner.innerHTML = `
    <span class="dropped-icon">💀</span>
    <div class="dropped-info">
      <div class="dropped-label">ДУШИ НА ЗЕМЛЕ</div>
      <div class="dropped-amount">${amount} ⚡</div>
    </div>
    <button class="btn-retrieve-souls" onclick="showSoulsDrop(${amount})">
      Забрать →
    </button>
  `;

  // Insert after the progress section
  const progress = document.querySelector(".progress-section");
  if (progress) progress.after(banner);
}

/**
 * Show the ЛИКВИДИРОВАН (souls drop) overlay.
 * @param {number} dropped - souls dropped
 */
function showSoulsDrop(dropped) {
  const overlay = document.getElementById("soulsDropOverlay");
  const amountEl = document.getElementById("soulsDropAmount");
  if (!overlay) return;
  if (amountEl) amountEl.textContent = `${dropped} ⚡`;
  overlay.classList.remove("hidden");
}

/** Close the souls-drop overlay. */
function closeSoulsDrop() {
  const overlay = document.getElementById("soulsDropOverlay");
  if (overlay) overlay.classList.add("hidden");
}

/** Exit hollow state — spend 100 souls. */
async function exitHollow() {
  if (!state.userId) return;
  try {
    const res  = await fetch(`${API}/souls/hollow-exit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId }),
    });
    const data = await res.json();
    if (data.ok) {
      document.body.classList.remove("is-hollow");
      document.getElementById("hollowOverlay")?.classList.add("hidden");
      updateSoulsHUD({ souls: data.total_souls });
      showToast("Hollow отступил. Огонь бонфайра возвращён.", "success", "🔥");
      spawnSoulParticle(`-100 ⚡`, false);
    } else {
      const msg = data.reason === "insufficient_souls"
        ? `Недостаточно душ. Нужно 100, у тебя ${data.have}.`
        : data.reason || "Ошибка";
      showToast(msg, "error", "💀");
    }
  } catch (e) {
    console.error("exitHollow:", e);
    showToast("Ошибка выхода из Hollow", "error");
  }
}

window.exitHollow      = exitHollow;
window.closeSoulsDrop  = closeSoulsDrop;
window.showSoulsDrop   = showSoulsDrop;

// ══════════════════════════════════════════════════════════════════════════
// ── PHASE 2: BOSS, BONFIRE, BLOODSTAINS, ESTUS HINTS ─────────────────────
// ══════════════════════════════════════════════════════════════════════════

// ── Boss state ──────────────────────────────────────────────────────────
const bossState = {
  moduleId:    null,
  config:      null,    // boss config from API
  questions:   [],
  current:     0,
  correct:     0,
  timer:       null,
  timerLeft:   0,
  timerMax:    120,
  startedAt:   null,
  soulsAtStake: 0,
};

// ── Open boss intro (called when user clicks boss quest) ─────────────────
async function openBossIntro(moduleId) {
  try {
    const res  = await fetch(`${API}/boss/${moduleId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId }),
    });
    const data = await res.json();
    if (!data.ok) { showToast(data.reason || "Босс недоступен", "error"); return; }

    bossState.moduleId     = moduleId;
    bossState.config       = data;
    bossState.questions    = data.questions || [];
    bossState.soulsAtStake = data.souls_at_stake || 0;

    document.getElementById("bossIntroName").textContent  = data.name || "Босс";
    document.getElementById("bossIntroLore").textContent  = data.lore || "";
    document.getElementById("bossStakeAmount").textContent= `${bossState.soulsAtStake} ⚡`;
    document.getElementById("bossTimerPreview").textContent = `${data.timer_secs} сек`;

    document.getElementById("bossIntroOverlay").classList.remove("hidden");
  } catch (e) {
    console.error("openBossIntro:", e);
    showToast("Ошибка загрузки босса", "error");
  }
}

function closeBossIntro() {
  document.getElementById("bossIntroOverlay")?.classList.add("hidden");
}

// ── Actually start the fight ─────────────────────────────────────────────
function startBossFight() {
  closeBossIntro();
  const arena = document.getElementById("bossArena");
  if (!arena) return;

  bossState.current   = 0;
  bossState.correct   = 0;
  bossState.startedAt = Date.now();
  bossState.timerMax  = bossState.config?.timer_secs ?? 120;
  bossState.timerLeft = bossState.timerMax;

  // Update HUD
  document.getElementById("bossArenaName").textContent = bossState.config?.name ?? "Босс";
  document.getElementById("bossArenaStake").textContent = bossState.soulsAtStake;
  _updateBossProgress();

  arena.classList.remove("hidden");
  _renderBossQuestion();
  _startBossTimer();

  // Block back button
  if (tg) { tg.BackButton.show(); tg.BackButton.onClick(() => {}); }
}

function _updateBossProgress() {
  const total = bossState.questions.length;
  const done  = bossState.current;
  const pct   = total > 0 ? Math.round(done / total * 100) : 0;
  const bar   = document.getElementById("bossProgressBar");
  if (bar) bar.style.width = pct + "%";
  const counter = document.getElementById("bossQCounter");
  if (counter) counter.textContent = `${done + 1}/${total}`;
  const acc = document.getElementById("bossAccuracyHud");
  if (acc && done > 0) acc.textContent = `${Math.round(bossState.correct / done * 100)}%`;
}

function _renderBossQuestion() {
  const q = bossState.questions[bossState.current];
  if (!q) return;
  document.getElementById("bossQuestionText").textContent = q.question;
  const fb = document.getElementById("bossQFeedback");
  if (fb) { fb.className = "boss-q-feedback hidden"; fb.textContent = ""; }

  const opts = document.getElementById("bossOptions");
  opts.innerHTML = "";
  q.options.forEach((opt, i) => {
    const btn = document.createElement("button");
    btn.className = "boss-option";
    btn.textContent = opt;
    btn.addEventListener("click", () => _onBossAnswer(i, q.correct_index, q.explanation));
    opts.appendChild(btn);
  });
  _updateBossProgress();
}

function _onBossAnswer(chosen, correctIdx, explanation) {
  const isCorrect = chosen === correctIdx;
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred(isCorrect ? "success" : "error");

  // Disable all options
  document.querySelectorAll(".boss-option").forEach((b, i) => {
    b.disabled = true;
    if (i === correctIdx) b.classList.add("correct");
    if (i === chosen && !isCorrect) b.classList.add("wrong");
  });

  if (isCorrect) bossState.correct++;

  const fb = document.getElementById("bossQFeedback");
  if (fb) {
    fb.className = `boss-q-feedback ${isCorrect ? "correct-fb" : "wrong-fb"}`;
    fb.textContent = isCorrect ? "✓ " + (explanation || "Верно!") : "✗ " + (explanation || "Неверно.");
    fb.classList.remove("hidden");
  }

  // Auto-advance after 1.8s
  setTimeout(() => {
    bossState.current++;
    if (bossState.current >= bossState.questions.length) {
      _finishBossFight();
    } else {
      _renderBossQuestion();
    }
  }, 1800);
}

function _startBossTimer() {
  clearInterval(bossState.timer);
  const totalCirc = 163; // SVG circumference for r=26
  bossState.timer = setInterval(() => {
    bossState.timerLeft--;
    const num    = document.getElementById("bossTimerNum");
    const circle = document.getElementById("bossTimerCircle");
    if (num) {
      num.textContent = bossState.timerLeft;
      num.classList.toggle("critical", bossState.timerLeft <= 15);
    }
    if (circle) {
      const pct = bossState.timerLeft / bossState.timerMax;
      circle.style.strokeDashoffset = totalCirc * (1 - pct);
      circle.style.stroke = bossState.timerLeft <= 15 ? "#c0392b" : "#c8a84e";
    }
    if (bossState.timerLeft <= 0) {
      _finishBossFight();
    }
  }, 1000);
}

async function _finishBossFight() {
  clearInterval(bossState.timer);
  document.getElementById("bossArena")?.classList.add("hidden");

  const timeSpent = Math.round((Date.now() - bossState.startedAt) / 1000);
  const total     = bossState.questions.length;

  try {
    const res  = await fetch(`${API}/boss/${bossState.moduleId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id:            state.userId,
        correct:            bossState.correct,
        total:              total,
        time_spent_seconds: timeSpent,
      }),
    });
    const data = await res.json();
    if (!data.ok) { showToast("Ошибка боя", "error"); return; }

    if (data.result === "victory") {
      _showBossVictory(data);
    } else {
      _showBossDeath(data);
    }
  } catch (e) {
    console.error("boss submit:", e);
    showToast("Ошибка отправки результата", "error");
  }

  // Re-enable back button
  if (tg) tg.BackButton.hide();
}

// ── Death screen ─────────────────────────────────────────────────────────
function _showBossDeath(data) {
  const screen = document.getElementById("bossDeathScreen");
  if (!screen) return;
  document.getElementById("deathDroppedAmount").textContent = `${data.dropped_souls ?? 0} ⚡`;
  screen.classList.remove("hidden");
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
  // Update souls HUD
  spawnSoulParticle(`-${data.dropped_souls ?? 0} ⚡`, false);
}

function retryBoss() {
  document.getElementById("bossDeathScreen")?.classList.add("hidden");
  openBossIntro(bossState.moduleId);
}

function leaveBossArena() {
  document.getElementById("bossDeathScreen")?.classList.add("hidden");
  loadQuests();
}

// ── Victory screen ───────────────────────────────────────────────────────
function _showBossVictory(data) {
  const screen = document.getElementById("bossVictoryScreen");
  if (!screen) return;
  document.getElementById("victoryBossName").textContent = data.boss_name || "Босс";

  // Stats
  const statsEl = document.getElementById("victoryStats");
  if (statsEl) {
    statsEl.innerHTML = `
      <div class="victory-stat">
        <div class="vs-label">ТОЧНОСТЬ</div>
        <div class="vs-value">${data.accuracy}%</div>
      </div>
      <div class="victory-stat">
        <div class="vs-label">ВЕРНО</div>
        <div class="vs-value">${data.correct}/${data.total}</div>
      </div>
    `;
  }

  const soulsEl = document.getElementById("victorySoulsEarned");
  if (soulsEl) soulsEl.textContent = `+${data.souls_earned ?? 0} ⚡`;
  spawnSoulParticle(`+${data.souls_earned ?? 0} ⚡`, true);

  const retrievedEl = document.getElementById("victorySoulsRetrieved");
  if (retrievedEl && data.souls_retrieved > 0) {
    retrievedEl.textContent = `+${data.souls_retrieved} ⚡ душ подобрано с земли!`;
    retrievedEl.classList.remove("hidden");
  }

  screen.classList.remove("hidden");
  _spawnVictoryParticles();
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");

  // Refresh header souls
  setTimeout(() => { refreshHeader(); loadQuests(); }, 500);
}

function afterBossVictory() {
  document.getElementById("bossVictoryScreen")?.classList.add("hidden");
  showBonfire();
}

function _spawnVictoryParticles() {
  const layer = document.getElementById("victoryParticles");
  if (!layer) return;
  layer.innerHTML = "";
  const emojis = ["⚡","✨","💛","🌟","⭐","💎","🏆"];
  for (let i = 0; i < 30; i++) {
    const p = document.createElement("div");
    p.className = "vp-particle";
    p.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    const tx  = (Math.random() - 0.5) * 300;
    const ty  = -(80 + Math.random() * 200);
    const rot = (Math.random() - 0.5) * 720;
    const dur = 1.5 + Math.random() * 1.5;
    p.style.cssText = `
      left:${20 + Math.random() * 60}%;
      top:${40 + Math.random() * 20}%;
      --tx:${tx}px; --ty:${ty}px; --rot:${rot}deg; --dur:${dur}s;
      animation-delay:${Math.random() * 0.5}s;
    `;
    layer.appendChild(p);
    setTimeout(() => p.remove(), (dur + 0.5) * 1000);
  }
}

// ── Bonfire screen ───────────────────────────────────────────────────────
async function showBonfire() {
  try {
    const res  = await fetch(`${API}/souls/bonfire/${state.userId}`, { method: "POST" });
    const data = await res.json();

    const screen = document.getElementById("bonfireScreen");
    if (!screen) return;

    // Module name
    const modName = document.getElementById("bonfireModuleName");
    if (modName && state.userState) {
      modName.textContent = `Модуль ${(state.userState.module_index ?? 0) + 1} пройден`;
    }

    // Stats
    const statsEl = document.getElementById("bonfireStats");
    if (statsEl) {
      statsEl.innerHTML = `
        <div class="bf-stat">
          <div class="bf-stat-label">ФЛАСКИ</div>
          <div class="bf-stat-value">${data.estus_flasks}/3</div>
        </div>
        <div class="bf-stat">
          <div class="bf-stat-label">ДУШИ</div>
          <div class="bf-stat-value">${data.souls} ⚡</div>
        </div>
      `;
    }

    // Next boss bloodstains
    const nextBossEl = document.getElementById("bonfireNextBoss");
    if (nextBossEl && data.next_boss_bloodstains?.total_attempts > 0) {
      const bs = data.next_boss_bloodstains;
      nextBossEl.textContent = `⚠️ Следующий босс: ${bs.boss_name} — ${bs.death_pct}% учеников погибли там`;
    } else if (nextBossEl) {
      nextBossEl.textContent = "";
    }

    // Spawn fire sparks
    _spawnFireSparks();

    // Update flasks HUD
    updateEstusHUD(data.estus_flasks, 3);

    screen.classList.remove("hidden");
  } catch (e) {
    console.error("showBonfire:", e);
    // If bonfire fails, just refresh quests
    loadQuests();
    refreshHeader();
  }
}

function _spawnFireSparks() {
  const sparks = document.getElementById("fireSparks");
  if (!sparks) return;
  sparks.innerHTML = "";
  for (let i = 0; i < 8; i++) {
    const s = document.createElement("div");
    s.className = "spark";
    const sx  = 20 + Math.random() * 60;
    const dx  = (Math.random() - 0.5) * 30;
    const dur = 0.6 + Math.random() * 0.8;
    const del = Math.random() * 1.5;
    s.style.cssText = `--sx:${sx}%; --dx:${dx}px; --dur:${dur}s; animation-delay:${del}s`;
    sparks.appendChild(s);
  }
}

function closeBonfire() {
  document.getElementById("bonfireScreen")?.classList.add("hidden");
  loadQuests();
  refreshHeader();
}

// ── Bloodstains on quest cards ────────────────────────────────────────────
const _bloodstainCache = {};

async function loadBloodstainForModule(moduleId) {
  if (_bloodstainCache[moduleId] !== undefined) return _bloodstainCache[moduleId];
  try {
    const res  = await fetch(`${API}/boss/${moduleId}/bloodstains`);
    const data = await res.json();
    _bloodstainCache[moduleId] = data.ok ? data : null;
    return _bloodstainCache[moduleId];
  } catch { return null; }
}

async function injectBloodstains(moduleId) {
  const data = await loadBloodstainForModule(moduleId);
  if (!data || !data.total_attempts) return;

  const bossCards = document.querySelectorAll(".quest-card.boss");
  bossCards.forEach(card => {
    // Avoid duplicate
    if (card.querySelector(".bloodstain-dot")) return;
    const dot = document.createElement("div");
    dot.className = "bloodstain-dot";
    dot.textContent = `${data.death_pct ?? 0}% учеников погибли здесь`;
    // Insert before the button
    const btn = card.querySelector(".btn-quest");
    if (btn) btn.before(dot);
  });
}

// ── Override quest card button for boss quests ────────────────────────────
const _origRenderQuests = window.renderQuests;

/**
 * Patch: after renderQuests() runs, make boss quest cards open BossIntro.
 */
function _patchBossButtons() {
  const cards = document.querySelectorAll(".quest-card.boss");
  cards.forEach(card => {
    const btn = card.querySelector(".btn-quest");
    if (!btn || btn.dataset.bossPatched) return;
    btn.dataset.bossPatched = "1";
    // Re-wire click handler to boss intro
    const newBtn = btn.cloneNode(true);
    btn.replaceWith(newBtn);
    // Determine moduleId from the card (added below via data attribute)
    const moduleId = parseInt(card.dataset.moduleId ?? "0", 10);
    if (!newBtn.disabled) {
      newBtn.addEventListener("click", () => openBossIntro(moduleId));
    }
  });
}

// ── Estus hint in quiz ────────────────────────────────────────────────────
async function useEstusHint() {
  if (!state.userId) return;
  const q = state.quizData?.questions?.[state.quizData?.current];
  if (!q) return;

  try {
    const res  = await fetch(`${API}/souls/estus-use`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId }),
    });
    const data = await res.json();
    if (!data.ok) {
      showToast(data.reason === "no_flasks" ? "Фласки закончились!" : "Ошибка", "error", "🔶");
      return;
    }

    // Update flask counter
    const cnt = document.getElementById("estusHintCount");
    if (cnt) cnt.textContent = data.remaining;
    updateEstusHUD(data.remaining, 3);

    // Show hint: eliminate one wrong option
    const correctIdx = q.correct_index;
    const wrongIdxs  = q.options
      .map((_, i) => i)
      .filter(i => i !== correctIdx);
    const eliminate  = wrongIdxs[Math.floor(Math.random() * wrongIdxs.length)];

    const hintEl = document.getElementById("estusHintText");
    if (hintEl) {
      hintEl.textContent = `💡 Подсказка: вариант "${q.options[eliminate]}" — неверный.`;
      hintEl.classList.remove("hidden");
    }

    // Dim the eliminated option
    const optBtns = document.querySelectorAll(".quiz-option");
    if (optBtns[eliminate]) {
      optBtns[eliminate].style.opacity = "0.3";
      optBtns[eliminate].disabled = true;
    }

    showToast(`Фласка использована. Осталось: ${data.remaining}`, "success", "🔶");
  } catch (e) {
    console.error("useEstusHint:", e);
  }
}
window.useEstusHint = useEstusHint;

// ── Wire up boss buttons after quests are rendered ────────────────────────
const _origLoadQuests = window.loadQuests;
window.loadQuests = async function() {
  // Call original (defined elsewhere)
  if (typeof loadQuests_original === "function") await loadQuests_original();
};

// Expose functions globally
window.openBossIntro    = openBossIntro;
window.closeBossIntro   = closeBossIntro;
window.startBossFight   = startBossFight;
window.retryBoss        = retryBoss;
window.leaveBossArena   = leaveBossArena;
window.afterBossVictory = afterBossVictory;
window.showBonfire      = showBonfire;
window.closeBonfire     = closeBonfire;

// ══════════════════════════════════════════════════════════════════════════════
// PHASE 3 — SOCIAL SYSTEMS
// ══════════════════════════════════════════════════════════════════════════════

// ── PHANTOM MESSAGES ──────────────────────────────────────────────────────────

let _currentPhantomQuestId = null;

async function openPhantoms(questId) {
  _currentPhantomQuestId = questId;
  const overlay = $("#phantomOverlay");
  const list    = $("#phantomList");
  overlay.classList.remove("hidden");
  list.innerHTML = `<div class="phantom-loading">Призываем призраков…</div>`;

  try {
    const uid = state.userId;
    const res = await fetch(`/api/social/phantoms/${questId}?user_id=${uid}`);
    const data = await res.json();
    const phantoms = data.phantoms || [];

    if (!phantoms.length) {
      list.innerHTML = `<div class="phantom-empty">Никто ещё не оставил послания.<br>Будь первым призраком.</div>`;
    } else {
      list.innerHTML = "";
      phantoms.forEach(ph => {
        const item = document.createElement("div");
        item.className = "phantom-item";
        item.dataset.id = ph.id;
        item.innerHTML = `
          <div class="phantom-item-header">
            <span class="phantom-item-user">👻 ${_esc(ph.username)}</span>
          </div>
          <div class="phantom-item-text">${_esc(ph.text)}</div>
          <div class="phantom-vote-row">
            <button class="phantom-vote-btn" onclick="votePhantom('${questId}','${ph.id}','up',this)">
              👍 ${ph.votes_up}
            </button>
            <button class="phantom-vote-btn" onclick="votePhantom('${questId}','${ph.id}','down',this)">
              👎 ${ph.votes_down}
            </button>
          </div>`;
        list.appendChild(item);
      });
    }
  } catch(e) {
    list.innerHTML = `<div class="phantom-empty">Не удалось призвать призраков.</div>`;
  }

  // Char counter
  const input = $("#phantomInput");
  const counter = $("#phantomCharCount");
  if (input) {
    input.value = "";
    input.oninput = () => { counter.textContent = `${input.value.length}/200`; };
  }
}

function closePhantoms() {
  $("#phantomOverlay").classList.add("hidden");
  _currentPhantomQuestId = null;
}

async function votePhantom(questId, phantomId, vote, btn) {
  btn.classList.add("voted");
  try {
    await fetch(`/api/social/phantoms/${questId}/${phantomId}/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, vote }),
    });
  } catch(e) { /* silent */ }
}

async function sendPhantom() {
  const input = $("#phantomInput");
  const text  = input?.value.trim();
  if (!text || !_currentPhantomQuestId) return;

  const btn = document.querySelector(".btn-phantom-send");
  if (btn) btn.disabled = true;

  try {
    await fetch(`/api/social/phantoms/${_currentPhantomQuestId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id:  state.userId,
        username: state.userState?.username || "Призрак",
        text,
      }),
    });
    input.value = "";
    $("#phantomCharCount").textContent = "0/200";
    // Refresh list
    await openPhantoms(_currentPhantomQuestId);
  } catch(e) { /* silent */ } finally {
    if (btn) btn.disabled = false;
  }
}

function _esc(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

// ── DAILY CHALLENGE ───────────────────────────────────────────────────────────

let _dailyData = null;

async function openDaily() {
  const overlay = $("#dailyOverlay");
  overlay.classList.remove("hidden");
  await _loadDailyChallenge();
}

function closeDaily() {
  $("#dailyOverlay").classList.add("hidden");
}

async function _loadDailyChallenge() {
  try {
    const res  = await fetch(`/api/social/daily?user_id=${state.userId}`);
    _dailyData = await res.json();

    $("#dailyDate").textContent       = _dailyData.date || "";
    $("#dailyStreakBadge").textContent = `🔥 ${_dailyData.streak || 0} дней`;
    $("#dailyRewardSouls").textContent = `${_dailyData.souls_reward || 0} ⚡`;
    $("#dailyQuestion").textContent   = _dailyData.question || "";

    const optEl = $("#dailyOptions");
    optEl.innerHTML = "";
    const resultEl   = $("#dailyResult");
    const completedEl = $("#dailyCompleted");
    resultEl.classList.add("hidden");
    completedEl.classList.add("hidden");

    if (_dailyData.completed) {
      // Already done today
      optEl.classList.add("hidden");
      completedEl.classList.remove("hidden");
      const streak = _dailyData.streak || 0;
      $("#dailyStreakDisplay").textContent = `🔥 Серия: ${streak} дней`;
    } else {
      optEl.classList.remove("hidden");
      (_dailyData.options || []).forEach((opt, i) => {
        const btn = document.createElement("button");
        btn.className = "daily-option";
        btn.textContent = opt;
        btn.addEventListener("click", () => _submitDailyAnswer(i));
        optEl.appendChild(btn);
      });
    }
  } catch(e) {
    $("#dailyQuestion").textContent = "Не удалось загрузить вызов.";
  }
}

async function _submitDailyAnswer(answerIdx) {
  // Disable all options immediately
  document.querySelectorAll(".daily-option").forEach(b => b.disabled = true);

  try {
    const res    = await fetch("/api/social/daily/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, answer_idx: answerIdx }),
    });
    const result = await res.json();

    // Mark correct/wrong options visually
    document.querySelectorAll(".daily-option").forEach((b, i) => {
      if (i === result.correct_idx) b.classList.add("correct");
      else if (i === answerIdx && !result.correct) b.classList.add("wrong");
    });

    // Show result after 600ms
    setTimeout(() => {
      $("#dailyOptions").classList.add("hidden");
      const resultEl = $("#dailyResult");
      resultEl.classList.remove("hidden");

      if (result.correct) {
        $("#dailyResultIcon").textContent  = "⚔️";
        $("#dailyResultText").textContent  = "Правильно! Рынок поклоняется тебе.";
        $("#dailySoulsWon").textContent    = `+${result.souls_won} ⚡`;
        $("#dailyStreakUpdate").textContent = `🔥 Серия: ${result.streak} дней`;
        // Update HUD
        if (state.userState) {
          state.userState.souls = (state.userState.souls || 0) + result.souls_won;
          updateSoulsHUD({ souls: state.userState.souls });
        }
      } else {
        $("#dailyResultIcon").textContent  = "💀";
        $("#dailyResultText").textContent  = "Ликвидирован. Рынок безжалостен.";
        $("#dailySoulsWon").textContent    = "0 ⚡";
        $("#dailyStreakUpdate").textContent = "Серия прервана.";
      }
    }, 600);

  } catch(e) {
    document.querySelectorAll(".daily-option").forEach(b => b.disabled = false);
  }
}

// Badge on daily button if not yet completed today
async function _checkDailyBadge() {
  try {
    const res  = await fetch(`/api/social/daily?user_id=${state.userId}`);
    const data = await res.json();
    const badge = $("#dailyBadge");
    if (badge) {
      badge.style.display = !data.completed ? "flex" : "none";
    }
  } catch(e) { /* silent */ }
}

// ── CLANS ─────────────────────────────────────────────────────────────────────

let _clanData = null;

async function openClanPanel() {
  $("#clanPanel").classList.remove("hidden");
  await _loadClanData();
}

function closeClanPanel() {
  $("#clanPanel").classList.add("hidden");
}

async function _loadClanData() {
  // Load user's clan
  try {
    const res   = await fetch(`/api/social/clans/me?user_id=${state.userId}`);
    const data  = await res.json();
    _clanData   = data.clan;
    _renderMyClan(_clanData);
  } catch(e) { /* silent */ }

  // Load leaderboard
  try {
    const res  = await fetch("/api/social/clans");
    const data = await res.json();
    _renderClanLeaderboard(data.clans || []);
  } catch(e) { /* silent */ }
}

function _renderMyClan(clan) {
  const noneEl = $("#clanNone");
  const mineEl = $("#clanMine");

  if (!clan) {
    noneEl.classList.remove("hidden");
    mineEl.classList.add("hidden");
    return;
  }

  noneEl.classList.add("hidden");
  mineEl.classList.remove("hidden");

  $("#clanMineTag").textContent  = `[${clan.tag}]`;
  $("#clanMineName").textContent = clan.name;

  const weeklySouls  = clan.weekly_souls || 0;
  const weeklyTarget = clan.weekly_target || 1000;
  $("#clanWeeklySouls").textContent  = weeklySouls;
  $("#clanWeeklyTarget").textContent = weeklyTarget;
  $("#clanProgressBar").style.width  = `${clan.progress_pct || 0}%`;

  // Members list
  const membersList = $("#clanMembersList");
  membersList.innerHTML = "";
  (clan.members || []).forEach(uid => {
    const row = document.createElement("div");
    row.className = "clan-member-row";
    const isLeader = uid === clan.leader_id;
    const isMe     = uid === state.userId;
    row.innerHTML = `
      <span class="clan-member-icon">${isLeader ? "👑" : "⚔️"}</span>
      <span class="clan-member-name">${isMe ? "Ты" : `Трейдер #${uid}`}</span>
      ${isLeader ? '<span class="clan-member-leader">Лидер</span>' : ""}
    `;
    membersList.appendChild(row);
  });

  // Hollow warning
  const hollowCount = clan.hollow_count || 0;
  const hollowWarn  = $("#clanHollowWarning");
  if (hollowCount > 0) {
    hollowWarn.classList.remove("hidden");
    $("#clanHollowCount").textContent = hollowCount;
  } else {
    hollowWarn.classList.add("hidden");
  }
}

function _renderClanLeaderboard(clans) {
  const lb = $("#clanLeaderboard");
  if (!clans.length) {
    lb.innerHTML = `<div class="clan-lb-loading">Кланов пока нет.</div>`;
    return;
  }
  lb.innerHTML = "";
  clans.forEach((c, i) => {
    const row = document.createElement("div");
    row.className = "clan-lb-row";
    row.innerHTML = `
      <span class="clan-lb-rank">${i + 1}</span>
      <span class="clan-lb-tag">[${c.tag}]</span>
      <span class="clan-lb-name">${_esc(c.name)}</span>
      <span class="clan-lb-souls">${c.souls_pool} ⚡</span>
      <span class="clan-lb-members">${c.member_count}/5</span>
    `;
    lb.appendChild(row);
  });
}

function showClanCreate() {
  $("#clanCreateForm").classList.toggle("hidden");
  $("#clanJoinForm").classList.add("hidden");
}

function showClanJoin() {
  $("#clanJoinForm").classList.toggle("hidden");
  $("#clanCreateForm").classList.add("hidden");
}

async function createClan() {
  const name = $("#clanNameInput").value.trim();
  const tag  = $("#clanTagInput").value.trim();
  if (!name || !tag) return;

  try {
    const res  = await fetch("/api/social/clans/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, name, tag }),
    });
    const data = await res.json();
    if (data.ok) {
      _clanData = data.clan;
      _renderMyClan(data.clan);
    } else {
      alert(data.detail || "Ошибка создания клана");
    }
  } catch(e) { alert("Ошибка сети"); }
}

async function joinClan() {
  const tag = $("#clanTagJoinInput").value.trim();
  if (!tag) return;

  try {
    const res  = await fetch("/api/social/clans/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, tag }),
    });
    const data = await res.json();
    if (data.ok) {
      _clanData = data.clan;
      _renderMyClan(data.clan);
    } else {
      alert(data.detail || "Клан не найден или переполнен");
    }
  } catch(e) { alert("Ошибка сети"); }
}

async function leaveClan() {
  if (!confirm("Покинуть клан?")) return;
  try {
    const res  = await fetch("/api/social/clans/leave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId }),
    });
    const data = await res.json();
    if (data.ok) {
      _clanData = null;
      _renderMyClan(null);
    }
  } catch(e) { alert("Ошибка сети"); }
}

function showContributeModal() {
  const modal = $("#contributeModal");
  modal.classList.remove("hidden");
  const avail = state.userState?.souls || 0;
  $("#contributeSoulsAvail").textContent = avail;
  $("#contributeAmount").value = "";
}

function closeContributeModal() {
  $("#contributeModal").classList.add("hidden");
}

async function confirmContribute() {
  const amount = parseInt($("#contributeAmount").value);
  if (!amount || amount < 10) { alert("Минимум 10 душ"); return; }

  try {
    const res  = await fetch("/api/social/clans/contribute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, amount }),
    });
    const data = await res.json();
    if (data.ok) {
      closeContributeModal();
      if (state.userState) {
        state.userState.souls = data.souls_remaining;
        updateSoulsHUD({ souls: data.souls_remaining });
      }
      _clanData = data.clan;
      _renderMyClan(data.clan);
    } else {
      alert(data.detail || "Недостаточно душ");
    }
  } catch(e) { alert("Ошибка сети"); }
}

// Expose globals
window.openPhantoms        = openPhantoms;
window.closePhantoms       = closePhantoms;
window.sendPhantom         = sendPhantom;
window.votePhantom         = votePhantom;
window.openDaily           = openDaily;
window.closeDaily          = closeDaily;
window.openClanPanel       = openClanPanel;
window.closeClanPanel      = closeClanPanel;
window.showClanCreate      = showClanCreate;
window.showClanJoin        = showClanJoin;
window.createClan          = createClan;
window.joinClan            = joinClan;
window.leaveClan           = leaveClan;
window.showContributeModal = showContributeModal;
window.closeContributeModal = closeContributeModal;
window.confirmContribute   = confirmContribute;

// ── BTN START ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  init();
  initChartLightbox();

  document.getElementById("startBtn")?.addEventListener("click", () => {
    switchTab("lessons");
    setTimeout(() => {
      const firstOpen = document.querySelector(".module-card.open .lesson-item");
      if (firstOpen) firstOpen.click();
    }, 200);
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// PHASE 4: KNOWLEDGE ROULETTE
// ══════════════════════════════════════════════════════════════════════════════

const _roulette = {
  selectedBet: null,
  spinId: null,
  potentialWin: 0,
  spinning: false,
  allTopics: [],
  winAngle: 0,
};

function openRoulette() {
  const modal = document.getElementById("rouletteModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  // Refresh balance
  const soulsEl = document.getElementById("rouletteSoulsBalance");
  if (soulsEl && state.userState) soulsEl.textContent = state.userState.souls ?? 0;
  // Reset state
  document.getElementById("rouletteBetSection").classList.remove("hidden");
  document.getElementById("rouletteQuestionSection").classList.add("hidden");
  document.getElementById("rouletteRevealBtn").classList.remove("hidden");
  document.getElementById("rouletteAnswerReveal").classList.add("hidden");
  _roulette.selectedBet = null;
  _roulette.spinId = null;
  _roulette.spinning = false;
  // Draw empty wheel
  _drawRouletteWheel([]);
  document.querySelectorAll(".roulette-bet-btn").forEach(b => b.classList.remove("selected"));
  document.getElementById("rouletteSpinBtn").disabled = true;
}

function closeRoulette() {
  document.getElementById("rouletteModal")?.classList.add("hidden");
}

function selectBet(amount) {
  _roulette.selectedBet = amount;
  document.querySelectorAll(".roulette-bet-btn").forEach(b => {
    b.classList.toggle("selected", parseInt(b.dataset.bet) === amount);
  });
  document.getElementById("rouletteSpinBtn").disabled = false;
}

function _drawRouletteWheel(topics) {
  const canvas = document.getElementById("rouletteCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const cx = 140, cy = 140, r = 135;
  ctx.clearRect(0, 0, 280, 280);

  const defaultTopics = topics.length > 0 ? topics : [
    {label:"Структура",color:"#c8a84e"},{label:"Ликвидность",color:"#00d4ff"},
    {label:"OB",color:"#a78bfa"},{label:"FVG",color:"#00e87a"},
    {label:"Inducement",color:"#f59e0b"},{label:"Premium/Disc",color:"#ff4d6d"},
    {label:"Риск",color:"#e8751a"},{label:"Killzones",color:"#78716c"},
  ];

  const sliceAngle = (2 * Math.PI) / defaultTopics.length;
  defaultTopics.forEach((t, i) => {
    const start = i * sliceAngle - Math.PI / 2;
    const end = start + sliceAngle;
    // Slice fill
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, start, end);
    ctx.closePath();
    ctx.fillStyle = i % 2 === 0 ? t.color + "cc" : t.color + "88";
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,0.4)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    // Label
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(start + sliceAngle / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#fff";
    ctx.font = "bold 11px Inter, sans-serif";
    ctx.fillText(t.label, r - 10, 4);
    ctx.restore();
  });
  // Center circle
  ctx.beginPath();
  ctx.arc(cx, cy, 20, 0, Math.PI * 2);
  ctx.fillStyle = "#0a0a0f";
  ctx.fill();
  ctx.strokeStyle = "rgba(200,168,78,0.6)";
  ctx.lineWidth = 2;
  ctx.stroke();
  // Center icon
  ctx.fillStyle = "#c8a84e";
  ctx.font = "bold 14px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("⚡", cx, cy);
}

async function spinRoulette() {
  if (!_roulette.selectedBet || _roulette.spinning) return;
  if (!state.userId) return;
  _roulette.spinning = true;
  document.getElementById("rouletteSpinBtn").disabled = true;

  try {
    const res = await fetch(`${API}/roulette/spin`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, bet: _roulette.selectedBet}),
    });
    const data = await res.json();
    if (!data.ok) {
      showToast(data.error === "not_enough_souls" ? "Недостаточно душ!" : "Ошибка", "error");
      _roulette.spinning = false;
      document.getElementById("rouletteSpinBtn").disabled = false;
      return;
    }

    _roulette.spinId = data.spin_id;
    _roulette.potentialWin = data.potential_win;
    _roulette.allTopics = data.all_topics || [];

    // Update balance
    if (state.userState) state.userState.souls = data.souls_remaining;
    const soulsEl = document.getElementById("rouletteSoulsBalance");
    if (soulsEl) soulsEl.textContent = data.souls_remaining;
    const hudEl = document.getElementById("hudSoulsVal");
    if (hudEl) hudEl.textContent = data.souls_remaining;

    // Draw wheel with real topics
    _drawRouletteWheel(_roulette.allTopics);

    // Find index of winning topic
    const topics = _roulette.allTopics;
    const winIdx = topics.findIndex(t => t.id === data.topic.id);
    const sliceAngle = 360 / topics.length;
    // Spin to winning slice (needle at top = 0 deg)
    const targetAngle = -(winIdx * sliceAngle + sliceAngle / 2);
    const totalSpin = 1440 + ((targetAngle % 360) + 360) % 360;
    document.getElementById("rouletteCanvas").style.setProperty("--spin-deg", totalSpin + "deg");

    const wheel = document.getElementById("rouletteWheel");
    wheel.classList.add("spinning");

    // After 3s animation — show question
    await new Promise(r => setTimeout(r, 3100));
    wheel.classList.remove("spinning");

    // Show question section
    document.getElementById("rouletteBetSection").classList.add("hidden");
    document.getElementById("rouletteQuestionSection").classList.remove("hidden");
    document.getElementById("rouletteTopicLabel").textContent = data.topic.label;
    document.getElementById("rouletteQuestion").textContent = data.question;
    document.getElementById("rouletteAnswerText").textContent = data.correct_answer;
    document.getElementById("roulettePotential").textContent = data.potential_win;

    _roulette.spinning = false;
  } catch(e) {
    showToast("Ошибка сети", "error");
    _roulette.spinning = false;
    document.getElementById("rouletteSpinBtn").disabled = false;
  }
}

function revealRouletteAnswer() {
  document.getElementById("rouletteRevealBtn").classList.add("hidden");
  document.getElementById("rouletteAnswerReveal").classList.remove("hidden");
}

async function submitRouletteAnswer(isCorrect) {
  if (!_roulette.spinId) return;
  document.querySelectorAll(".roulette-yes-btn, .roulette-no-btn").forEach(b => b.disabled = true);
  try {
    const res = await fetch(`${API}/roulette/answer`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, spin_id: _roulette.spinId, is_correct: isCorrect}),
    });
    const data = await res.json();
    if (data.ok) {
      if (state.userState) state.userState.souls = data.total_souls;
      const hudEl = document.getElementById("hudSoulsVal");
      if (hudEl) hudEl.textContent = data.total_souls;
      spawnSoulParticle(data.message, isCorrect);
      showToast(data.message, isCorrect ? "success" : "error");
      setTimeout(() => closeRoulette(), 2000);
    }
  } catch(e) { showToast("Ошибка", "error"); }
}


// ══════════════════════════════════════════════════════════════════════════════
// PHASE 4: INVASIONS
// ══════════════════════════════════════════════════════════════════════════════

const _invasion = {
  id: null,
  deadline: null,
  timerInterval: null,
};

async function checkInvasion() {
  if (!state.userId) return;
  try {
    const res = await fetch(`${API}/invasion/check/${state.userId}`);
    const data = await res.json();
    if (data.has_invasion && !data.expired && !data.invasion?.result) {
      _showInvasionModal(data.invasion, data.minutes_left);
    }
  } catch(e) { /* silent */ }
}

function _showInvasionModal(inv, minutesLeft) {
  _invasion.id = inv.id;
  _invasion.deadline = new Date(Date.now() + (minutesLeft || 30) * 60000);
  document.getElementById("invasionQuestion").textContent = inv.question;
  document.getElementById("invasionReward").textContent = inv.souls_reward || 50;
  document.getElementById("invasionModal").classList.remove("hidden");
  document.getElementById("invasionResult").classList.add("hidden");
  document.getElementById("invasionAnswerInput").value = "";
  _startInvasionTimer(minutesLeft * 60);
}

function _startInvasionTimer(seconds) {
  clearInterval(_invasion.timerInterval);
  let s = seconds;
  const timerEl = document.getElementById("invasionTimer");
  _invasion.timerInterval = setInterval(() => {
    s--;
    if (s <= 0) {
      clearInterval(_invasion.timerInterval);
      if (timerEl) timerEl.textContent = "00:00";
      const res = document.getElementById("invasionResult");
      if (res) {
        res.textContent = "⏰ Время вышло! Streak -1";
        res.className = "invasion-result defeated";
        res.classList.remove("hidden");
      }
      return;
    }
    const m = Math.floor(s / 60), sec = s % 60;
    if (timerEl) timerEl.textContent = `${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
  }, 1000);
}

function closeInvasion() {
  clearInterval(_invasion.timerInterval);
  document.getElementById("invasionModal")?.classList.add("hidden");
}

async function submitInvasion() {
  const answer = document.getElementById("invasionAnswerInput").value.trim();
  if (!answer) { showToast("Введи ответ", "error"); return; }
  if (!_invasion.id || !state.userId) return;

  document.querySelector(".invasion-submit-btn").disabled = true;
  try {
    const res = await fetch(`${API}/invasion/answer`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, invasion_id: _invasion.id, answer_text: answer}),
    });
    const data = await res.json();
    clearInterval(_invasion.timerInterval);
    const resEl = document.getElementById("invasionResult");
    if (data.ok) {
      resEl.textContent = `⚔️ Вторжение отражено! +${data.souls_earned} ⚡`;
      resEl.className = "invasion-result survived";
      if (state.userState) state.userState.souls = data.total_souls;
      const hudEl = document.getElementById("hudSoulsVal");
      if (hudEl) hudEl.textContent = data.total_souls;
      spawnSoulParticle(`+${data.souls_earned} ⚡`, true);
    } else {
      resEl.textContent = "❌ " + (data.error || "Ошибка");
      resEl.className = "invasion-result defeated";
    }
    resEl.classList.remove("hidden");
    setTimeout(() => closeInvasion(), 3000);
  } catch(e) {
    showToast("Ошибка сети", "error");
    document.querySelector(".invasion-submit-btn").disabled = false;
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// PHASE 4: PvP BATTLE MARKUP
// ══════════════════════════════════════════════════════════════════════════════

const _pvp = {
  matchId: null,
  pollInterval: null,
  battleTimer: null,
  timeLeft: 180,
};

function openPvP() {
  document.getElementById("pvpModal")?.classList.remove("hidden");
  document.getElementById("pvpMatchmaking")?.classList.remove("hidden");
  document.getElementById("pvpBattle")?.classList.add("hidden");
  document.getElementById("pvpResult")?.classList.add("hidden");
  document.getElementById("pvpWaiting")?.classList.add("hidden");
  document.getElementById("pvpFindActions")?.classList.remove("hidden");
  _pvp.matchId = null;
  clearInterval(_pvp.pollInterval);
  clearInterval(_pvp.battleTimer);

  // Setup slider
  const slider = document.getElementById("pvpScoreSlider");
  const valEl = document.getElementById("pvpScoreValue");
  if (slider && valEl) {
    slider.value = 50;
    valEl.textContent = "50";
    slider.oninput = () => {
      valEl.textContent = slider.value;
      slider.style.setProperty("--val", slider.value + "%");
    };
  }
}

function closePvP() {
  clearInterval(_pvp.pollInterval);
  clearInterval(_pvp.battleTimer);
  document.getElementById("pvpModal")?.classList.add("hidden");
}

async function pvpFindMatch() {
  if (!state.userId) return;
  document.getElementById("pvpFindActions")?.classList.add("hidden");
  document.getElementById("pvpWaiting")?.classList.remove("hidden");

  let waitEl = document.getElementById("pvpWaitSec");
  let waited = 0;
  const waitTimer = setInterval(() => {
    waited++;
    if (waitEl) waitEl.textContent = waited;
  }, 1000);

  // Poll for match
  _pvp.pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API}/pvp/find-match`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({user_id: state.userId}),
      });
      const data = await res.json();
      if (data.status === "matched") {
        clearInterval(_pvp.pollInterval);
        clearInterval(waitTimer);
        _pvp.matchId = data.match_id;
        _startPvPBattle(data);
      } else if (data.status === "timeout") {
        clearInterval(_pvp.pollInterval);
        clearInterval(waitTimer);
        document.getElementById("pvpWaiting")?.classList.add("hidden");
        document.getElementById("pvpFindActions")?.classList.remove("hidden");
        showToast("Соперник не найден. Попробуй позже.", "info");
      }
    } catch(e) { /* silent poll failure */ }
  }, 3000);
}

function _startPvPBattle(matchData) {
  document.getElementById("pvpMatchmaking")?.classList.add("hidden");
  document.getElementById("pvpBattle")?.classList.remove("hidden");

  const topicMap = {
    market_structure: "Структура рынка",
    liquidity: "Ликвидность",
    order_blocks: "Ордер-блоки",
    fvg: "Fair Value Gap",
    inducement: "Inducement",
    killzones: "Killzones",
    risk_management: "Риск-менеджмент",
  };
  const topicEl = document.getElementById("pvpChartTopic");
  if (topicEl) topicEl.textContent = topicMap[matchData.chart_key] || matchData.chart_key;

  // Battle countdown
  _pvp.timeLeft = matchData.time_limit_seconds || 180;
  const timerEl = document.getElementById("pvpBattleTimer");
  _pvp.battleTimer = setInterval(() => {
    _pvp.timeLeft--;
    if (timerEl) {
      const m = Math.floor(_pvp.timeLeft / 60), s = _pvp.timeLeft % 60;
      timerEl.textContent = `${m}:${String(s).padStart(2,"0")}`;
    }
    if (_pvp.timeLeft <= 0) {
      clearInterval(_pvp.battleTimer);
      // Auto-submit with current score
      submitPvP();
    }
  }, 1000);
}

async function submitPvP() {
  if (!_pvp.matchId || !state.userId) return;
  clearInterval(_pvp.battleTimer);
  const score = parseInt(document.getElementById("pvpScoreSlider")?.value || "50");

  document.querySelector(".pvp-submit-btn")?.setAttribute("disabled", true);
  try {
    const res = await fetch(`${API}/pvp/submit`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        user_id: state.userId,
        match_id: _pvp.matchId,
        markup: [],
        self_score: score,
      }),
    });
    const data = await res.json();
    if (data.status === "complete") {
      _showPvPResult(data);
    } else {
      // Waiting for opponent
      showToast("Ожидаем соперника...", "info");
      _pvp.pollInterval = setInterval(async () => {
        const r2 = await fetch(`${API}/pvp/result/${_pvp.matchId}?user_id=${state.userId}`);
        const d2 = await r2.json();
        if (d2.status === "complete") {
          clearInterval(_pvp.pollInterval);
          _showPvPResult({...d2, my_score: score, opponent_score: "?"});
        }
      }, 3000);
    }
  } catch(e) { showToast("Ошибка сети", "error"); }
}

function _showPvPResult(data) {
  document.getElementById("pvpBattle")?.classList.add("hidden");
  document.getElementById("pvpResult")?.classList.remove("hidden");

  const icon = document.getElementById("pvpResultIcon");
  const title = document.getElementById("pvpResultTitle");
  const scores = document.getElementById("pvpResultScores");
  const souls = document.getElementById("pvpResultSouls");

  const resultMap = {
    win: {icon:"🏆", text:"ПОБЕДА!", cls:"win", msg:`+${data.souls_earned || 30} ⚡ душ`},
    loss: {icon:"💀", text:"ПОРАЖЕНИЕ", cls:"loss", msg:"Тренируйся — и возвращайся!"},
    draw: {icon:"🤝", text:"НИЧЬЯ", cls:"draw", msg:`+${data.souls_earned || 10} ⚡ душ`},
  };
  const r = resultMap[data.result] || resultMap.draw;
  if (icon) icon.textContent = r.icon;
  if (title) { title.textContent = r.text; title.className = `pvp-result-title ${r.cls}`; }
  if (scores) scores.innerHTML = `Твой счёт: <b>${data.my_score}%</b><br>Соперник: <b>${data.opponent_score}%</b>`;
  if (souls) souls.textContent = r.msg;

  if (state.userState && data.souls_earned) {
    state.userState.souls = (state.userState.souls || 0) + data.souls_earned;
    const hudEl = document.getElementById("hudSoulsVal");
    if (hudEl) hudEl.textContent = state.userState.souls;
    if (data.souls_earned > 0) spawnSoulParticle(`+${data.souls_earned} ⚡`, true);
  }
}

// Expose Phase 4 globals
window.openRoulette        = openRoulette;
window.closeRoulette       = closeRoulette;
window.selectBet           = selectBet;
window.spinRoulette        = spinRoulette;
window.revealRouletteAnswer = revealRouletteAnswer;
window.submitRouletteAnswer = submitRouletteAnswer;
window.closeInvasion       = closeInvasion;
window.submitInvasion      = submitInvasion;
window.openPvP             = openPvP;
window.closePvP            = closePvP;
window.pvpFindMatch        = pvpFindMatch;
window.submitPvP           = submitPvP;

// Check invasion on page load
document.addEventListener("DOMContentLoaded", () => {
  setTimeout(checkInvasion, 3000);  // check 3s after load
});

// ══════════════════════════════════════════════════════════════════════════════
// ── SHOP ─────────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

const SHOP_CATS = [
  {id:"consumable", label:"Расходники"},
  {id:"boost",      label:"Бусты"},
  {id:"protection", label:"Защита"},
  {id:"emergency",  label:"Экстренное"},
  {id:"cosmetic",   label:"Косметика"},
  {id:"title",      label:"Титулы"},
];
let _shopData = null, _shopCat = "consumable";

async function loadShop() {
  if (!state.userId) return;
  try {
    const d = await fetch(`${API}/shop?user_id=${state.userId}`).then(r=>r.json());
    _shopData = d;
    _renderShop(d);
  } catch(e) { console.warn("shop:", e); }
}

function _renderShop(d) {
  const wrap = document.getElementById("shopWrap");
  if (!wrap) return;
  const souls = d.souls || 0;
  wrap.innerHTML = `
    <div class="shop-hdr">
      <span class="shop-ttl">⚗️ Лаборатория Алхимика</span>
      <div class="shop-bal">
        <span>⚡</span>
        <span id="shopSouls">${Math.floor(souls)}</span>
        <span class="shop-bal-lbl">душ</span>
      </div>
    </div>
    <div class="shop-cats" id="shopCats">
      ${SHOP_CATS.map(c=>`
        <button class="shop-cat ${c.id===_shopCat?'shop-cat-on':''}"
          onclick="setShopCat('${c.id}')">${c.label}</button>`).join('')}
    </div>
    <div id="shopItems"></div>
    <div class="shop-stars-row">
      Мало душ? <button class="shop-stars-btn" onclick="openBotShop()">Купить за ⭐ Stars</button>
    </div>`;
  _renderShopItems(d);
}

function setShopCat(cat) {
  _shopCat = cat;
  document.querySelectorAll(".shop-cat").forEach(b=>{
    b.classList.toggle("shop-cat-on", b.textContent.trim()===SHOP_CATS.find(c=>c.id===cat)?.label);
  });
  if (_shopData) _renderShopItems(_shopData);
}
window.setShopCat = setShopCat;

function _renderShopItems(d) {
  const el = document.getElementById("shopItems");
  if (!el) return;
  const items = (d.items||[]).filter(i=>i.category===_shopCat);
  if (!items.length) { el.innerHTML='<div class="shop-empty">Нет товаров</div>'; return; }
  el.innerHTML = items.map(item=>{
    const owned = item.owned, active = !!item.active_until;
    const canAfford = item.can_afford;
    let badge = owned ? '<span class="shop-owned">✓</span>'
              : active ? '<span class="shop-active">Активно</span>' : '';
    let btnTxt = `${item.price} ⚡`;
    let btnCls = "shop-buy-btn";
    let dis = "";
    if (owned || active) { btnTxt = owned?"Куплено":"Активно"; btnCls+=" shop-btn-dim"; dis="disabled"; }
    else if (!canAfford)  { btnCls+=" shop-btn-dim"; dis="disabled"; }
    return `
    <div class="shop-item">
      <span class="shop-item-ico">${item.icon}</span>
      <div class="shop-item-body">
        <div class="shop-item-name">${item.name} ${badge}</div>
        <div class="shop-item-desc">${item.desc}</div>
      </div>
      <button class="${btnCls}" ${dis}
        onclick="buyItem('${item.id}','${item.name.replace(/'/g,"\\'")}',${item.price})">
        ${btnTxt}
      </button>
    </div>`;
  }).join('');
}

async function buyItem(id, name, price) {
  if ((_shopData?.souls||0) < price) {
    showToast(`Нужно ${price} ⚡. Есть ${Math.floor(_shopData?.souls||0)}.`,"error"); return;
  }
  if (!confirm(`Купить «${name}» за ${price} ⚡?`)) return;
  try {
    const d = await fetch(`${API}/shop/buy`,{
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({user_id:state.userId, item_id:id})
    }).then(r=>r.json());
    if (d.ok) {
      playSound("buy");
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      showToast(d.message,"success");
      if (_shopData) _shopData.souls = d.souls_left;
      const el = document.getElementById("shopSouls");
      if (el) el.textContent = Math.floor(d.souls_left);
      const hud = document.getElementById("hudSoulsVal");
      if (hud) hud.textContent = Math.floor(d.souls_left);
      setTimeout(loadShop, 400);
    } else { showToast(d.message||"Ошибка","error"); }
  } catch(e) { showToast("Ошибка","error"); }
}
window.buyItem = buyItem;

function openBotShop() {
  tg ? tg.openTelegramLink("https://t.me/CHM_smcbot?start=shop")
     : showToast("Открой в Telegram","info");
}
window.openBotShop = openBotShop;


// ══════════════════════════════════════════════════════════════════════════════
// ── PERSONAL LEADERBOARD ─────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function loadPersonalLeaderboard() {
  if (!state.userId) return;
  try {
    const d = await fetch(`${API}/leaderboard/personal/${state.userId}`).then(r=>r.json());
    _renderPersonalLB(d);
  } catch(e) { console.warn("personal lb:", e); }
}

function _renderPersonalLB(d) {
  const wrap = document.getElementById("leaderboardContent");
  if (!wrap) return;

  const myPos = d.my_position;
  const total = d.total_players;
  const medals = ["🥇","🥈","🥉"];

  const renderRow = (e, highlight=false) => {
    const posLabel = medals[e.position-1] || `#${e.position}`;
    const hollow = e.is_hollow ? ' lb-hollow' : '';
    const me = e.is_me ? ' lb-me' : '';
    return `
    <div class="lb-row${hollow}${me}${highlight?' lb-rival':''}">
      <span class="lb-pos">${posLabel}</span>
      <div class="lb-info">
        <span class="lb-name">${e.name}${e.is_hollow?' <span class="lb-hollow-badge">Hollow</span>':''}</span>
        <span class="lb-meta">Lvl ${e.level} · ${e.xp} XP · 🔥${e.streak}</span>
      </div>
      <span class="lb-xp">${e.xp}</span>
    </div>`;
  };

  const tauntHtml = d.taunt ? `<div class="lb-taunt">${d.taunt}</div>` : '';
  const myBadge = myPos ? `
    <div class="lb-my-pos">
      <span class="lb-my-pos-num">#${myPos}</span>
      <span class="lb-my-pos-lbl">из ${total} трейдеров</span>
    </div>` : '';

  wrap.innerHTML = `
    ${tauntHtml}
    ${myBadge}
    <div class="lb-section-label">Топ-3</div>
    ${(d.top3||[]).map(e=>renderRow(e)).join('')}
    ${(d.around||[]).length && d.my_position > 3 ? `
      <div class="lb-divider">···</div>
      <div class="lb-section-label">Рядом с тобой</div>
      ${d.around.map(e=>renderRow(e, !e.is_me && e.position === d.my_position-1)).join('')}
    ` : ''}`;
}


// ══════════════════════════════════════════════════════════════════════════════
// ── MYSTERY BOX ──────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function showMysteryBox(questId) {
  const modal = document.getElementById("mysteryBoxModal");
  if (!modal) return;
  modal.querySelector(".mb-flask").classList.remove("mb-shake","mb-open");
  modal.querySelector(".mb-reward").classList.add("hidden");
  modal.querySelector(".mb-tap-hint").classList.remove("hidden");
  modal.dataset.questId = questId;
  modal.dataset.opened = "0";
  modal.classList.remove("hidden");
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

async function tapMysteryBox() {
  const modal = document.getElementById("mysteryBoxModal");
  if (!modal || modal.dataset.opened === "1") return;
  modal.dataset.opened = "1";
  const flask = modal.querySelector(".mb-flask");
  const questId = modal.dataset.questId;
  flask.classList.add("mb-shake");
  playSound("catalyst_on");
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("heavy");
  try {
    const d = await fetch(`${API}/mystery-box/open`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, quest_id: questId})
    }).then(r=>r.json());
    setTimeout(() => {
      flask.classList.remove("mb-shake");
      flask.classList.add("mb-open");
      if (d.ok && d.reward) {
        const r = d.reward;
        const rarityColors = {
          legendary:"#fbbf24", epic:"#a78bfa", rare:"#60a5fa", common:"#94a3b8"
        };
        const col = rarityColors[r.rarity] || "#94a3b8";
        const rewardEl = modal.querySelector(".mb-reward");
        rewardEl.innerHTML = `
          <div class="mb-rarity" style="color:${col}">${r.rarity.toUpperCase()}</div>
          <div class="mb-reward-icon">${r.type==="souls"?"💀":r.type==="isotope"?"🧪":r.type==="boost"?"⚡":"✨"}</div>
          <div class="mb-reward-msg" style="color:${col}">${r.message}</div>`;
        rewardEl.classList.remove("hidden");
        modal.querySelector(".mb-tap-hint").classList.add("hidden");
        if (r.rarity==="legendary") playSound("bosswin");
        else if (r.rarity==="epic") playSound("levelup");
        else if (r.rarity==="rare") playSound("questdone");
        else playSound("soulsgain");
        if (tg?.HapticFeedback) {
          if (r.rarity==="legendary") tg.HapticFeedback.notificationOccurred("success");
          else tg.HapticFeedback.impactOccurred("medium");
        }
        if (r.type==="souls" && state.userState) {
          state.userState.souls = (state.userState.souls||0) + r.amount;
          const hud = document.getElementById("hudSoulsVal");
          if (hud) hud.textContent = Math.floor(state.userState.souls);
        }
      }
    }, 800);
  } catch(e) { console.error("mystery box:", e); }
}
window.tapMysteryBox = tapMysteryBox;

function closeMysteryBox() {
  const modal = document.getElementById("mysteryBoxModal");
  if (modal) { modal.classList.add("hidden"); modal.dataset.opened="0"; }
}
window.closeMysteryBox = closeMysteryBox;


// ══════════════════════════════════════════════════════════════════════════════
// ── LIVE SIGNAL BANNER ───────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

let _liveSignalData = null;

async function checkLiveSignal() {
  try {
    const d = await fetch(`${API}/live-signal`).then(r=>r.json());
    if (d.active) {
      _liveSignalData = d;
      _showLiveSignalBanner(d);
    } else {
      _hideLiveSignalBanner();
    }
  } catch(e) {}
}

function _showLiveSignalBanner(d) {
  let banner = document.getElementById("liveSignalBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "liveSignalBanner";
    banner.className = "ls-banner";
    const header = document.querySelector(".app-header, .module-progress-area");
    if (header?.nextSibling) header.parentNode.insertBefore(banner, header.nextSibling);
    else document.body.prepend(banner);
  }
  const stateColors = {
    crash:"#ff4d6d", dump:"#f97316", pump:"#fbbf24",
    rally:"#00e87a", volatile:"#a78bfa", flat:"#64748b", neutral:"#6366f1"
  };
  const col = stateColors[d.market_state] || "#6366f1";
  banner.style.borderColor = col + "55";
  banner.innerHTML = `
    <div class="ls-pulse" style="background:${col}"></div>
    <div class="ls-body">
      <span class="ls-label" style="color:${col}">📡 ЖИВОЙ СИГНАЛ</span>
      <span class="ls-concept">${d.concept}</span>
      <span class="ls-price">BTC $${(d.btc_price||0).toLocaleString()} ${d.price_change_1h>0?'+':''}${d.price_change_1h||0}%</span>
    </div>
    <button class="ls-open-btn" onclick="openLiveSignalLesson()" style="border-color:${col};color:${col}">
      Учиться
    </button>
    <button class="ls-dismiss" onclick="dismissLiveSignal()">✕</button>`;
  banner.classList.remove("hidden");
}

function _hideLiveSignalBanner() {
  const b = document.getElementById("liveSignalBanner");
  if (b) b.classList.add("hidden");
}

async function openLiveSignalLesson() {
  if (!_liveSignalData) return;
  switchTab("lessons");
  setTimeout(() => {
    const lessonKey = _liveSignalData.lesson_key;
    if (typeof openLesson === "function") openLesson(lessonKey);
  }, 300);
  dismissLiveSignal();
}
window.openLiveSignalLesson = openLiveSignalLesson;

async function dismissLiveSignal() {
  _hideLiveSignalBanner();
  if (!state.userId) return;
  try {
    await fetch(`${API}/live-signal/dismiss/${state.userId}`, {method:"POST"});
  } catch(e) {}
}
window.dismissLiveSignal = dismissLiveSignal;


// ══════════════════════════════════════════════════════════════════════════════
// ── BATTLE PASS ──────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function loadBattlePass() {
  if (!state.userId) return;
  try {
    const d = await fetch(`${API}/season/progress/${state.userId}`).then(r=>r.json());
    _renderBattlePass(d);
  } catch(e) { console.warn("bp:", e); }
}

function _renderBattlePass(d) {
  const wrap = document.getElementById("battlePassWrap");
  if (!wrap) return;
  const col = d.season?.accent_color || "#ff4d6d";
  const lvl = d.bp_level || 0;
  const hasClaim = d.claimable_count > 0;
  wrap.innerHTML = `
    <div class="bp-header">
      <div class="bp-header-left">
        <span class="bp-season-name" style="color:${col}">${d.season?.name || "Сезон 1"}</span>
        <span class="bp-days-left">${d.days_left} дней осталось</span>
      </div>
      <div class="bp-level-badge" style="border-color:${col}">
        <span class="bp-lvl-num">${lvl}</span>
        <span class="bp-lvl-lbl">/ 30</span>
      </div>
    </div>
    <div class="bp-xp-bar-wrap">
      <div class="bp-xp-bar-bg">
        <div class="bp-xp-bar-fill" style="width:${d.bp_pct}%;background:${col}"></div>
      </div>
      <div class="bp-xp-info">
        <span>XP до след. уровня: ${d.bp_xp_to_next}</span>
        ${hasClaim ? `<span class="bp-claim-hint" style="color:${col}">${d.claimable_count} наград ждут!</span>` : ''}
      </div>
    </div>
    ${hasClaim ? `
    <div class="bp-claimable-section">
      ${(d.claimable||[]).map(r=>`
        <div class="bp-reward-card ${r.type}" style="border-color:${col}44">
          <span class="bp-rew-level" style="color:${col}">Ур.${r.level}</span>
          <span class="bp-rew-label">${r.label}</span>
          <button class="bp-claim-btn" style="background:${col}" onclick="claimBP(${r.level})">Забрать</button>
        </div>`).join('')}
    </div>` : ''}
    <div class="bp-track" id="bpTrack">
      ${(d.rewards||[]).map(r=>{
        const done = r.level <= lvl;
        const claimed = (d.claimed||[]).includes(r.level);
        return `
          <div class="bp-node ${done?'bp-done':''} ${claimed?'bp-claimed':''}">
            <div class="bp-node-circle" style="${done?`background:${col}`:''}">
              ${claimed?'✓':r.level}
            </div>
            <div class="bp-node-label">${r.label.split(' ').slice(0,2).join(' ')}</div>
          </div>`;
      }).join('')}
    </div>`;
}

async function claimBP(level) {
  try {
    const d = await fetch(`${API}/season/claim`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, level})
    }).then(r=>r.json());
    if (d.ok) {
      playSound("questdone");
      showToast(`🎁 ${d.label}`, "success");
      loadBattlePass();
    } else {
      showToast(d.error||"Ошибка","error");
    }
  } catch(e) { showToast("Ошибка","error"); }
}
window.claimBP = claimBP;


// ══════════════════════════════════════════════════════════════════════════════
// ── REFERRAL ─────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function loadReferral() {
  if (!state.userId) return;
  try {
    const d = await fetch(`${API}/referral/${state.userId}`).then(r=>r.json());
    _renderReferral(d);
  } catch(e) { console.warn("referral:", e); }
}

function _renderReferral(d) {
  const wrap = document.getElementById("referralWrap");
  if (!wrap) return;
  const link = d.ref_link || "";
  wrap.innerHTML = `
    <div class="ref-header">⚗️ Реферальная Алхимия</div>
    <div class="ref-link-box">
      <span class="ref-link-text" id="refLinkText">${link}</span>
      <button class="ref-copy-btn" onclick="copyRefLink('${link.replace(/'/g,"\\'")}')">Скопировать</button>
    </div>
    <button class="ref-share-btn" onclick="shareRefLink('${link.replace(/'/g,"\\'")}')">📤 Поделиться</button>
    <div class="ref-stats">
      <div class="ref-stat">
        <span class="ref-stat-val">${d.total_referrals}</span>
        <span class="ref-stat-lbl">приглашено</span>
      </div>
      <div class="ref-stat">
        <span class="ref-stat-val">${d.souls_earned || 0}</span>
        <span class="ref-stat-lbl">Душ заработано</span>
      </div>
    </div>
    <div class="ref-milestones">
      ${(d.milestones||[]).map(m=>`
        <div class="ref-ms ${m.reached?'ref-ms-done':''}">
          <span class="ref-ms-check">${m.reached?'✓':'○'}</span>
          <span class="ref-ms-count">${m.count} чел.</span>
          <span class="ref-ms-reward">${m.reward}</span>
        </div>`).join('')}
    </div>`;
}

function copyRefLink(link) {
  navigator.clipboard?.writeText(link).then(()=>showToast("Ссылка скопирована ✓","success"))
    .catch(()=>{
      const el=document.getElementById("refLinkText");
      if(el){const r=document.createRange();r.selectNode(el);window.getSelection().removeAllRanges();window.getSelection().addRange(r);}
    });
}
window.copyRefLink = copyRefLink;

function shareRefLink(link) {
  if (tg) {
    const text = encodeURIComponent("Крипто Химия — Souls-like обучение SMC. Присоединяйся:");
    tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`);
  } else {
    copyRefLink(link);
  }
}
window.shareRefLink = shareRefLink;


// ══════════════════════════════════════════════════════════════════════════════
// ── SCHOLAR JOURNAL ──────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function openScholarJournal() {
  const modal = document.getElementById("journalModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  try {
    const d = await fetch(`${API}/scholar-journal/${state.userId}`).then(r=>r.json());
    const body = modal.querySelector(".journal-body");
    if (!body) return;
    const shareText = d.share_text || "";
    body.innerHTML = `
      <div class="journal-card">
        <div class="journal-watermark">⚗️</div>
        <div class="journal-top">
          <div class="journal-academy">CHM Smart Money Academy</div>
          <div class="journal-title">${d.card_title}</div>
          <div class="journal-name">${d.name}</div>
        </div>
        <div class="journal-divider"></div>
        <div class="journal-stats">
          <div class="journal-stat">
            <span class="j-val">${d.level}</span>
            <span class="j-lbl">Уровень</span>
          </div>
          <div class="journal-stat">
            <span class="j-val">${d.modules_completed}</span>
            <span class="j-lbl">Модулей</span>
          </div>
          <div class="journal-stat">
            <span class="j-val">${d.boss_wins}</span>
            <span class="j-lbl">Боссов</span>
          </div>
          <div class="journal-stat">
            <span class="j-val">${d.streak}</span>
            <span class="j-lbl">Стрик</span>
          </div>
        </div>
        <div class="journal-divider"></div>
        <div class="journal-rank">${d.rank}</div>
        <div class="journal-souls">💀 ${(d.souls_total||0).toLocaleString()} Душ накоплено</div>
      </div>
      <button class="journal-share-btn" id="journalShareBtn">📤 Поделиться в Telegram</button>
      <button class="journal-close-btn" onclick="closeJournal()">Закрыть</button>`;
    document.getElementById("journalShareBtn").onclick = () => shareJournal(shareText);
  } catch(e) { console.error("journal:", e); }
}
window.openScholarJournal = openScholarJournal;

function shareJournal(text) {
  if (tg) {
    tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent("https://t.me/CHM_smcbot")}&text=${encodeURIComponent(text)}`);
  } else {
    navigator.clipboard?.writeText(text).then(()=>showToast("Скопировано!","success"));
  }
}
window.shareJournal = shareJournal;

function closeJournal() {
  document.getElementById("journalModal")?.classList.add("hidden");
}
window.closeJournal = closeJournal;


// ══════════════════════════════════════════════════════════════════════════════
// ── CLAN RAID ─────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

async function loadRaid() {
  try {
    const d = await fetch(`${API}/raid/status`).then(r=>r.json());
    _renderRaid(d);
  } catch(e) {}
}

function _renderRaid(d) {
  const wrap = document.getElementById("raidWrap");
  if (!wrap) return;

  if (!d.active) {
    wrap.innerHTML = `
      <div class="raid-inactive">
        <span class="raid-icon">⚔️</span>
        <div>
          <div class="raid-inactive-ttl">Клановый Рейд</div>
          <div class="raid-inactive-sub">Следующий рейд — в понедельник в 10:00 UTC</div>
        </div>
      </div>`;
    return;
  }

  const boss = d.boss || {};
  const hpPct = d.hp_max > 0 ? Math.round(d.hp_current / d.hp_max * 100) : 0;
  const hpCol = hpPct > 50 ? '#00e87a' : hpPct > 25 ? '#f59e0b' : '#ff4d6d';
  const myEntry = d.participants?.[String(state.userId)];
  const alreadyAnswered = myEntry?.answered;

  wrap.innerHTML = `
    <div class="raid-active">
      <div class="raid-boss-header">
        <span class="raid-boss-icon">${boss.icon || '💀'}</span>
        <div>
          <div class="raid-boss-name">РЕЙД: ${boss.name}</div>
          <div class="raid-boss-sub">Атакуй вместе с кланом</div>
        </div>
      </div>
      <div class="raid-hp-section">
        <div class="raid-hp-labels">
          <span>HP Босса</span>
          <span style="color:${hpCol};font-weight:700">${(d.hp_current||0).toLocaleString()} / ${(d.hp_max||0).toLocaleString()}</span>
        </div>
        <div class="raid-hp-bg">
          <div class="raid-hp-fill" style="width:${hpPct}%;background:${hpCol}"></div>
        </div>
      </div>
      ${!alreadyAnswered ? `
      <div class="raid-question-card">
        <div class="raid-q-label">❓ Вопрос для атаки</div>
        <div class="raid-q-text">${boss.question || ''}</div>
        <div class="raid-q-btns">
          <button class="raid-reveal-btn" onclick="_revealRaidAnswer()">Показать ответ</button>
        </div>
        <div class="raid-answer-box hidden" id="raidAnswerBox">
          <div class="raid-ans-text">${boss.answer || ''}</div>
          <div class="raid-confirm-row">
            <span>Ты знал ответ?</span>
            <button class="raid-yes-btn" onclick="submitRaid(true)">✓ Да (+${boss.souls_reward || 0} душ)</button>
            <button class="raid-no-btn"  onclick="submitRaid(false)">✕ Нет</button>
          </div>
        </div>
      </div>` : `
      <div class="raid-done-badge">
        ✓ Ты уже атаковал в этом рейде!
        ${myEntry?.is_correct ? `<br>+${boss.souls_reward || 0} душ получено.` : '<br>Урон всё равно нанесён.'}
      </div>`}
      <div class="raid-participants">
        Участников: ${Object.keys(d.participants || {}).length}
      </div>
    </div>`;
}

function _revealRaidAnswer() {
  const box = document.getElementById("raidAnswerBox");
  if (box) {
    box.classList.remove("hidden");
    const btn = document.querySelector(".raid-reveal-btn");
    if (btn) btn.style.display = "none";
  }
}
window._revealRaidAnswer = _revealRaidAnswer;

async function submitRaid(isCorrect) {
  try {
    const d = await fetch(`${API}/raid/attack`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({user_id: state.userId, is_correct: isCorrect})
    }).then(r=>r.json());
    if (d.ok) {
      playSound(d.boss_defeated ? "bosswin" : isCorrect ? "questdone" : "hit");
      if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred(d.boss_defeated?"heavy":"medium");
      if (d.boss_defeated) showToast("💥 БОСС ПОВЕРЖЕН! Клан победил!", "success");
      else if (isCorrect) showToast(`⚔️ Урон ${d.damage}! +${d.souls_reward} душ`, "success");
      else showToast(`⚔️ Урон ${d.damage} (ошибка). Учись!`, "info");
      setTimeout(loadRaid, 500);
    } else {
      showToast(d.error||"Ошибка","error");
    }
  } catch(e) { showToast("Ошибка","error"); }
}
window.submitRaid = submitRaid;
