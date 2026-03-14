// ── DOM refs ──
const form = document.getElementById("meaning-form");
const runBtn = document.getElementById("run-btn");
const sampleBtn = document.getElementById("sample-btn");
const statusEl = document.getElementById("status");
const chipContainer = document.getElementById("message-type-chips");
const contentEl = document.getElementById("content");

const loadingStage = document.getElementById("loading-stage");
const loadingText = document.getElementById("loading-text");
const loadingAvatars = document.getElementById("loading-avatars");
const loadingProgressWrap = document.getElementById("loading-progress-wrap");
const loadingProgressBar = document.getElementById("loading-progress-bar");
const skeletonState = document.getElementById("skeleton-state");

const resultsWrap = document.getElementById("results-wrap");
const resultsHeader = document.getElementById("results-header");
const statusPill = document.getElementById("status-pill");
const dynamicHeadline = document.getElementById("dynamic-headline");
const submittedMessage = document.getElementById("submitted-message");
const outlierBanner = document.getElementById("outlier-banner");
const signalCardsRoot = document.getElementById("signal-cards");
const mapRoot = document.getElementById("map-root");
const personaGrid = document.getElementById("persona-grid");
const riskList = document.getElementById("risk-list");

const fixDrawer = document.getElementById("fix-drawer");
const fixDrawerOverlay = document.getElementById("fix-drawer-overlay");
const drawerClose = document.getElementById("drawer-close");
const drawerOriginal = document.getElementById("drawer-original");
const drawerRewrite = document.getElementById("drawer-rewrite");
const drawerCopy = document.getElementById("drawer-copy");
const drawerUse = document.getElementById("drawer-use");

const historyPanel = document.getElementById("history-panel");
const historyToggle = document.getElementById("history-toggle");
const historyCount = document.getElementById("history-count");
const historyList = document.getElementById("history-list");
const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");

const SIGNALS = ["clarity", "trust", "hype", "confusion", "credibility"];
const PERSONA_COLORS = ["#1D9E75", "#378ADD", "#BA7517", "#993C1D", "#A32D2D"];

let lastMapPoints = [];
let lastResult = null;
let expandedCard = null;

// ── Utilities ──
function setStatus(msg, type = "ok") { statusEl.textContent = msg; statusEl.classList.toggle("error", type === "error"); }
function fmt(v) { return `${Number(v).toFixed(1)}%`; }
function titleCase(v) { return v.charAt(0).toUpperCase() + v.slice(1); }
function abbr(name) { return name.split(/[\s-]+/).map(w => w[0]).join("").slice(0, 3).toUpperCase(); }
function pColor(name) { let h = 0; for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0; return PERSONA_COLORS[Math.abs(h) % PERSONA_COLORS.length]; }
function tagClass(val) { return val > 60 ? "tag-green" : val >= 40 ? "tag-amber" : "tag-red"; }
function trustBarClass(val) { return val > 60 ? "bar-green" : val >= 35 ? "bar-amber" : "bar-red"; }
function chipSeverity(val) { return val < 35 ? "chip-danger" : val <= 60 ? "chip-warning" : "chip-info"; }
function chipLabel(key, val) { return val < 35 ? `Low ${key}` : val > 65 ? `High ${key}` : titleCase(key); }
function svgEl(tag) { return document.createElementNS("http://www.w3.org/2000/svg", tag); }
function makeLine(x1, y1, x2, y2, cls) { const l = svgEl("line"); l.setAttribute("x1", x1); l.setAttribute("y1", y1); l.setAttribute("x2", x2); l.setAttribute("y2", y2); l.setAttribute("class", cls); return l; }
function scale(v, d0, d1, r0, r1) { return r0 + ((v - d0) / (d1 - d0)) * (r1 - r0); }
function getSelectedType() { const s = chipContainer.querySelector(".chip.selected"); return s ? s.dataset.value : "startup_pitch"; }
function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

function clearResults() {
  signalCardsRoot.innerHTML = "";
  mapRoot.innerHTML = "";
  personaGrid.innerHTML = "";
  riskList.innerHTML = "";
  outlierBanner.innerHTML = "";
  outlierBanner.classList.add("hidden");
  resultsWrap.classList.add("hidden");
  resultsWrap.querySelectorAll(".reveal-section").forEach(s => s.classList.remove("revealed"));
}

// ── Chip interaction (item 7) ──
chipContainer.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  chipContainer.querySelectorAll(".chip").forEach(c => c.classList.remove("selected"));
  chip.classList.add("selected");
  // Brief flash on persona section to signal results would change
  personaGrid.style.opacity = "0.4";
  setTimeout(() => { personaGrid.style.opacity = "1"; }, 300);
});

// ══════════════════════════════════════════════
// ITEM 1: Cinematic loading flow
// ══════════════════════════════════════════════
async function cinematicReveal(result) {
  const hasOutlier = result.interpretations.some(i => i.outlier);
  const personas = result.personas;

  // Show loading stage
  skeletonState.classList.add("hidden");
  loadingStage.classList.remove("hidden");

  // Phase 1: Generating personas (0–1.2s)
  loadingText.textContent = "Generating audience personas...";
  loadingText.classList.remove("danger");
  loadingAvatars.innerHTML = "";
  loadingProgressWrap.classList.add("hidden");
  loadingProgressBar.style.width = "0";

  personas.forEach((p, i) => {
    const av = document.createElement("div");
    av.className = "loading-avatar";
    av.style.background = pColor(p.name);
    av.textContent = abbr(p.name);
    loadingAvatars.appendChild(av);
    setTimeout(() => av.classList.add("visible"), 150 * (i + 1));
  });
  await wait(1200);

  // Phase 2: Interpreting (1.2–2.8s)
  loadingText.textContent = "Running interpretation agents...";
  loadingProgressWrap.classList.remove("hidden");
  requestAnimationFrame(() => { loadingProgressBar.style.width = "80%"; });
  loadingAvatars.querySelectorAll(".loading-avatar").forEach((av, i) => {
    setTimeout(() => { av.classList.add("thinking"); setTimeout(() => av.classList.remove("thinking"), 400); }, i * 200);
  });
  await wait(1600);

  // Phase 3: Divergence detected (2.8–3.5s)
  if (hasOutlier) {
    loadingText.textContent = "Divergence detected";
    loadingText.classList.add("danger");
    loadingProgressBar.style.width = "100%";
    await wait(700);
  } else {
    loadingProgressBar.style.width = "100%";
    await wait(300);
  }

  // Hide loading, show results
  loadingStage.classList.add("hidden");

  // Render all content (hidden)
  renderAllSections(result);
  resultsWrap.classList.remove("hidden");

  // Phase 4: Staggered reveal
  const sections = resultsWrap.querySelectorAll(".reveal-section");
  for (let i = 0; i < sections.length; i++) {
    await wait(80);
    sections[i].classList.add("revealed");
  }

  // Animate map dots
  animateMapDots();
}

function animateMapDots() {
  const dots = mapRoot.querySelectorAll(".point");
  dots.forEach((dot, i) => {
    dot.style.opacity = "0";
    setTimeout(() => {
      dot.style.opacity = "1";
      dot.classList.add("animate-in");
      // Outlier pulse ring
      if (dot.classList.contains("outlier")) {
        const cx = dot.querySelector("circle").getAttribute("cx");
        const cy = dot.querySelector("circle").getAttribute("cy");
        const ring = svgEl("circle");
        ring.setAttribute("cx", cx);
        ring.setAttribute("cy", cy);
        ring.setAttribute("r", "0");
        ring.setAttribute("class", "pulse-ring");
        ring.setAttribute("fill", "none");
        ring.setAttribute("stroke", "var(--color-danger)");
        ring.setAttribute("stroke-width", "2");
        ring.setAttribute("opacity", "0.7");
        dot.parentNode.appendChild(ring);
      }
    }, 300 + i * 300);
  });
}

// ══════════════════════════════════════════════
// Render all sections (called before reveal)
// ══════════════════════════════════════════════
function renderAllSections(result) {
  lastResult = result;
  renderHeader(result);
  renderOutlierBanner(result);
  renderSignalCards(result.summary, result.interpretations);
  renderMap(result.map_points || []);
  renderPersonas(result);
  renderRisks(result.summary);
}

// ── Results header ──
function renderHeader(result) {
  const n = result.personas.length;
  const div = result.summary.divergence_score;
  statusPill.textContent = `${n} personas mapped`;
  dynamicHeadline.textContent = div > 15 ? "Your audience is split." : div < 5 ? "Strong consensus." : "Mostly aligned, with outliers.";
  submittedMessage.textContent = result.input_echo.content;
}

// ══════════════════════════════════════════════
// ITEM 2: Outlier alert
// ══════════════════════════════════════════════
function renderOutlierBanner(result) {
  const outliers = result.interpretations.filter(i => i.outlier);
  if (!outliers.length) { outlierBanner.classList.add("hidden"); return; }
  const o = outliers[0];
  const quote = o.quote || o.interpretation;
  const chips = SIGNALS.map(s => {
    const v = Math.round(o.signals[s]);
    return `<span class="outlier-chip ${chipSeverity(v)}">${chipLabel(s, v)}</span>`;
  }).join("");

  outlierBanner.innerHTML = `
    <p class="outlier-label">Critical outlier</p>
    <p class="outlier-monologue">"${quote}"</p>
    <p class="outlier-meta">${o.persona.name} &middot; ${fmt(o.signals.trust)} trust &middot; ${fmt(o.persona.share * 100)} share</p>
    <div class="outlier-chips">${chips}</div>
  `;
  outlierBanner.classList.remove("hidden");
}

// ══════════════════════════════════════════════
// ITEM 6: Signal cards with visual encoding
// ══════════════════════════════════════════════
function renderSignalCards(summary, interpretations) {
  signalCardsRoot.innerHTML = "";

  let lowestTrust = null, ltv = 101;
  interpretations.forEach(i => { if (i.signals.trust < ltv) { ltv = i.signals.trust; lowestTrust = i; } });

  // Alignment card with donut
  const alignVal = summary.alignment_score;
  const circumference = Math.PI * 2 * 14;
  const dashOffset = circumference - (alignVal / 100) * circumference;

  const divColor = summary.divergence_score > 25 ? "color-danger" : summary.divergence_score > 10 ? "color-warning" : "color-success";

  const cards = [
    {
      label: "Alignment",
      value: fmt(alignVal),
      color: "color-success",
      subtitle: `${fmt(alignVal)} of personas read this similarly`,
      extra: `<div class="donut-wrap"><svg class="donut-svg" viewBox="0 0 36 36"><circle class="donut-bg" cx="18" cy="18" r="14"/><circle class="donut-fill" cx="18" cy="18" r="14" stroke-dasharray="${circumference}" stroke-dashoffset="${dashOffset}"/></svg></div>`,
    },
    {
      label: "Divergence",
      value: fmt(summary.divergence_score),
      color: divColor,
      subtitle: `${summary.top_confusion_personas.length} personas interpret this very differently`,
      extra: "",
    },
    {
      label: "Lowest Trust",
      value: lowestTrust ? lowestTrust.persona.name : "n/a",
      color: "color-danger",
      subtitle: lowestTrust ? `${fmt(ltv)} trust` : "",
      extra: "",
    },
  ];

  cards.forEach(c => {
    const el = document.createElement("article");
    el.className = "signal-card";
    el.innerHTML = `
      <div class="signal-card-top">${c.extra}<div><p class="signal-card-label">${c.label}</p><p class="signal-card-value ${c.color}">${c.value}</p></div></div>
      <p class="signal-card-subtitle">${c.subtitle}</p>
    `;
    signalCardsRoot.appendChild(el);
  });
}

// ══════════════════════════════════════════════
// ITEM 4: Interpretation map — full width hero
// ══════════════════════════════════════════════
function renderMap(points) {
  lastMapPoints = points;
  const width = mapRoot.clientWidth || 700;
  const height = 440;
  const pad = 44;

  mapRoot.innerHTML = "";
  const svg = svgEl("svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "map-svg");

  const hw = width / 2, hh = height / 2;

  // Quadrant bgs
  [
    { x: hw, y: 0, w: hw, h: hh, fill: "rgba(29,158,117,0.07)" },
    { x: 0, y: hh, w: hw, h: hh, fill: "rgba(239,68,68,0.06)" },
    { x: 0, y: 0, w: hw, h: hh, fill: "rgba(100,120,140,0.04)" },
    { x: hw, y: hh, w: hw, h: hh, fill: "rgba(100,120,140,0.04)" },
  ].forEach(q => {
    const r = svgEl("rect");
    r.setAttribute("x", q.x); r.setAttribute("y", q.y); r.setAttribute("width", q.w); r.setAttribute("height", q.h); r.setAttribute("fill", q.fill);
    svg.appendChild(r);
  });

  // Quadrant labels
  [
    { x: hw + 8, y: 18, text: "High trust + credibility" },
    { x: 8, y: hh + 18, text: "Low trust + confused" },
    { x: 8, y: 18, text: "High hype, low trust" },
    { x: hw + 8, y: hh + 18, text: "Skeptical but engaged" },
  ].forEach(l => { const t = svgEl("text"); t.setAttribute("x", l.x); t.setAttribute("y", l.y); t.setAttribute("class", "quadrant-label"); t.textContent = l.text; svg.appendChild(t); });

  // Grid + axis
  for (let i = 1; i < 4; i++) { svg.appendChild(makeLine((width/4)*i, 0, (width/4)*i, height, "grid-line")); svg.appendChild(makeLine(0, (height/4)*i, width, (height/4)*i, "grid-line")); }
  svg.appendChild(makeLine(hw, 0, hw, height, "axis-line"));
  svg.appendChild(makeLine(0, hh, width, hh, "axis-line"));

  // Axis labels
  const xl = svgEl("text"); xl.setAttribute("x", width - pad); xl.setAttribute("y", hh - 8); xl.setAttribute("class", "axis-label"); xl.setAttribute("text-anchor", "end"); xl.textContent = "Trust \u2192"; svg.appendChild(xl);
  const yl = svgEl("text"); yl.setAttribute("x", hw + 8); yl.setAttribute("y", pad - 12); yl.setAttribute("class", "axis-label"); yl.textContent = "Credibility \u2191"; svg.appendChild(yl);

  // Cluster ellipse
  const aligned = points.filter(p => !p.outlier);
  const outliers = points.filter(p => p.outlier);
  let cx = 0, cy = 0;
  if (aligned.length) {
    aligned.forEach(p => { cx += scale(p.x, -1, 1, pad, width - pad); cy += scale(p.y, -1, 1, height - pad, pad); });
    cx /= aligned.length; cy /= aligned.length;
    let maxDx = 0, maxDy = 0;
    aligned.forEach(p => { const px = scale(p.x, -1, 1, pad, width - pad); const py = scale(p.y, -1, 1, height - pad, pad); maxDx = Math.max(maxDx, Math.abs(px - cx)); maxDy = Math.max(maxDy, Math.abs(py - cy)); });
    const rx = Math.max(40, maxDx + 30), ry = Math.max(30, maxDy + 25);
    const el = svgEl("ellipse"); el.setAttribute("cx", cx); el.setAttribute("cy", cy); el.setAttribute("rx", rx); el.setAttribute("ry", ry); el.setAttribute("class", "cluster-ellipse"); svg.appendChild(el);
    const share = Math.round(aligned.reduce((s, p) => s + p.audience_share, 0) * 100);
    const cl = svgEl("text"); cl.setAttribute("x", cx); cl.setAttribute("y", cy - ry - 6); cl.setAttribute("class", "cluster-label"); cl.setAttribute("text-anchor", "middle"); cl.textContent = `${share}% cluster here`; svg.appendChild(cl);
    outliers.forEach(p => { const px = scale(p.x, -1, 1, pad, width - pad); const py = scale(p.y, -1, 1, height - pad, pad); svg.appendChild(makeLine(px, py, cx, cy, "outlier-connector")); });
  }

  // Dots
  points.forEach((pt) => {
    const x = scale(pt.x, -1, 1, pad, width - pad);
    const y = scale(pt.y, -1, 1, height - pad, pad);
    const r = pt.outlier ? 18 : Math.max(12, Math.min(22, 13 + pt.audience_share * 28));
    const color = pColor(pt.persona_name);
    const g = svgEl("g"); g.setAttribute("class", "point" + (pt.outlier ? " outlier" : "")); g.dataset.persona = pt.persona_name;
    const circle = svgEl("circle"); circle.setAttribute("cx", x); circle.setAttribute("cy", y); circle.setAttribute("r", r); circle.setAttribute("fill", color); circle.setAttribute("fill-opacity", pt.outlier ? "0.9" : "0.85");
    const ab = svgEl("text"); ab.setAttribute("x", x); ab.setAttribute("y", y); ab.setAttribute("class", "dot-abbrev"); ab.textContent = abbr(pt.persona_name);
    const lb = svgEl("text"); lb.setAttribute("x", x + r + 5); lb.setAttribute("y", y + 4); lb.setAttribute("class", "dot-label"); lb.textContent = pt.persona_name;
    const tt = svgEl("title"); tt.textContent = `${pt.persona_name} \u2014 Trust: ${Math.round(pt.signals.trust)}`;
    g.appendChild(circle); g.appendChild(ab); g.appendChild(lb); g.appendChild(tt);
    g.addEventListener("click", () => selectPersona(pt.persona_name));
    svg.appendChild(g);
  });

  mapRoot.appendChild(svg);
}

// ══════════════════════════════════════════════
// ITEM 3: Persona cards — 2-column grid
// ══════════════════════════════════════════════
function renderPersonas(result) {
  personaGrid.innerHTML = "";
  expandedCard = null;

  result.interpretations.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = "persona-card";
    card.dataset.persona = item.persona.name;
    card.style.animationDelay = `${idx * 80}ms`;

    const color = pColor(item.persona.name);
    const trust = item.signals.trust;
    const quote = item.quote || item.interpretation;

    card.innerHTML = `
      ${item.outlier ? '<span class="persona-outlier-pill">outlier</span>' : ""}
      <div class="persona-card-header">
        <div class="persona-avatar" style="background:${color}">${abbr(item.persona.name)}</div>
        <p class="persona-card-name">${item.persona.name}</p>
        <p class="persona-card-share">${fmt(item.persona.share * 100)}</p>
      </div>
      <div class="trust-bar-wrap"><div class="trust-bar"><div class="trust-bar-fill ${trustBarClass(trust)}" style="width:${trust}%"></div></div></div>
      <p class="persona-quote">"${quote}"</p>
      <div class="persona-card-body">
        <div class="signal-tags">
          ${SIGNALS.map(s => {
            const v = Math.round(item.signals[s]);
            return `<span class="signal-tag ${tagClass(v)}">${titleCase(s)} ${v}</span>`;
          }).join("")}
        </div>
      </div>
    `;

    card.addEventListener("click", () => toggleCard(item.persona.name));
    personaGrid.appendChild(card);
  });
}

function toggleCard(name) {
  const cards = personaGrid.querySelectorAll(".persona-card");
  cards.forEach(c => {
    if (c.dataset.persona === name) {
      const wasExpanded = c.classList.contains("expanded");
      cards.forEach(cc => cc.classList.remove("expanded", "active"));
      if (!wasExpanded) { c.classList.add("expanded", "active"); expandedCard = name; }
      else expandedCard = null;
    }
  });
  // Dim non-selected map dots
  mapRoot.querySelectorAll(".point").forEach(g => {
    g.style.opacity = (!expandedCard || g.dataset.persona === expandedCard) ? "1" : "0.35";
  });
}

function selectPersona(name) {
  toggleCard(name);
  const target = personaGrid.querySelector(`.persona-card[data-persona="${CSS.escape(name)}"]`);
  if (target) target.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ══════════════════════════════════════════════
// ITEM 5: Risks + Fix drawer
// ══════════════════════════════════════════════
function renderRisks(summary) {
  riskList.innerHTML = "";
  const risks = summary.key_misunderstanding_risks || [];
  if (!risks.length) { const li = document.createElement("li"); li.textContent = "No major misunderstanding signals detected."; riskList.appendChild(li); return; }

  risks.forEach(risk => {
    const li = document.createElement("li");
    li.className = `risk-item severity-${risk.severity}`;
    li.innerHTML = `
      <span class="risk-severity-label ${risk.severity}">${risk.severity}</span>
      <div>
        <div class="risk-text">${risk.text}</div>
        ${risk.personas.length ? `<p class="risk-personas">${risk.personas.join(" \u00b7 ")}</p>` : ""}
      </div>
      <button class="fix-btn" type="button" data-risk="${encodeURIComponent(risk.text)}" data-persona="${encodeURIComponent(risk.personas[0] || "")}">Fix with AI \u2197</button>
    `;
    riskList.appendChild(li);
  });

  riskList.querySelectorAll(".fix-btn").forEach(btn => btn.addEventListener("click", () => openFixDrawer(btn)));
}

async function openFixDrawer(btn) {
  if (!lastResult) return;
  const riskText = decodeURIComponent(btn.dataset.risk);
  const persona = decodeURIComponent(btn.dataset.persona);

  // Show drawer with skeleton
  drawerOriginal.textContent = lastResult.input_echo.content;
  drawerRewrite.innerHTML = '<div class="skeleton-line"></div><div class="skeleton-line short"></div><div class="skeleton-line"></div>';
  fixDrawerOverlay.classList.remove("hidden");
  fixDrawer.classList.remove("hidden");
  requestAnimationFrame(() => fixDrawer.classList.add("open"));

  try {
    const resp = await fetch("/api/fix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: lastResult.input_echo.content, risk: riskText, persona }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    drawerRewrite.textContent = data.rewrite;
  } catch (e) {
    drawerRewrite.textContent = `Error: ${e.message}`;
  }
}

function closeDrawer() {
  fixDrawer.classList.remove("open");
  setTimeout(() => { fixDrawer.classList.add("hidden"); fixDrawerOverlay.classList.add("hidden"); }, 300);
}

drawerClose.addEventListener("click", closeDrawer);
fixDrawerOverlay.addEventListener("click", closeDrawer);
drawerCopy.addEventListener("click", () => {
  navigator.clipboard.writeText(drawerRewrite.textContent);
  drawerCopy.textContent = "Copied!";
  setTimeout(() => { drawerCopy.textContent = "Copy rewrite"; }, 1500);
});
drawerUse.addEventListener("click", () => {
  contentEl.value = drawerRewrite.textContent;
  closeDrawer();
});

// ══════════════════════════════════════════════
// API calls + orchestration
// ══════════════════════════════════════════════
function getPayload() {
  return { content: contentEl.value, message_type: getSelectedType(), num_personas: 5 };
}

async function runMeaningMap() {
  clearResults();
  skeletonState.classList.add("hidden");
  runBtn.disabled = true;
  setStatus("Running audience simulation across personas...");

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getPayload()),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(String(err?.detail?.details || err?.detail || `HTTP ${response.status}`));
    }
    const result = await response.json();
    await cinematicReveal(result);
    setStatus(`Mapped ${result.personas.length} personas using ${result.model}.`);
    loadHistory();
  } catch (error) {
    loadingStage.classList.add("hidden");
    setStatus(`Analysis failed: ${error.message}`, "error");
  } finally {
    runBtn.disabled = false;
  }
}

async function loadSample() {
  clearResults();
  skeletonState.classList.add("hidden");
  setStatus("Loading sample interpretation map...");
  try {
    const resp = await fetch("/sample-result");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const result = await resp.json();
    await cinematicReveal(result);
    setStatus("Sample result loaded.");
  } catch (e) {
    setStatus(`Failed to load sample: ${e.message}`, "error");
  }
}

// ── Event listeners ──
form.addEventListener("submit", async (e) => { e.preventDefault(); await runMeaningMap(); });
sampleBtn.addEventListener("click", async () => { await loadSample(); });
window.addEventListener("resize", () => { if (mapRoot.childElementCount > 0 && lastMapPoints.length) renderMap(lastMapPoints); });

// ══════════════════════════════════════════════
// History & semantic search (PostgreSQL + pgvector)
// ══════════════════════════════════════════════

// Toggle collapsed/expanded, persist in localStorage
historyToggle.addEventListener("click", () => {
  const collapsed = historyPanel.classList.toggle("collapsed");
  localStorage.setItem("mm-history-collapsed", collapsed ? "1" : "0");
});

// Restore saved state (default: collapsed)
if (localStorage.getItem("mm-history-collapsed") === "0") {
  historyPanel.classList.remove("collapsed");
}

function alignBadge(val) {
  const cls = val >= 80 ? "align-good" : val >= 50 ? "align-mid" : "align-low";
  return `<span class="history-badge ${cls}">${Number(val).toFixed(0)}% aligned</span>`;
}

function updateHistoryCount(count) {
  historyCount.textContent = `${count} saved`;
  historyCount.classList.toggle("hidden", count === 0);
}

function renderHistoryItems(items, showSimilarity) {
  if (!items.length) { historyList.innerHTML = '<p class="history-empty">No results found.</p>'; return; }
  historyList.innerHTML = "";
  items.forEach(item => {
    const el = document.createElement("div");
    el.className = "history-item";
    const sim = showSimilarity && item.similarity != null ? `<span class="similarity">${(item.similarity * 100).toFixed(0)}% match</span>` : "";
    const date = new Date(item.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    el.innerHTML = `
      <p class="history-item-content">${item.content}</p>
      <div class="history-item-meta">
        ${sim}
        ${alignBadge(item.alignment)}
        <span class="history-chip">${item.persona_count} personas</span>
        <span>${date}</span>
      </div>
    `;
    el.addEventListener("click", () => loadAnalysis(item.id));
    historyList.appendChild(el);
  });
}

async function loadHistory() {
  try {
    const resp = await fetch("/api/history?limit=20");
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.db_available) { historyList.innerHTML = '<p class="history-empty">Database not connected.</p>'; updateHistoryCount(0); return; }
    updateHistoryCount(data.items.length);
    renderHistoryItems(data.items, false);
  } catch { /* silent */ }
}

async function searchHistory() {
  const q = searchInput.value.trim();
  if (!q) { loadHistory(); return; }
  searchBtn.disabled = true;
  searchBtn.textContent = "Searching...";
  try {
    const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderHistoryItems(data.results, true);
  } catch (e) {
    historyList.innerHTML = `<p class="history-empty">Search failed: ${e.message}</p>`;
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = "Search";
  }
}

async function loadAnalysis(id) {
  clearResults();
  skeletonState.classList.add("hidden");
  setStatus("Loading past analysis...");
  try {
    const resp = await fetch(`/api/history/${id}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const result = data.result;
    await cinematicReveal(result);
    setStatus(`Loaded past analysis (${result.model}).`);
  } catch (e) {
    setStatus(`Failed to load analysis: ${e.message}`, "error");
  }
}

searchBtn.addEventListener("click", searchHistory);
searchInput.addEventListener("keydown", (e) => { if (e.key === "Enter") searchHistory(); });

// Item 8: Show skeleton on initial load (don't auto-load sample)
loadHistory();
