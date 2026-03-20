/* ═══════════════════════════════════════════════════════════════════════
   CHM Smart Money Academy — app.js v5.0
   72h Deadlines · SMC Levels · Streak · Penalty Flow · Countdown Timer
   ═══════════════════════════════════════════════════════════════════════ */

// ── CONFIG ────────────────────────────────────────────────────────────────
const API     = "/api";
const tg      = window.Telegram?.WebApp ?? null;
const DEV_UID = 445677777;

// ── GLOBAL STATE ──────────────────────────────────────────────────────────
const state = {
  userId: null,
  userState: null,
  quizData: null,
  currentQuestId: null,
  lessonsMetaCache: {},
  quizStreak: 0,
  countdownInterval: null,
  deadlineInfo: null,
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
    return { id: u.id, username: u.username || null, first_name: u.first_name || null, last_name: u.last_name || null };
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


// ── ONBOARDING ────────────────────────────────────────────────────────────
let obCurrentSlide = 0;
const OB_TOTAL = 3;

function initOnboarding() {
  const overlay = $("#onboardingOverlay");
  if (!overlay || localStorage.getItem("smc_onboarding_done")) return;
  overlay.classList.remove("hidden");
  const nextBtn = $("#ob-next-btn");
  const skipBtn = $("#ob-skip-btn");
  nextBtn.addEventListener("click", () => {
    if (obCurrentSlide < OB_TOTAL - 1) goToSlide(obCurrentSlide + 1);
    else closeOnboarding();
  });
  skipBtn.addEventListener("click", closeOnboarding);
  document.querySelectorAll(".ob-dot").forEach(dot => {
    dot.addEventListener("click", () => goToSlide(parseInt(dot.dataset.dot)));
  });
}

function goToSlide(idx) {
  const slides = document.querySelectorAll(".ob-slide");
  const dots   = document.querySelectorAll(".ob-dot");
  const nextBtn = $("#ob-next-btn");
  slides[obCurrentSlide].classList.add("exit-left");
  slides[obCurrentSlide].classList.remove("active");
  setTimeout(() => slides[obCurrentSlide]?.classList.remove("exit-left"), 400);
  obCurrentSlide = idx;
  slides[idx].classList.add("active");
  dots.forEach((d, i) => d.classList.toggle("active", i === idx));
  nextBtn.textContent = idx === OB_TOTAL - 1 ? "Начать →" : "Далее";
}

function closeOnboarding() {
  const overlay = $("#onboardingOverlay");
  if (overlay) { overlay.style.animation = "fadeOut 0.3s ease forwards"; setTimeout(() => overlay.classList.add("hidden"), 300); }
  localStorage.setItem("smc_onboarding_done", "1");
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
  if (name === "leaderboard")  loadLeaderboard();
  if (name === "pet")          loadPet();
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
  state.userState = s;
  const rankName = s.rank || "Наблюдатель рынка";
  const lvlInfo  = getLevelInfo(s.xp || 0);

  $("#userName").textContent = s.name || "Трейдер";
  $("#userXP").textContent   = s.xp ?? 0;
  $("#userLvl").textContent  = s.level ?? 1;
  $("#moduleName").textContent = `Модуль ${(s.module_index ?? 0) + 1}`;

  // Title
  const titleEl = $("#userTitle");
  if (titleEl) titleEl.textContent = s.current_title || "Ликвидность";

  // Souls HUD from user state
  if (s.souls !== undefined) {
    const soulsEl = $("#soulsCount");
    if (soulsEl) soulsEl.textContent = s.souls;
  }

  // Estus flasks
  updateEstusHUD(s.estus_flasks ?? 3, s.estus_max ?? 3);

  const rankWrap = $("#rankIconWrap");
  if (rankWrap) rankWrap.innerHTML = getRankSVG(rankName);

  // Streak badge
  const streak = s.streak || 0;
  const streakBadge = $("#streakBadge");
  const streakCount = $("#streakCount");
  if (streakBadge && streakCount) {
    streakCount.textContent = streak;
    streakBadge.classList.toggle("hidden", streak < 2);
    if (streak >= 7) streakBadge.classList.add("streak-hot");
    else streakBadge.classList.remove("streak-hot");
  }
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
  container.innerHTML = "";
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

    card.append(headerRow, badges, desc, btn);
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
      body: JSON.stringify({ user_id: state.userId, quest_id: questId, question_index: current, is_correct: isCorrect }),
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
    // Cipher stat reaction: notify user and refresh pet stats
    setTimeout(() => {
      showToast("⚡ Cipher получил энергию! Резонанс ↑", "success");
      loadPet();
    }, 2200);
  } else {
    showResult("⚠️", "ГИПОТЕЗА НЕ ПОДТВЕРЖДЕНА", `Результат: ${data.correct}/${data.total} (${data.score}%)\nНужно набрать ${data.required}%`, null);
    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
    // Cipher distress reaction
    setTimeout(() => showToast("⚠️ Cipher теряет стабильность... пройди протокол заново", "error"), 1200);
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
      user_id:  state.userId,
      quest_id: state.currentQuestId,
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
  try {
    const res = await fetch(`${API}/user/${state.userId}`);
    const s   = await res.json();
    renderHeader(s);
  } catch (e) {}
}
window.showDeadlineExpiredScreen = showDeadlineExpiredScreen;

// ── INITIAL LOAD ──────────────────────────────────────────────────────────
async function init() {
  initOnboarding();

  const info = getUserInfo();
  state.userId = info.id;

  try {
    const initRes = await fetch(`${API}/user/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: info.id, username: info.username, first_name: info.first_name, last_name: info.last_name }),
    });
    const initData = await initRes.json();

    const [userRes, modulesRes, questsRes, metaRes, lbRes] = await Promise.all([
      fetch(`${API}/user/${info.id}`),
      fetch(`${API}/modules`),
      fetch(`${API}/quests/${info.id}`),
      fetch(`${API}/lessons/meta`),
      fetch(`${API}/leaderboard`),
    ]);

    const [userData, modulesData, questsData, metaData, lbData] = await Promise.all([
      userRes.json(), modulesRes.json(), questsRes.json(), metaRes.json(), lbRes.json(),
    ]);

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

    // Evolution badge from init response
    if (initData.evolution) renderEvolution(initData.evolution);

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

  } catch (e) {
    console.error("init error:", e);
    showToast("Ошибка загрузки данных", "error");
  }
}

// ── PET SYSTEM ────────────────────────────────────────────────────────────

const PET_HINT_BY_STATE = {
  idle:    "Активируй Cipher — тапай для резонанса 🧬",
  happy:   "Cipher резонирует! Проходи протоколы для восстановления энергии ⚡",
  excited: "CRITICAL RESONANCE! Cipher в состоянии возбуждения! 💠",
  hungry:  "ALERT: Энергетический субстрат критически низкий 😢 Пройди урок!",
  sick:    "ALERT: Клеточная целостность нарушена 😷 Срочно пройди квиз!",
};

let _petTapCooldown = false;
let _petComboTimer  = null;

async function loadPet() {
  if (!state.userId) return;
  try {
    const [petRes, evoRes] = await Promise.all([
      fetch(`${API}/pet/${state.userId}`),
      fetch(`${API}/pet/evolution/${state.userId}`),
    ]);
    const [petData, evoData] = await Promise.all([petRes.json(), evoRes.json()]);
    if (petData.ok) renderPet(petData);
    if (evoData.ok) renderEvolution(evoData);
  } catch (e) { console.error("loadPet:", e); }
}

function renderPet(data) {
  // Stats
  _setPetStat("Hunger",    data.hunger,    data.hunger);
  _setPetStat("Happiness", data.happiness, data.happiness);
  _setPetStat("Health",    data.health,    data.health);

  // Level & XP
  const lvl  = data.pet_level  || 1;
  const xpC  = data.pet_xp     || 0;
  const xpCL = data.current_level_xp || 0;
  const xpNL = data.next_level_xp;
  const pct  = xpNL ? Math.min(100, Math.round(((xpC - xpCL) / (xpNL - xpCL)) * 100)) : 100;

  const lvlBadge = document.getElementById("petLevelBadge");
  if (lvlBadge) lvlBadge.textContent = `Ст. ${lvl}`;
  const xpCurEl = document.getElementById("petXpCurrent");
  if (xpCurEl) xpCurEl.textContent = xpC;
  const xpNxtEl = document.getElementById("petXpNext");
  if (xpNxtEl) xpNxtEl.textContent = xpNL ?? "MAX";
  const xpFill = document.getElementById("petXpFill");
  if (xpFill) xpFill.style.width = pct + "%";

  // Coins
  const coinsEl = document.getElementById("petCoins");
  if (coinsEl) coinsEl.textContent = data.coins || 0;

  // Fox visual state
  const fox = document.getElementById("petFox");
  if (fox) {
    ["idle","happy","excited","hungry","sick"].forEach(s => fox.classList.remove(`pet-fox--${s}`));
    fox.classList.add(`pet-fox--${data.visual_state || "idle"}`);
  }

  // State-change toast (show once on transition, not every render)
  const newState = data.visual_state || "idle";
  if (newState !== (renderPet._lastState || "idle")) {
    if (newState === "excited") showToast("Критический резонанс!", "success", "⚡");
    else if (newState === "hungry") showToast("Энергия критически низкая", "error", "⚠️", "Пройди урок");
    else if (newState === "sick")   showToast("Клеточная целостность нарушена", "error", "🧬", "Пройди квиз");
    renderPet._lastState = newState;
  }

  // Aura color based on state
  const aura = document.getElementById("petAura");
  if (aura) {
    const auraColors = {
      idle:    "rgba(0,212,255,0.18)",
      happy:   "rgba(0,255,200,0.22)",
      excited: "rgba(0,255,255,0.32)",
      hungry:  "rgba(239,68,68,0.20)",
      sick:    "rgba(100,120,140,0.18)",
    };
    const c = auraColors[data.visual_state] || auraColors.idle;
    aura.style.background = `radial-gradient(circle, ${c} 0%, transparent 70%)`;
  }

  // Low-stat screen vignette
  const critLow = data.health < 20 || data.hunger < 20;
  let vignette = document.getElementById("statVignette");
  if (critLow && !vignette) {
    vignette = document.createElement("div");
    vignette.id = "statVignette";
    vignette.className = "screen-vignette-red";
    document.body.appendChild(vignette);
  } else if (!critLow && vignette) {
    vignette.remove();
  }
}

function _setPetStat(statName, value, rawVal) {
  const pct = Math.max(0, Math.min(100, Math.round(rawVal)));
  const valEl  = document.getElementById(`pet${statName}`);
  const fillEl = document.getElementById(`pet${statName}Bar`);
  if (valEl)  valEl.textContent = pct;
  if (fillEl) {
    fillEl.style.width = pct + "%";
    fillEl.classList.toggle("pet-stat-fill--low", pct < 25);
  }
}

async function onPetTap(e) {
  if (_petTapCooldown) return;
  _petTapCooldown = true;
  setTimeout(() => { _petTapCooldown = false; }, 200);

  // Haptic
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");

  // Tap squish animation
  const fox = document.getElementById("petFox");
  if (fox) {
    fox.classList.remove("pet-fox--tapping");
    void fox.offsetWidth; // reflow to restart
    fox.classList.add("pet-fox--tapping");
    setTimeout(() => fox.classList.remove("pet-fox--tapping"), 320);
  }

  // Compute tap position for floating reward
  const stage = document.getElementById("petStage");
  let tapX = 50, tapY = 40;
  if (e && stage) {
    const rect = stage.getBoundingClientRect();
    tapX = ((e.clientX - rect.left) / rect.width  * 100);
    tapY = ((e.clientY - rect.top)  / rect.height * 100);
  }

  try {
    const res  = await fetch(`${API}/pet/tap`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ user_id: state.userId }),
    });
    const data = await res.json();
    if (!data.ok) return;

    // Floating DATA reward
    _spawnFloatReward(`+${data.data_awarded || 2} Ð`, tapX, tapY,
      data.combo > 2 ? "float-reward--combo" : "float-reward--data");

    // Combo badge
    if (data.combo > 1) _showComboBadge(data.combo);

    // ── Souls system: show souls gained and update HUD ───────────────────
    if (data.souls_earned > 0) {
      spawnSoulParticle(`+${data.souls_earned} ⚡`, true);
      const soulsEl = document.getElementById("soulsCount");
      if (soulsEl) {
        soulsEl.textContent = data.total_souls;
        soulsEl.classList.remove("souls-gaining");
        void soulsEl.offsetWidth;
        soulsEl.classList.add("souls-gaining");
      }
    }

    // Update DATA counter with bump animation
    const coinsEl = document.getElementById("petCoins");
    if (coinsEl) {
      coinsEl.textContent = data.total_data ?? data.coins ?? 0;
      coinsEl.classList.remove("data-counter", "bump");
      void coinsEl.offsetWidth;
      coinsEl.classList.add("data-counter", "bump");
    }

    // Coins milestone bonus
    if (data.coins_earned > 0) {
      _spawnCoinBurst(data.coins_earned);
      showToast(`Milestone! +${data.coins_earned} Ð bonus`, "success", "🏆");
    }

    // Level up
    if (data.level_up) {
      _triggerPetLevelUp(data.pet_level);
    }

    // Update UI incrementally
    _setPetStat("Hunger",    data.hunger,    data.hunger);
    _setPetStat("Happiness", data.happiness, data.happiness);
    _setPetStat("Health",    data.health,    data.health);

    const lvlBadge = document.getElementById("petLevelBadge");
    if (lvlBadge) lvlBadge.textContent = `Ст. ${data.pet_level}`;

    const xpCurEl = document.getElementById("petXpCurrent");
    if (xpCurEl) xpCurEl.textContent = data.pet_xp;

    const xpNL = data.next_level_xp;
    const xpCL = data.current_level_xp || 0;
    const xpC  = data.pet_xp;
    const pct  = xpNL ? Math.min(100, Math.round(((xpC - xpCL) / (xpNL - xpCL)) * 100)) : 100;
    const xpFill = document.getElementById("petXpFill");
    if (xpFill) xpFill.style.width = pct + "%";

    // Visual state
    if (fox) {
      ["idle","happy","excited","hungry","sick"].forEach(s => fox.classList.remove(`pet-fox--${s}`));
      fox.classList.add(`pet-fox--${data.visual_state || "idle"}`);
    }

  } catch (err) { console.error("pet tap:", err); }
}
window.onPetTap = onPetTap;

function _spawnFloatReward(text, pctX, pctY, extraClass) {
  const container = document.getElementById("petFloatRewards");
  if (!container) return;
  const el = document.createElement("div");
  el.className = "float-reward" + (extraClass ? " " + extraClass : "");
  el.textContent = text;
  el.style.left   = (pctX - 10) + "%";
  el.style.top    = pctY + "%";
  container.appendChild(el);
  setTimeout(() => el.remove(), 950);
}

function _showComboBadge(combo) {
  const el = document.getElementById("petCombo");
  const tx = document.getElementById("petComboText");
  if (!el || !tx) return;
  tx.textContent = `x${combo} РЕЗОНАНС!`;
  el.style.display = "block";
  clearTimeout(_petComboTimer);
  _petComboTimer = setTimeout(() => { if (el) el.style.display = "none"; }, 1800);
}

function _triggerPetLevelUp(newLevel) {
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  showToast(`Cipher эволюционировал! Стадия ${newLevel}`, "success", "🧬");
  const flash = document.createElement("div");
  flash.className = "pet-level-up-flash";
  document.body.appendChild(flash);
  setTimeout(() => flash.remove(), 850);
}

function _spawnCoinBurst(count) {
  const fox = document.getElementById("petFox");
  if (!fox) return;
  const rect = fox.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top  + rect.height / 2;
  const num = Math.min(count, 8);
  for (let i = 0; i < num; i++) {
    const el = document.createElement("div");
    el.className = "coin-particle";
    el.textContent = "Ð";
    el.style.left = cx + "px";
    el.style.top  = cy + "px";
    const angle = (360 / num) * i;
    const dist  = 60 + Math.random() * 40;
    const tx = Math.cos(angle * Math.PI / 180) * dist;
    const ty = Math.sin(angle * Math.PI / 180) * dist - 40;
    el.style.setProperty("--tx", `translate(${tx}px,${ty}px)`);
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 950);
  }
}

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

// Hook fever/frenzy + ripple + flash into existing onPetTap
const _origOnPetTap = onPetTap;
window.onPetTap = async function(e) {
  _trackTapVelocity();
  _spawnTapRipple(e, document.getElementById("petStage"));
  _spawnScreenFlash();
  await _origOnPetTap(e);
};

// Override float reward to use combo color
const _origSpawnFloat = _spawnFloatReward;
function _spawnFloatRewardColored(text, px, py, combo) {
  const container = document.getElementById("petFloatRewards");
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

  // Price label
  const priceEl = document.getElementById("hbPrice");
  if (priceEl && data.btc_price) {
    priceEl.textContent = `$${data.btc_price.toLocaleString("en-US", {maximumFractionDigits: 0})}`;
  }

  // Change badge
  const chEl = document.getElementById("hbChange");
  if (chEl && data.price_change_1h != null) {
    const ch = data.price_change_1h;
    chEl.textContent = (ch >= 0 ? "+" : "") + ch.toFixed(2) + "%";
    chEl.className = "btc-change " + (ch >= 0 ? "up" : "down");
  }

  // State label removed — market state shown visually through Cipher color

  // Dot color
  const dot = document.getElementById("hbDot");
  if (dot) dot.style.background = mood.aura || "#10b981";

  // Pulse speed (volatility → speed)
  _pulseSpeed = mood.pulse_speed || 1.0;

  // Update fox visual state based on market if pet tab active
  const fox = document.getElementById("petFox");
  if (fox && document.getElementById("tab-pet")?.classList.contains("active")) {
    const mv = mood.visual || "idle";
    // Only override if market state is stronger than current
    if (["sick","excited"].includes(mv)) {
      ["idle","happy","excited","hungry","sick"].forEach(s => fox.classList.remove(`pet-fox--${s}`));
      fox.classList.add(`pet-fox--${mv}`);
    }
  }

  // Update aura color
  const aura = document.getElementById("petAura");
  if (aura && mood.aura) {
    aura.style.background = `radial-gradient(circle, ${mood.aura}30 0%, transparent 70%)`;
  }

  // BTC market color theme on Cipher — visual-only, no text label
  const petFox = document.getElementById("petFox");
  if (petFox && data.price_change_1h != null) {
    const ch = data.price_change_1h;
    petFox.classList.remove("cipher-bull-market", "cipher-bear-market");
    if (ch >= 2) {
      petFox.classList.add("cipher-bull-market");
    } else if (ch <= -2) {
      petFox.classList.add("cipher-bear-market");
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
      resEl.innerHTML = `✅ <strong>ГИПОТЕЗА ПОДТВЕРЖДЕНА!</strong> Cipher пробуждается! +${r.coins_earned} Ð DATA`;
      _spawnCoinBurst(r.coins_earned);
      // Refresh pet stats
      setTimeout(loadPet, 800);
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

function renderEvolution(evo) {
  if (!evo) return;
  const info = evo.info || {};
  const el   = document.getElementById("evoEmoji");
  if (el) el.textContent = info.emoji || "🧬";
  const nm = document.getElementById("evoName");
  if (nm) nm.textContent = info.name || "Cell Cipher";
  const st = document.getElementById("evoStage");
  if (st) st.textContent = `Ст.${evo.stage || 1}`;
  if (evo.evolved) {
    setTimeout(() => _showEvolutionModal(evo), 800);
  }
}

async function showEvolutionInfo() {
  if (!state.userId) return;
  try {
    const res  = await fetch(`${API}/pet/evolution/${state.userId}`);
    const data = await res.json();
    _renderEvolutionStagesList(data);
    openModal("evolutionModal");
  } catch (e) { console.warn("evo info:", e); }
}
window.showEvolutionInfo = showEvolutionInfo;

function _showEvolutionModal(evo) {
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  const info = evo.info || {};
  document.getElementById("evoEmojiBig").textContent   = info.emoji || "🧬";
  document.getElementById("evoModalTitle").textContent = "ТРАНСФОРМАЦИЯ!";
  document.getElementById("evoModalName").textContent  = info.name || "";
  _renderEvolutionStagesList(evo);
  _spawnEvolutionParticles();
  openModal("evolutionModal");
}

function _renderEvolutionStagesList(evo) {
  const listEl = document.getElementById("evoStagesList");
  if (!listEl) return;
  const stages = evo.all_stages || [];
  const current = evo.stage || 1;
  listEl.innerHTML = stages.map(s => {
    let cls = "evo-stage-row";
    if (s.stage < current) cls += " done";
    if (s.stage === current) cls += " current";
    return `<div class="${cls}">
      <span class="evo-stage-emoji">${s.emoji}</span>
      <span><strong>${s.name}</strong> — ${s.req}</span>
      ${s.stage === current ? "<span style='margin-left:auto'>← Сейчас</span>" : ""}
      ${s.stage < current ? "<span style='margin-left:auto'>✓</span>" : ""}
    </div>`;
  }).join("");
}

function _spawnEvolutionParticles() {
  const container = document.getElementById("evoParticles");
  if (!container) return;
  container.innerHTML = "";
  const emojis = ["🧬","⚡","💠","🌑","💎","✨","〜"];
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
  const soulsEl = document.getElementById("soulsCount");
  if (soulsEl) soulsEl.textContent = s.souls ?? 0;
  updateEstusHUD(s.estus_flasks ?? 3, s.estus_max ?? 3);
  // Title
  const titleEl = document.getElementById("userTitle");
  if (titleEl && s.current_title) titleEl.textContent = s.current_title;
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

// ── BTN START ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  init();
  initChartLightbox();

  document.getElementById("btn-start")?.addEventListener("click", () => {
    switchTab("lessons");
    setTimeout(() => {
      const firstOpen = document.querySelector(".module-card.open .lesson-item");
      if (firstOpen) firstOpen.click();
    }, 200);
  });
});
