/* Intellect — UI wiring.
 *
 * This file renders and listens. All grading, scheduling, and progression
 * live behind api.js / session.js / player.js, which is what keeps one
 * codebase honest across a phone and a laptop: the layout changes, the loop
 * does not.
 */

import { api } from "./api.js";
import { renderMath, setMath } from "./math.js";
import {
  MAX_HEARTS, addGoalXP, dailyGoalTarget, goalXP, hearts,
  selectedClass, setSelectedClass,
} from "./player.js";
import { PHASES, loadSession } from "./session.js";

const $ = (id) => document.getElementById(id);

const state = {
  campaign: selectedClass(),
  dashboard: null,
  classes: [],
  path: null,
  session: null,
  nextNode: null,
};

/* ---------------- primitives ---------------- */

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("is-visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("is-visible"), 2800);
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function showScreen(name) {
  document.querySelectorAll(".screen").forEach((screen) => {
    screen.classList.toggle("is-active", screen.id === `screen-${name}`);
  });
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.screen === name);
  });
  document.body.classList.toggle("in-session", name === "session");
}

function haptic(pattern) {
  // Browsers reject vibration until the user has actually touched the page,
  // and a rejected call logs an error. Feedback is decorative, so only try
  // once a real interaction has happened.
  if (!hasInteracted || !navigator.vibrate) return;
  try { navigator.vibrate(pattern); } catch (_) { /* desktop has none */ }
}

let hasInteracted = false;
["pointerdown", "keydown", "touchstart"].forEach((event) => {
  window.addEventListener(event, () => { hasInteracted = true; }, { once: true, passive: true });
});

/* ---------------- HUD ---------------- */

function renderHearts() {
  const left = hearts();
  const el = $("stat-hearts");
  el.innerHTML = `<i aria-hidden="true">♥</i><b>${left}</b>`;
  el.classList.toggle("is-dim", left === 0);
  setText("session-hearts", "♥".repeat(left) + "♡".repeat(MAX_HEARTS - left));
}

function renderGoal() {
  const target = dailyGoalTarget();
  const xp = goalXP();
  $("today-ring").style.setProperty("--ring", `${Math.min(100, Math.round((xp / target) * 100))}%`);
  setText("today-ring-label", `${xp}/${target}`);
}

/* ---------------- class switcher ---------------- */

function classLabel(name) {
  if (name === "All") return { short: "ALL", label: "All classes" };
  const found = state.classes.find((item) => item.name === name);
  return { short: found ? found.short : name.slice(0, 6), label: found ? found.name : name };
}

function renderClasses() {
  const options = [
    {
      name: "All",
      short: "ALL",
      title: "All classes",
      sub: state.classes.length
        ? `${state.classes.length} classes · exam pressure decides the order`
        : "Nothing imported yet",
      due: state.classes.reduce((sum, item) => sum + item.due, 0),
      mastery: null,
    },
    ...state.classes.map((item) => ({
      name: item.name,
      short: item.short,
      title: item.title,
      sub: item.days_left === null || item.days_left === undefined
        ? `${item.questions} items · ${item.topics} topics`
        : `${item.next_exam} in ${item.days_left}d · ${item.questions} items`,
      due: item.due,
      mastery: item.mastery,
      urgent: item.days_left !== null && item.days_left !== undefined && item.days_left <= 7,
    })),
  ];

  // Sidebar (laptop) and sheet (phone) read from the same list, so a class can
  // never appear in one place and not the other.
  const rail = $("rail-classes");
  const sheet = $("course-options");
  rail.innerHTML = "";
  sheet.innerHTML = "";

  options.forEach((option) => {
    const active = state.campaign === option.name;

    const railItem = document.createElement("button");
    railItem.className = `rail-class${active ? " is-active" : ""}${option.urgent ? " is-urgent" : ""}`;
    railItem.innerHTML = `<span class="rail-flag">${option.short}</span>
      <span class="rail-copy"><b></b><small>${option.sub}</small></span>
      ${option.due ? `<span class="rail-due">${option.due}</span>` : ""}`;
    railItem.querySelector("b").textContent = option.title;
    railItem.addEventListener("click", () => pickClass(option.name));
    rail.append(railItem);

    const sheetItem = document.createElement("button");
    sheetItem.className = `sheet-option${active ? " is-active" : ""}`;
    sheetItem.innerHTML = `<span class="sheet-flag">${option.short}</span>
      <span class="sheet-copy"><b></b><small>${option.sub}</small></span>
      ${active ? '<span aria-hidden="true">✓</span>' : ""}`;
    sheetItem.querySelector("b").textContent = option.title;
    sheetItem.addEventListener("click", () => { closeSheet(); pickClass(option.name); });
    sheet.append(sheetItem);
  });

  const current = classLabel(state.campaign);
  setText("course-flag", current.short);
  setText("course-name", current.label);

  const select = $("import-campaign");
  const names = state.classes.map((item) => item.name);
  ["General"].forEach((extra) => { if (!names.includes(extra)) names.push(extra); });
  select.innerHTML = names.map((name) => `<option>${name}</option>`).join("");
}

async function pickClass(name) {
  state.campaign = name;
  setSelectedClass(name);
  renderClasses();
  await loadPath();
  renderSideRail();
}

function openSheet() { $("course-sheet").hidden = false; }
function closeSheet() { $("course-sheet").hidden = true; }

/* ---------------- dashboard ---------------- */

async function loadDashboard() {
  const data = await api.get("/api/dashboard");
  state.dashboard = data;
  const profile = data.profile || {};

  $("stat-streak").innerHTML = `<i aria-hidden="true">🔥</i><b>${profile.daily_streak || 0}</b>`;
  $("stat-xp").innerHTML = `<i aria-hidden="true">⚡</i><b>${profile.xp || 0}</b>`;
  renderHearts();
  renderGoal();

  setText("review-due", data.due_count);
  setText("side-due", data.due_count);
  setText("you-streak", profile.daily_streak || 0);
  setText("you-xp", profile.xp || 0);
  setText("you-accuracy", data.reviews_count ? `${Math.round((data.strong_recall || 0) * 100)}%` : "—");
  setText("you-questions", data.questions_count || 0);
  setText("you-companion", profile.companion || "Nightling");
  setText("you-rank", `Rank ${profile.rank || "E"}`);

  const goal = goalXP();
  if (goal >= dailyGoalTarget()) {
    setText("today-kicker", "Goal complete");
    setText("today-title", "Daily goal done.");
    setText("today-sub", "Anything more today is pure gain. Your streak is safe.");
  } else if (data.due_count > 0) {
    setText("today-kicker", "Today");
    setText("today-title", `${data.due_count} item${data.due_count === 1 ? "" : "s"} ready`);
    setText("today-sub", "Picked from what is weakest and closest to an exam.");
  } else {
    setText("today-kicker", "Today");
    setText("today-title", "Nothing overdue");
    setText("today-sub", "Walk the path to cover new ground, or review early to get ahead.");
  }

  renderWeak(data.topics || []);
  renderLibrary(data.materials || []);
}

function weakButton(topic) {
  const button = document.createElement("button");
  button.className = "weak-item";
  button.innerHTML = `<span class="card-grow"><b></b><small>${topic.campaign} · ${topic.questions} item${topic.questions === 1 ? "" : "s"}</small></span>
    <span class="mini-bar"><i style="width:${Math.round((topic.mastery || 0) * 100)}%"></i></span>`;
  setMath(button.querySelector("b"), topic.name);
  button.addEventListener("click", () => beginSession({ topic: topic.name, campaign: topic.campaign, label: topic.name }));
  return button;
}

function renderWeak(topics) {
  const host = $("weak-list");
  host.innerHTML = "";
  if (!topics.length) {
    host.innerHTML = '<p class="empty">Import material and your weakest topics will surface here.</p>';
  } else {
    topics.slice(0, 10).forEach((topic) => host.append(weakButton(topic)));
  }
  const side = $("side-weak");
  side.innerHTML = "";
  topics.slice(0, 4).forEach((topic) => side.append(weakButton(topic)));
}

function renderLibrary(materials) {
  const host = $("library-grid");
  host.innerHTML = "";
  if (!materials.length) {
    host.innerHTML = '<p class="empty">No material yet. Add a PDF or paste your notes to build a path.</p>';
    return;
  }
  materials.forEach((material) => {
    const card = document.createElement("div");
    card.className = "library-card";
    card.innerHTML = `<span class="card-grow"><b></b><small>${material.campaign} · ${material.questions} item${material.questions === 1 ? "" : "s"}</small></span>`;
    setMath(card.querySelector("b"), material.title);
    host.append(card);
  });
}

async function loadCourses() {
  try {
    const data = await api.get("/api/courses");
    const host = $("you-courses");
    host.innerHTML = "";
    if (!data.courses || !data.courses.length) {
      host.innerHTML = '<p class="empty">No courses yet.</p>';
      return;
    }
    data.courses.forEach((course) => {
      const card = document.createElement("div");
      card.className = "course-card";
      const countdown = course.days_left === null || course.days_left === undefined
        ? "no exam scheduled"
        : `${course.next_exam} in ${course.days_left}d`;
      card.innerHTML = `<span class="card-grow"><b>${course.code}</b><small>${countdown} · ${course.questions} items</small></span>
        <span class="mini-bar"><i style="width:${Math.round((course.mastery || 0) * 100)}%"></i></span>`;
      host.append(card);
    });
  } catch (_) {
    /* Courses are optional context, never a boot blocker. */
  }
}

/* ---------------- path ---------------- */

const NODE_ICON = { complete: "★", current: "▶", next: "▶", open: "▶", locked: "🔒" };

async function loadPath() {
  const data = await api.query("/api/path", { campaign: state.campaign });
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
    const pill = document.createElement("button");
    const urgency = unit.days_left <= 2 ? " is-urgent" : unit.days_left <= 7 ? " is-soon" : "";
    pill.className = `exam-pill${urgency}`;
    pill.innerHTML = `<b>${unit.course}</b><small>${unit.exam_title || "Exam"} · ${unit.days_left === 0 ? "today" : `${unit.days_left}d`}</small>`;
    pill.addEventListener("click", () => pickClass(unit.campaign));
    rail.append(pill);
  });
}

function renderPath(units) {
  const host = $("path-units");
  host.innerHTML = "";
  state.nextNode = null;
  if (!units.length) {
    host.innerHTML = '<p class="empty">No path yet.<br>Add material and Intellect builds the units for you.</p>';
    $("path-end").hidden = false;
    renderSideRail();
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
    setMath(head.querySelector("h3"), unit.title);
    section.append(head);

    unit.nodes.forEach((node) => {
      if (node.state === "current" && !state.nextNode) {
        state.nextNode = { ...node, campaign: unit.campaign, unit: unit.title };
      }
      const row = document.createElement("div");
      row.className = "node-row";
      const wrap = document.createElement("div");
      wrap.className = `node is-${node.state}`;

      const button = document.createElement("button");
      button.className = "node-btn";
      button.textContent = NODE_ICON[node.state] || "▶";
      button.setAttribute("aria-label", `${node.topic} — ${node.state}`);
      button.title = node.topic;
      button.addEventListener("click", () => {
        if (node.state === "locked") { toast("Finish the node above first"); haptic(12); return; }
        beginSession({ topic: node.topic, campaign: unit.campaign, label: node.topic, lessonId: node.lesson_id });
      });

      const label = document.createElement("span");
      label.className = "node-label";
      setMath(label, node.topic);

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
  renderSideRail();
}

function renderSideRail() {
  const next = state.nextNode;
  setMath($("side-next"), next ? `${next.topic} — ${next.unit}` : "Nothing queued yet");
}

/* ---------------- session ---------------- */

async function beginSession(options) {
  try {
    if (hearts() === 0) toast("Out of hearts — they refill tomorrow. Review still works.");
    const session = await loadSession(options);
    if (!session) { toast("Nothing to study here yet"); return; }
    state.session = session;
    showScreen("session");
    renderHearts();
    renderStage();
  } catch (error) {
    toast(error.message);
  }
}

function renderStage() {
  const session = state.session;
  if (!session) return;
  ["teach", "question", "done"].forEach((stage) => {
    $(`stage-${stage}`).hidden = stage !== (session.phase === PHASES.VERDICT ? "question" : session.phase);
  });
  $("session-bar").style.width = `${Math.round(session.progress * 100)}%`;

  if (session.phase === PHASES.TEACH) renderTeach();
  else if (session.phase === PHASES.QUESTION) renderQuestion();
  else if (session.phase === PHASES.VERDICT) renderVerdict();
  else renderDone();
}

function renderTeach() {
  const lesson = state.session.lesson;
  setText("teach-chip", "New concept");
  setMath($("teach-title"), lesson.title || lesson.topic);
  setMath($("teach-objective"), lesson.objective || "");

  const body = $("teach-body");
  body.innerHTML = "";
  const block = (title, build) => {
    const div = document.createElement("div");
    div.className = "teach-block";
    const heading = document.createElement("h4");
    heading.textContent = title;
    div.append(heading);
    build(div);
    body.append(div);
  };

  if (lesson.motivation) {
    block("Why it exists", (div) => {
      const p = document.createElement("p");
      setMath(p, lesson.motivation);
      div.append(p);
    });
  }
  if (lesson.primitives && lesson.primitives.length) {
    block("The pieces", (div) => {
      const list = document.createElement("ul");
      lesson.primitives.forEach((item) => {
        const li = document.createElement("li");
        setMath(li, typeof item === "string" ? item : `${item.term || item.name}: ${item.meaning || ""}`);
        list.append(li);
      });
      div.append(list);
    });
  }
  if (lesson.derivation_steps && lesson.derivation_steps.length) {
    block("How it is built", (div) => {
      const list = document.createElement("ol");
      lesson.derivation_steps.forEach((step) => {
        const li = document.createElement("li");
        setMath(li, typeof step === "string" ? step : `${step.claim || ""} — ${step.reason || ""}`);
        list.append(li);
      });
      div.append(list);
    });
  }
  const worked = lesson.worked_example || {};
  if (worked.problem) {
    block("Worked once, completely", (div) => {
      const box = document.createElement("div");
      box.className = "teach-worked";
      const problem = document.createElement("b");
      setMath(problem, worked.problem);
      box.append(problem);
      (worked.steps || []).forEach((step) => {
        const p = document.createElement("p");
        setMath(p, step);
        box.append(p);
      });
      if (worked.answer) {
        const answer = document.createElement("p");
        answer.className = "worked-answer";
        setMath(answer, worked.answer);
        box.append(answer);
      }
      div.append(box);
    });
  }
  if (lesson.misconception) {
    const note = document.createElement("div");
    note.className = "teach-note";
    const strong = document.createElement("b");
    strong.textContent = "Common wrong turn. ";
    const span = document.createElement("span");
    setMath(span, lesson.misconception);
    note.append(strong, span);
    body.append(note);
  }

  $("verdict").hidden = true;
  const action = $("session-action");
  action.textContent = "Got it";
  action.disabled = false;
}

function renderQuestion() {
  const session = state.session;
  const question = session.question;
  setText("q-chip", question.mode === "recognition"
    ? "Pick the right one"
    : question.kind === "transfer" ? "Transfer challenge" : "Recall it");
  setMath($("q-prompt"), question.prompt);

  const choices = $("q-choices");
  const recall = $("q-recall");
  choices.innerHTML = "";

  if (question.mode === "recognition" && question.choices && question.choices.length) {
    recall.hidden = true;
    choices.hidden = false;
    question.choices.forEach((choice, index) => {
      const button = document.createElement("button");
      button.className = "choice";
      button.innerHTML = `<span class="choice-key">${index + 1}</span><span class="choice-text"></span>`;
      setMath(button.querySelector(".choice-text"), choice);
      button.addEventListener("click", () => {
        choices.querySelectorAll(".choice").forEach((el) => el.classList.remove("is-picked"));
        button.classList.add("is-picked");
        session.setResponse(choice);
        $("session-action").disabled = !session.canSubmit;
        haptic(8);
      });
      choices.append(button);
    });
  } else {
    choices.hidden = true;
    recall.hidden = false;
    const input = $("q-answer");
    input.value = "";
    input.oninput = () => {
      session.setResponse(input.value);
      $("session-action").disabled = !session.canSubmit;
    };
    // Focus is right on a laptop and wrong on a phone, where it throws up the
    // keyboard before the learner has even read the question.
    if (window.matchMedia("(min-width: 900px)").matches) input.focus();
  }

  $("verdict").hidden = true;
  $("self-rate").hidden = true;
  const action = $("session-action");
  action.textContent = "Check";
  action.disabled = !session.canSubmit;
}

function renderVerdict() {
  const session = state.session;
  const preview = session.preview;
  const question = session.question;

  if (question.mode === "recognition") {
    $("q-choices").querySelectorAll(".choice").forEach((el) => {
      el.disabled = true;
      const text = el.querySelector(".choice-text").textContent;
      if (text === preview.answer) el.classList.add("is-right");
      else if (text === preview.response) el.classList.add("is-wrong");
    });
  }

  const verdict = $("verdict");
  verdict.hidden = false;
  verdict.className = `verdict ${preview.right ? "is-right" : "is-wrong"}`;
  setText("verdict-title", preview.right ? "Correct" : "Not quite");
  setText("verdict-xp", preview.right ? "+10 XP" : "");
  setMath($("verdict-answer"), preview.right ? "" : preview.answer);
  setMath($("verdict-why"), preview.explanation || "");
  setMath($("verdict-quote"), preview.source_quote || "");
  $("verdict-source").hidden = !preview.source_quote;
  $("self-rate").hidden = !session.needsSelfRating;

  const action = $("session-action");
  action.textContent = "Continue";
  action.disabled = session.needsSelfRating;
  haptic(preview.right ? 14 : [18, 60, 18]);
  renderHearts();
}

function renderDone() {
  const session = state.session;
  const seconds = session.elapsedSeconds;
  setText("done-xp", `+${session.xp}`);
  setText("done-accuracy", session.accuracy === null ? "—" : `${Math.round(session.accuracy * 100)}%`);
  setText("done-time", `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`);
  const target = dailyGoalTarget();
  setText("done-note", goalXP() >= target
    ? "Daily goal reached. Your streak is safe."
    : `${target - goalXP()} XP to hit today's goal.`);
  $("session-bar").style.width = "100%";
  $("verdict").hidden = true;
  const action = $("session-action");
  action.textContent = "Done";
  action.disabled = false;
  haptic([10, 40, 10, 40, 20]);
}

async function advance() {
  const session = state.session;
  if (!session) return;
  const action = $("session-action");
  action.disabled = true;
  try {
    if (session.phase === PHASES.TEACH) {
      session.acknowledgeLesson();
      renderStage();
    } else if (session.phase === PHASES.QUESTION) {
      await session.check();
      renderStage();
    } else if (session.phase === PHASES.VERDICT) {
      await session.commit(session.suggestedRating);
      renderStage();
    } else {
      await endSession();
    }
  } catch (error) {
    toast(error.message);
    action.disabled = false;
  }
}

async function rateAndAdvance(rating) {
  const session = state.session;
  if (!session || session.phase !== PHASES.VERDICT) return;
  try {
    await session.commit(rating);
    renderStage();
  } catch (error) {
    toast(error.message);
  }
}

async function endSession() {
  state.session = null;
  showScreen("path");
  await refresh();
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
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
      await api.post("/api/material-files", {
        title, campaign, filename: file.name, content_base64: btoa(binary), generate,
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
    await refresh();
  } catch (error) {
    toast(error.message);
  }
}

/* ---------------- routing + keys ---------------- */

function routeHash() {
  const hash = location.hash.replace(/^#\/?/, "");
  if (!hash) return;
  if (["path", "review", "library", "you"].includes(hash)) { showScreen(hash); return; }
  if (hash === "start") { startToday(); return; }
  if (hash === "review-now") { beginSession({ limit: 12, label: "Review" }); return; }
  // #topic/<name> opens one topic directly. A shareable link to a concept,
  // and what the end-to-end checks drive.
  const topic = hash.match(/^topic\/(.+)$/);
  if (topic) {
    const name = decodeURIComponent(topic[1]);
    beginSession({ topic: name, label: name, limit: 5 });
  }
}

function startToday() {
  const next = state.nextNode;
  if (next) {
    beginSession({ topic: next.topic, campaign: next.campaign, label: next.topic, lessonId: next.lesson_id });
  } else {
    beginSession({ limit: 8, label: "Today" });
  }
}

function onKey(event) {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  const inSession = $("screen-session").classList.contains("is-active");
  const session = state.session;

  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    if (inSession) advance();
    return;
  }
  if (typing) return;

  if (inSession && session) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      advance();
      return;
    }
    if (event.key === "Escape") { endSession(); return; }
    if (session.phase === PHASES.QUESTION && /^[1-9]$/.test(event.key)) {
      const choice = $("q-choices").querySelectorAll(".choice")[Number(event.key) - 1];
      if (choice) { choice.click(); event.preventDefault(); }
      return;
    }
    if (session.phase === PHASES.VERDICT && session.needsSelfRating && /^[1-4]$/.test(event.key)) {
      rateAndAdvance(["again", "hard", "good", "easy"][Number(event.key) - 1]);
      event.preventDefault();
    }
    return;
  }

  const shortcuts = { s: startToday, r: () => beginSession({ limit: 12, label: "Review" }), a: () => $("import-dialog").showModal() };
  const key = event.key.toLowerCase();
  if (shortcuts[key]) { shortcuts[key](); event.preventDefault(); return; }
  if (/^[1-9]$/.test(event.key)) {
    const option = $("rail-classes").children[Number(event.key) - 1];
    if (option) option.click();
  }
}

/* ---------------- boot ---------------- */

async function refresh() {
  try {
    const classes = await api.get("/api/classes");
    state.classes = classes.classes || [];
    // A class can disappear when its material is removed; do not strand the
    // learner filtered to something that no longer exists.
    if (state.campaign !== "All" && !state.classes.some((item) => item.name === state.campaign)) {
      state.campaign = "All";
      setSelectedClass("All");
    }
    renderClasses();
    await loadDashboard();
    await loadPath();
    await loadCourses();
  } catch (error) {
    toast(error.message);
  }
}

function bind() {
  window.addEventListener("hashchange", routeHash);
  document.addEventListener("keydown", onKey);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => showScreen(tab.dataset.screen));
  });
  $("session-action").addEventListener("click", advance);
  $("session-quit").addEventListener("click", endSession);
  $("start-review").addEventListener("click", () => beginSession({ limit: 12, label: "Review" }));
  $("side-review").addEventListener("click", () => beginSession({ limit: 12, label: "Review" }));
  $("side-start").addEventListener("click", startToday);
  $("today-card").addEventListener("click", startToday);
  $("today-card").addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); startToday(); }
  });
  $("course-switch").addEventListener("click", openSheet);
  $("course-sheet").addEventListener("click", (event) => {
    if (event.target.id === "course-sheet") closeSheet();
  });
  ["library-import", "path-add", "rail-import"].forEach((id) => {
    $(id).addEventListener("click", () => $("import-dialog").showModal());
  });
  $("import-form").addEventListener("submit", submitImport);
  document.querySelectorAll("#self-rate [data-rating]").forEach((button) => {
    button.addEventListener("click", () => rateAndAdvance(button.dataset.rating));
  });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

bind();
refresh().then(routeHash);

// Exposed for end-to-end checks that drive the real UI rather than a mock.
window.intellect = { state, beginSession, advance, refresh, renderMath, pickClass };
