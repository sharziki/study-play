/* Intellect — client.
   State is deliberately small: the server owns scheduling and mastery, the
   client owns only what the current session needs. Anything else would drift. */

const api = {
  async get(path) {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "request failed");
    return data;
  },
  async post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "request failed");
    return data;
  },
};

const $ = (id) => document.getElementById(id);
const DAILY_GOAL = 40;          // XP. Small enough to finish on a bus.
const MAX_HEARTS = 5;

const state = {
  campaign: localStorage.getItem("intellect.campaign") || "All",
  dashboard: null,
  path: null,
  session: null,
};

/* ---------------- helpers ---------------- */

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("is-visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("is-visible"), 2600);
}

function typeset(node) {
  if (window.renderMathInElement) {
    try {
      window.renderMathInElement(node, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\(", right: "\\)", display: false },
          { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
      });
    } catch (_) { /* math is a nicety, never a blocker */ }
  }
}

function setText(id, value) { const el = $(id); if (el) el.textContent = value; }

function showScreen(name) {
  document.querySelectorAll(".screen").forEach((screen) => {
    screen.classList.toggle("is-active", screen.id === `screen-${name}`);
  });
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.screen === name);
  });
  window.scrollTo(0, 0);
}

function haptic(pattern) {
  if (navigator.vibrate) { try { navigator.vibrate(pattern); } catch (_) {} }
}

/* ---------------- daily goal ---------------- */

function today() { return new Date().toISOString().slice(0, 10); }

function goalXP() {
  const saved = JSON.parse(localStorage.getItem("intellect.goal") || "{}");
  return saved.date === today() ? saved.xp || 0 : 0;
}

function addGoalXP(amount) {
  const value = goalXP() + amount;
  localStorage.setItem("intellect.goal", JSON.stringify({ date: today(), xp: value }));
  renderGoal();
}

function renderGoal() {
  const xp = goalXP();
  const percent = Math.min(100, Math.round((xp / DAILY_GOAL) * 100));
  const ring = $("today-ring");
  ring.style.setProperty("--ring", `${percent}%`);
  setText("today-ring-label", `${xp}/${DAILY_GOAL}`);
}

/* ---------------- dashboard ---------------- */

async function loadDashboard() {
  const data = await api.get("/api/dashboard");
  state.dashboard = data;
  const profile = data.profile || {};

  setText("stat-streak", "");
  $("stat-streak").innerHTML = `<i aria-hidden="true">🔥</i><b>${profile.daily_streak || 0}</b>`;
  $("stat-xp").innerHTML = `<i aria-hidden="true">⚡</i><b>${profile.xp || 0}</b>`;
  renderHearts();

  setText("review-due", data.due_count);
  setText("you-streak", profile.daily_streak || 0);
  setText("you-xp", profile.xp || 0);
  setText("you-accuracy", data.reviews_count ? `${Math.round((data.strong_recall || 0) * 100)}%` : "—");
  setText("you-questions", data.questions_count || 0);
  setText("you-companion", profile.companion || "Nightling");
  setText("you-rank", `Rank ${profile.rank || "E"}`);

  const goal = goalXP();
  if (goal >= DAILY_GOAL) {
    setText("today-kicker", "Goal complete");
    setText("today-title", "Daily goal done.");
    setText("today-sub", "Anything more today is pure gain. Your streak is safe.");
  } else if (data.due_count > 0) {
    setText("today-kicker", "Today");
    setText("today-title", `${data.due_count} item${data.due_count === 1 ? "" : "s"} ready`);
    setText("today-sub", "Picked from what is weakest and closest to an exam. Tap a node to start.");
  } else {
    setText("today-kicker", "Today");
    setText("today-title", "Nothing overdue");
    setText("today-sub", "Walk the path to cover new ground, or review early to get ahead.");
  }
  renderGoal();
  renderWeak(data.topics || []);
  renderLibrary(data.materials || []);
  renderCourseOptions(data.tracks || []);
}

function renderHearts() {
  const hearts = currentHearts();
  const el = $("stat-hearts");
  el.innerHTML = `<i aria-hidden="true">♥</i><b>${hearts}</b>`;
  el.classList.toggle("is-dim", hearts === 0);
}

function currentHearts() {
  const saved = JSON.parse(localStorage.getItem("intellect.hearts") || "{}");
  // Hearts refill daily. They exist to slow down guess-spamming, not to sell
  // refills, so the penalty never blocks studying for more than a day.
  if (saved.date !== today()) return MAX_HEARTS;
  return Math.max(0, Math.min(MAX_HEARTS, saved.hearts ?? MAX_HEARTS));
}

function setHearts(value) {
  localStorage.setItem("intellect.hearts", JSON.stringify({ date: today(), hearts: value }));
  renderHearts();
}

function renderWeak(topics) {
  const host = $("weak-list");
  if (!topics.length) { host.innerHTML = `<p class="empty">Import material and your weakest topics will surface here.</p>`; return; }
  host.innerHTML = "";
  topics.slice(0, 10).forEach((topic) => {
    const button = document.createElement("button");
    button.className = "weak-item";
    button.innerHTML = `<div class="card-grow"><b></b><small>${topic.campaign} · ${topic.questions} item${topic.questions === 1 ? "" : "s"}</small></div>
      <div class="mini-bar"><i style="width:${Math.round((topic.mastery || 0) * 100)}%"></i></div>`;
    button.querySelector("b").textContent = topic.name;
    button.addEventListener("click", () => startSession({ topic: topic.name, campaign: topic.campaign, label: topic.name }));
    host.append(button);
  });
}

function renderLibrary(materials) {
  const host = $("library-grid");
  if (!materials.length) { host.innerHTML = `<p class="empty">No material yet. Add a PDF or paste your notes to build a path.</p>`; return; }
  host.innerHTML = "";
  materials.forEach((material) => {
    const card = document.createElement("div");
    card.className = "library-card";
    card.innerHTML = `<div class="card-grow"><b></b><small>${material.campaign} · ${material.questions} item${material.questions === 1 ? "" : "s"}</small></div>`;
    card.querySelector("b").textContent = material.title;
    host.append(card);
  });
}

function renderCourseOptions(tracks) {
  const host = $("course-options");
  host.innerHTML = "";
  const options = [{ name: "All", label: "All classes", sub: "Exam pressure decides the order" }].concat(
    tracks.map((track) => ({
      name: track.name,
      label: track.name,
      sub: `${track.questions} items · ${track.due} due`,
    }))
  );
  options.forEach((option) => {
    const button = document.createElement("button");
    button.className = `sheet-option${state.campaign === option.name ? " is-active" : ""}`;
    button.innerHTML = `<span>${option.label}<br><small>${option.sub}</small></span>${state.campaign === option.name ? "<span>✓</span>" : ""}`;
    button.addEventListener("click", () => {
      state.campaign = option.name;
      localStorage.setItem("intellect.campaign", option.name);
      $("course-sheet").hidden = true;
      refreshHome();
    });
    host.append(button);
  });

  const select = $("import-campaign");
  if (select) {
    const names = tracks.map((track) => track.name);
    ["General", "Putnam"].forEach((extra) => { if (!names.includes(extra)) names.push(extra); });
    select.innerHTML = names.map((name) => `<option>${name}</option>`).join("");
  }

  const isAll = state.campaign === "All";
  setText("course-flag", isAll ? "ALL" : state.campaign.split(/\s+/)[0].slice(0, 4).toUpperCase());
  setText("course-name", isAll ? "All classes" : state.campaign);
}

/* ---------------- path ---------------- */

async function loadPath() {
  const query = state.campaign === "All" ? "" : `?campaign=${encodeURIComponent(state.campaign)}`;
  const data = await api.get(`/api/path${query}`);
  state.path = data;
  renderPath(data.units || []);
  renderExamRail(data.units || []);
}

function renderExamRail(units) {
  const rail = $("exam-rail");
  const seen = new Map();
  units.forEach((unit) => {
    if (unit.days_left === null || unit.days_left === undefined) return;
    if (!seen.has(unit.course)) seen.set(unit.course, unit);
  });
  if (!seen.size) { rail.hidden = true; return; }
  rail.hidden = false;
  rail.innerHTML = "";
  [...seen.values()].sort((a, b) => a.days_left - b.days_left).forEach((unit) => {
    const pill = document.createElement("div");
    const urgent = unit.days_left <= 2 ? " is-urgent" : unit.days_left <= 7 ? " is-soon" : "";
    pill.className = `exam-pill${urgent}`;
    pill.innerHTML = `<b>${unit.course}</b><small>${unit.exam_title || "Exam"} · ${unit.days_left === 0 ? "today" : `${unit.days_left}d`}</small>`;
    rail.append(pill);
  });
}

const NODE_ICONS = { complete: "★", current: "▶", next: "▶", locked: "🔒", open: "▶" };

function renderPath(units) {
  const host = $("path-units");
  host.innerHTML = "";
  if (!units.length) {
    host.innerHTML = `<p class="empty">No path yet.<br>Add material and Intellect builds the units for you.</p>`;
    $("path-end").hidden = false;
    return;
  }
  units.forEach((unit) => {
    const section = document.createElement("section");
    section.className = "unit";
    const urgent = unit.days_left !== null && unit.days_left !== undefined && unit.days_left <= 7;
    const head = document.createElement("div");
    head.className = `unit-head${urgent ? " is-urgent" : ""}`;
    head.innerHTML = `<span class="unit-course">${unit.course}${urgent ? ` · exam in ${unit.days_left}d` : ""}</span>
      <h3></h3>
      <div class="unit-bar"><i style="width:${Math.round((unit.progress || 0) * 100)}%"></i></div>`;
    head.querySelector("h3").textContent = unit.title;
    section.append(head);

    unit.nodes.forEach((node) => {
      const row = document.createElement("div");
      row.className = "node-row";
      const wrap = document.createElement("div");
      wrap.className = `node is-${node.state}`;
      const button = document.createElement("button");
      button.className = "node-btn";
      button.textContent = NODE_ICONS[node.state] || "▶";
      button.setAttribute("aria-label", `${node.topic} — ${node.state}`);
      button.addEventListener("click", () => {
        if (node.state === "locked") { toast("Finish the node above first"); haptic(12); return; }
        startSession({ topic: node.topic, campaign: unit.campaign, label: node.topic, lessonId: node.lesson_id });
      });
      const label = document.createElement("span");
      label.className = "node-label";
      label.textContent = node.topic;
      wrap.append(button, label);
      if (node.state === "current") {
        const tip = document.createElement("span");
        tip.className = "node-start";
        tip.textContent = "START";
        wrap.prepend(tip);
      }
      row.append(wrap);
      section.append(row);
    });
    host.append(section);
  });
  $("path-end").hidden = false;
}

/* ---------------- session ---------------- */

async function startSession({ topic = null, campaign = null, label = "", lessonId = null, limit = 8 } = {}) {
  if (currentHearts() === 0) {
    toast("Out of hearts — they refill tomorrow. Review mode still works.");
  }
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    const scope = campaign || state.campaign;
    if (scope && scope !== "All") params.set("campaign", scope);
    if (topic) params.set("topic", topic);
    const data = await api.get(`/api/session?${params}`);
    if (!data.questions || !data.questions.length) { toast("Nothing to study here yet"); return; }

    let lesson = null;
    if (lessonId) {
      try {
        const candidate = await api.get(`/api/lesson${scope && scope !== "All" ? `?campaign=${encodeURIComponent(scope)}` : ""}`);
        if (candidate.available && candidate.topic === topic) lesson = candidate;
      } catch (_) { /* a missing lesson just means straight to practice */ }
    }

    state.session = {
      label: label || scope || "Study",
      questions: data.questions,
      index: 0,
      lesson,
      teachShown: false,
      xp: 0,
      correct: 0,
      answered: 0,
      startedAt: Date.now(),
      questionStartedAt: Date.now(),
      picked: null,
      preview: null,
      phase: "idle",
    };
    showScreen("session");
    renderHeartStrip();
    if (lesson) showTeach(); else showQuestion();
  } catch (error) {
    toast(error.message);
  }
}

function renderHeartStrip() {
  const hearts = currentHearts();
  setText("session-hearts", "♥".repeat(hearts) + "♡".repeat(MAX_HEARTS - hearts));
}

function progressPercent() {
  const session = state.session;
  const total = session.questions.length + (session.lesson ? 1 : 0);
  const done = session.index + (session.lesson && session.teachShown ? 1 : 0);
  return Math.round((done / total) * 100);
}

function setStage(name) {
  ["teach", "question", "done"].forEach((stage) => { $(`stage-${stage}`).hidden = stage !== name; });
  $("session-bar").style.width = `${progressPercent()}%`;
}

function showTeach() {
  const lesson = state.session.lesson;
  state.session.phase = "teach";
  setText("teach-chip", "New concept");
  setText("teach-title", lesson.title || lesson.topic);
  setText("teach-objective", lesson.objective || "");

  const body = $("teach-body");
  body.innerHTML = "";
  const block = (title, html) => {
    if (!html) return;
    const div = document.createElement("div");
    div.className = "teach-block";
    div.innerHTML = `<h4>${title}</h4>${html}`;
    body.append(div);
  };
  block("Why it exists", lesson.motivation ? `<p>${lesson.motivation}</p>` : "");
  if (lesson.primitives && lesson.primitives.length) {
    block("The pieces", `<ul>${lesson.primitives.map((item) => `<li>${typeof item === "string" ? item : `<b>${item.name}</b> — ${item.meaning || ""}`}</li>`).join("")}</ul>`);
  }
  if (lesson.derivation_steps && lesson.derivation_steps.length) {
    block("How it is built", `<ol>${lesson.derivation_steps.map((step) => `<li>${typeof step === "string" ? step : `${step.claim || ""} <i>${step.reason || ""}</i>`}</li>`).join("")}</ol>`);
  }
  const worked = lesson.worked_example || {};
  if (worked.problem) {
    block("Worked once, completely", `<div class="teach-worked"><b>${worked.problem}</b><p>${(worked.steps || []).join("<br>")}</p><p><b>${worked.answer || ""}</b></p></div>`);
  }
  if (lesson.misconception) {
    const note = document.createElement("div");
    note.className = "teach-note";
    note.innerHTML = `<b>Common wrong turn.</b> ${lesson.misconception}`;
    body.append(note);
  }
  typeset(body);

  setStage("teach");
  $("verdict").hidden = true;
  const action = $("session-action");
  action.textContent = "Got it";
  action.disabled = false;
}

function showQuestion() {
  const session = state.session;
  const question = session.questions[session.index];
  session.phase = "question";
  session.picked = null;
  session.preview = null;
  session.questionStartedAt = Date.now();

  setText("q-chip", question.mode === "recognition" ? "Pick the right one" : question.kind === "transfer" ? "Transfer challenge" : "Recall it");
  const prompt = $("q-prompt");
  prompt.textContent = question.prompt;
  typeset(prompt);

  const choices = $("q-choices");
  const recall = $("q-recall");
  choices.innerHTML = "";
  if (question.mode === "recognition" && question.choices && question.choices.length) {
    recall.hidden = true;
    choices.hidden = false;
    question.choices.forEach((choice) => {
      const button = document.createElement("button");
      button.className = "choice";
      button.textContent = choice;
      button.addEventListener("click", () => {
        choices.querySelectorAll(".choice").forEach((el) => el.classList.remove("is-picked"));
        button.classList.add("is-picked");
        session.picked = choice;
        $("session-action").disabled = false;
        haptic(8);
      });
      choices.append(button);
    });
    typeset(choices);
  } else {
    choices.hidden = true;
    recall.hidden = false;
    const input = $("q-answer");
    input.value = "";
    input.oninput = () => { $("session-action").disabled = input.value.trim().length < 2; };
  }

  setStage("question");
  $("verdict").hidden = true;
  const action = $("session-action");
  action.textContent = "Check";
  action.disabled = true;
}

async function checkAnswer() {
  const session = state.session;
  const question = session.questions[session.index];
  const response = question.mode === "recognition" ? (session.picked || "") : $("q-answer").value.trim();
  const seconds = (Date.now() - session.questionStartedAt) / 1000;

  const preview = await api.post("/api/review-preview", {
    question_id: question.id,
    response,
    confidence: 4,
    mode: question.mode,
  });
  session.preview = { ...preview, response, seconds };
  session.phase = "verdict";

  const right = question.mode === "recognition"
    ? response === preview.answer
    : preview.suggested_rating === "good" || preview.suggested_rating === "easy";

  if (question.mode === "recognition") {
    $("q-choices").querySelectorAll(".choice").forEach((el) => {
      el.disabled = true;
      if (el.textContent === preview.answer) el.classList.add("is-right");
      else if (el.textContent === response) el.classList.add("is-wrong");
    });
  }

  const verdict = $("verdict");
  verdict.hidden = false;
  verdict.className = `verdict ${right ? "is-right" : "is-wrong"}`;
  setText("verdict-title", right ? "Correct" : "Not quite");
  setText("verdict-xp", right ? "+10 XP" : "");
  setText("verdict-answer", right ? "" : preview.answer);
  setText("verdict-why", preview.explanation || "");
  setText("verdict-quote", preview.source_quote || "");
  $("verdict-source").hidden = !preview.source_quote;
  typeset(verdict);

  const selfRate = $("self-rate");
  selfRate.hidden = !preview.needs_rating;
  $("session-action").disabled = preview.needs_rating;
  $("session-action").textContent = "Continue";

  if (right) {
    haptic(14);
  } else {
    haptic([18, 60, 18]);
    setHearts(Math.max(0, currentHearts() - 1));
    renderHeartStrip();
    // A missed item is re-queued at the end of the set. Getting it right once
    // after failing is what actually moves it, so the set does not end on a
    // miss the learner never saw resolved.
    session.questions.push(question);
  }
}

async function commit(rating) {
  const session = state.session;
  const question = session.questions[session.index];
  const preview = session.preview;
  const result = await api.post("/api/reviews", {
    question_id: question.id,
    rating,
    confidence: 4,
    response: preview.response,
    response_seconds: preview.seconds,
    boss: !!question.boss,
  });
  session.xp += result.xp_gained + (result.lesson_bonus_xp || 0);
  session.answered += 1;
  if (rating === "good" || rating === "easy") session.correct += 1;
  addGoalXP(result.xp_gained);
  session.index += 1;
  if (session.index >= session.questions.length) finishSession();
  else showQuestion();
}

function finishSession() {
  const session = state.session;
  session.phase = "done";
  const seconds = Math.round((Date.now() - session.startedAt) / 1000);
  setText("done-xp", `+${session.xp}`);
  setText("done-accuracy", session.answered ? `${Math.round((session.correct / session.answered) * 100)}%` : "—");
  setText("done-time", `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`);
  setText("done-note", goalXP() >= DAILY_GOAL
    ? "Daily goal reached. Your streak is safe."
    : `${DAILY_GOAL - goalXP()} XP to hit today's goal.`);
  $("session-bar").style.width = "100%";
  setStage("done");
  $("verdict").hidden = true;
  $("session-action").textContent = "Done";
  $("session-action").disabled = false;
  haptic([10, 40, 10, 40, 20]);
}

async function sessionAction() {
  const session = state.session;
  if (!session) return;
  const action = $("session-action");
  action.disabled = true;
  try {
    if (session.phase === "teach") {
      session.teachShown = true;
      showQuestion();
    } else if (session.phase === "question") {
      await checkAnswer();
    } else if (session.phase === "verdict") {
      const rating = session.preview.needs_rating ? "good" : session.preview.suggested_rating;
      await commit(rating);
    } else if (session.phase === "done") {
      await exitSession();
    }
  } catch (error) {
    toast(error.message);
    action.disabled = false;
  }
}

async function exitSession() {
  state.session = null;
  showScreen("path");
  await refreshHome();
}

/* ---------------- import ---------------- */

async function submitImport(event) {
  event.preventDefault();
  const title = $("import-title-input").value.trim();
  const campaign = $("import-campaign").value;
  const content = $("import-content").value.trim();
  const file = $("file-input").files[0];
  const generate = $("generate-now").checked;
  if (!title) { toast("Give it a title"); return; }
  try {
    if (file) {
      const buffer = await file.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = "";
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
      await api.post("/api/material-files", {
        title, campaign, filename: file.name,
        content_base64: btoa(binary), generate,
      });
    } else if (content) {
      await api.post("/api/materials", { title, campaign, content, generate });
    } else {
      toast("Add a file or paste some text");
      return;
    }
    $("import-dialog").close();
    $("import-form").reset();
    toast(generate ? "Added — building your lessons" : "Added");
    await refreshHome();
  } catch (error) {
    toast(error.message);
  }
}

/* ---------------- boot ---------------- */

async function refreshHome() {
  try {
    await loadDashboard();
    await loadPath();
    await loadCourses();
  } catch (error) {
    toast(error.message);
  }
}

async function loadCourses() {
  try {
    const data = await api.get("/api/courses");
    const host = $("you-courses");
    if (!data.courses || !data.courses.length) {
      host.innerHTML = `<p class="empty">No courses yet.</p>`;
      return;
    }
    host.innerHTML = "";
    data.courses.forEach((course) => {
      const card = document.createElement("div");
      card.className = "course-card";
      const countdown = course.days_left === null || course.days_left === undefined
        ? "no exam scheduled"
        : `${course.next_exam} in ${course.days_left}d`;
      card.innerHTML = `<div class="card-grow"><b>${course.code}</b><small>${countdown} · ${course.questions} items</small></div>
        <div class="mini-bar"><i style="width:${Math.round((course.mastery || 0) * 100)}%"></i></div>`;
      host.append(card);
    });
  } catch (_) { /* courses are optional context, never a boot blocker */ }
}

function routeHash() {
  const hash = location.hash.replace(/^#\/?/, "");
  if (!hash) return;
  if (["path", "review", "library", "you"].includes(hash)) { showScreen(hash); return; }
  if (hash === "start") { startSession({ limit: 8, label: "Today" }); return; }
  if (hash === "review-now") { startSession({ limit: 12, label: "Review" }); }
}

function bind() {
  // Deep links. A home-screen shortcut that lands straight in a set removes the
  // "open the app, decide what to do" step that kills a study habit.
  window.addEventListener("hashchange", routeHash);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => showScreen(tab.dataset.screen));
  });
  $("session-action").addEventListener("click", sessionAction);
  $("session-quit").addEventListener("click", exitSession);
  $("start-review").addEventListener("click", () => startSession({ limit: 12, label: "Review" }));
  $("today-card").addEventListener("click", () => startSession({ limit: 8, label: "Today" }));
  $("course-switch").addEventListener("click", () => { $("course-sheet").hidden = false; });
  $("course-sheet").addEventListener("click", (event) => {
    if (event.target.id === "course-sheet") $("course-sheet").hidden = true;
  });
  $("library-import").addEventListener("click", () => $("import-dialog").showModal());
  $("path-add").addEventListener("click", () => $("import-dialog").showModal());
  $("import-form").addEventListener("submit", submitImport);
  document.querySelectorAll("#self-rate [data-rating]").forEach((button) => {
    button.addEventListener("click", () => commit(button.dataset.rating).catch((error) => toast(error.message)));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      if ($("screen-session").classList.contains("is-active")) sessionAction();
    }
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

bind();
refreshHome().then(routeHash);
