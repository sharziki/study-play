const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  dashboard: null,
  questions: [],
  index: 0,
  minutes: 20,
  campaign: "All",
  selectedChoice: null,
  startedAt: 0,
  sessionStartedAt: 0,
  sessionXP: 0,
  committed: false,
  pendingFile: null,
  timer: null,
  lesson: null,
  lessonCheckIndex: 0,
  lessonCheckResult: null,
};

const sound = {
  muted: localStorage.getItem("intellect-muted") === "true",
  volume: Number(localStorage.getItem("intellect-volume") || 35) / 100,
  context: null,
};

function playSound(kind) {
  if (sound.muted || sound.volume <= 0) return;
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  sound.context ||= new AudioContext();
  if (sound.context.state === "suspended") sound.context.resume();
  const patterns = {
    correct: [[523.25, 0], [659.25, .08]],
    incorrect: [[220, 0], [196, .11]],
    unlock: [[392, 0], [523.25, .09], [659.25, .18], [783.99, .29]],
    complete: [[523.25, 0], [659.25, .09], [783.99, .18], [1046.5, .31]],
  };
  const notes = patterns[kind] || patterns.correct;
  notes.forEach(([frequency, delay], index) => {
    const oscillator = sound.context.createOscillator();
    const gain = sound.context.createGain();
    const start = sound.context.currentTime + delay;
    oscillator.type = kind === "incorrect" ? "triangle" : "sine";
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(sound.volume * .16, start + .012);
    gain.gain.exponentialRampToValueAtTime(.0001, start + .16 + index * .015);
    oscillator.connect(gain).connect(sound.context.destination);
    oscillator.start(start);
    oscillator.stop(start + .2);
  });
}

function showAchievement(title, detail) {
  const popover = $("#achievement-popover");
  $("#achievement-title").textContent = title;
  $("#achievement-detail").textContent = detail;
  popover.hidden = false;
  popover.classList.add("is-visible");
  clearTimeout(popover.timer);
  popover.timer = setTimeout(() => {
    popover.classList.remove("is-visible");
    setTimeout(() => { popover.hidden = true; }, 250);
  }, 3200);
}

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}

function renderMath(root = document.body) {
  if (typeof window.renderMathInElement !== "function") return;
  window.renderMathInElement(root, {
    delimiters: [
      {left: "$$", right: "$$", display: true},
      {left: "\\[", right: "\\]", display: true},
      {left: "\\(", right: "\\)", display: false},
      {left: "$", right: "$", display: false},
    ],
    throwOnError: false,
    strict: false,
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("is-visible");
  clearTimeout(node.timer);
  node.timer = setTimeout(() => node.classList.remove("is-visible"), 2800);
}

function percent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function setView(name) {
  $$(".view").forEach(view => view.classList.toggle("is-visible", view.id === `${name}-view`));
  $$(".nav-item").forEach(button => {
    const active = button.dataset.view === name;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (name === "library" && state.dashboard) renderLibrary();
  window.scrollTo({top: 0, behavior: "smooth"});
}

function buildMasteryField() {
  const field = $("#hero-field");
  field.innerHTML = "";
  const nodes = [
    [8,17,100,-8],[18,72,150,-23],[35,33,120,18],[52,82,120,-16],[64,21,145,32],
    [73,60,90,-38],[86,32,90,20],[92,79,70,-28],[43,57,110,4],[27,91,80,-42],
  ];
  nodes.forEach(([x,y,reach,angle], index) => {
    const node = document.createElement("i");
    node.className = "field-node";
    node.style.left = `${x}%`;
    node.style.top = `${y}%`;
    node.style.setProperty("--reach", `${reach}px`);
    node.style.setProperty("--angle", `${angle}deg`);
    node.style.opacity = String(.25 + (index % 4) * .18);
    field.append(node);
  });
}

async function loadDashboard() {
  try {
    const [dashboard, courses] = await Promise.all([
      api("/api/dashboard"),
      // A brain-new install has no courses; that must not blank the dashboard.
      api("/api/courses").catch(() => ({ courses: [] })),
    ]);
    state.dashboard = dashboard;
    state.courses = courses.courses || [];
    renderDashboard();
  } catch (error) {
    toast(error.message);
  }
}

function examLabel(daysLeft) {
  if (daysLeft === 0) return "Today";
  if (daysLeft === 1) return "Tomorrow";
  return `${daysLeft} days`;
}

function renderExamStrip() {
  const strip = $("#exam-strip");
  if (!strip) return;
  const upcoming = (state.courses || []).filter(course => course.days_left !== null && course.days_left !== undefined);
  if (!upcoming.length) {
    strip.hidden = true;
    strip.innerHTML = "";
    return;
  }
  strip.hidden = false;
  strip.innerHTML = upcoming.map(course => {
    const days = course.days_left;
    const urgency = days <= 2 ? "is-imminent" : days <= 7 ? "is-urgent" : "";
    return `
      <button class="exam-card ${urgency}" data-campaign="${escapeHTML(course.code)}">
        <span class="exam-course">${escapeHTML(course.code)}</span>
        <span class="exam-count">${examLabel(days)}</span>
        <span class="exam-meta">${escapeHTML(course.next_exam || "Exam")} · ${percent(course.mastery)} ready</span>
      </button>`;
  }).join("");
  $$(".exam-card", strip).forEach(button => button.addEventListener("click", () => {
    const select = $("#campaign-select");
    if ([...select.options].some(option => option.value === button.dataset.campaign)) {
      select.value = button.dataset.campaign;
      state.campaign = button.dataset.campaign;
    }
    $("#start-sprint").focus();
  }));
}

function renderDashboard() {
  const data = state.dashboard;
  if (!data) return;
  const p = data.profile;
  $("#due-count").textContent = data.due_count;
  $("#strong-recall").textContent = percent(data.strong_recall);
  $("#question-count").textContent = data.questions_count;
  $("#material-count").textContent = `across ${data.materials_count} source${data.materials_count === 1 ? "" : "s"}`;
  $("#rank").textContent = p.rank;
  $("#nyx-stage").textContent = p.companion;
  $("#nyx-progress").textContent = p.next_evolution_xp ? `${p.next_evolution_xp - p.xp} XP until evolution` : "final evolution";
  $("#queue-label").textContent = data.due_count ? `${data.due_count} ideas are ready to revisit` : "A fresh set is ready";
  $(".topbar .eyebrow").textContent = `${new Intl.DateTimeFormat("en-US", {weekday:"long"}).format(new Date())} · today’s study note`;

  const campaignSelect = $("#campaign-select");
  const previous = campaignSelect.value || state.campaign;
  campaignSelect.innerHTML = '<option value="All">All tracks</option>' + data.tracks.map(track =>
    `<option value="${escapeHTML(track.name)}">${escapeHTML(track.name)}</option>`
  ).join("");
  campaignSelect.value = [...campaignSelect.options].some(option => option.value === previous) ? previous : "All";

  const trackList = $("#track-list");
  trackList.innerHTML = data.tracks.length ? data.tracks.map(track => `
    <button class="track-item" data-campaign="${escapeHTML(track.name)}">
      <i class="track-dot"></i><span>${escapeHTML(track.name)}</span><small>${track.due} due</small>
    </button>`).join("") : '<div class="empty-state">Add your first source</div>';
  $$(".track-item", trackList).forEach(button => button.addEventListener("click", () => {
    campaignSelect.value = button.dataset.campaign;
    state.campaign = button.dataset.campaign;
    setView("dashboard");
    $("#start-sprint").focus();
  }));

  const mastery = $("#mastery-field");
  mastery.innerHTML = data.topics.length ? data.topics.map(topic => `
    <article class="mastery-node" style="--mastery:${Number(topic.mastery).toFixed(3)}">
      <span>${escapeHTML(topic.campaign)}</span>
      <strong>${escapeHTML(topic.name)}</strong>
      <small>${percent(topic.mastery)}</small>
    </article>`).join("") : '<div class="empty-state">Import material and generate questions to reveal the mastery field.</div>';

  const trackCards = $("#track-cards");
  trackCards.innerHTML = data.tracks.length ? data.tracks.map(track => `
    <article class="track-card">
      <div><strong>${escapeHTML(track.name)}</strong><small>${track.questions} questions · ${track.due} due</small></div>
      <div class="track-progress"><i style="width:${percent(track.mastery)}"></i></div>
      <span>${percent(track.mastery)}</span>
    </article>`).join("") : '<div class="empty-state">No tracks yet.</div>';

  const materials = $("#recent-materials");
  materials.innerHTML = data.materials.length ? data.materials.slice(0, 4).map(material => `
    <article class="material-row"><div><strong>${escapeHTML(material.title)}</strong><small>${escapeHTML(material.campaign)} · ${material.questions} questions</small></div><span>#${material.id}</span></article>
  `).join("") : '<div class="empty-state">No source material yet.</div>';
  renderExamStrip();
  renderLibrary();
}

function renderLibrary() {
  if (!state.dashboard) return;
  const grid = $("#library-grid");
  const materials = state.dashboard.materials;
  grid.innerHTML = materials.length ? materials.map(material => `
    <article class="library-card">
      <span>${escapeHTML(material.campaign)}</span>
      <h3>${escapeHTML(material.title)}</h3>
      <small>${material.questions} grounded questions · local source #${material.id}</small>
    </article>`).join("") : '<div class="empty-state">Your library is empty. Add one trustworthy source to begin.</div>';
}

function selectedConfidence() {
  return Number($("input[name=confidence]:checked")?.value || 4);
}

function currentQuestion() {
  return state.questions[state.index];
}

async function startSprint() {
  state.campaign = $("#campaign-select").value;
  const button = $("#start-sprint");
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "Preparing your lesson…";
  try {
    const params = new URLSearchParams({campaign: state.campaign});
    const lesson = await api(`/api/lesson?${params}`);
    if (lesson.available && lesson.stage !== "complete") {
      state.lesson = lesson;
      state.lessonCheckIndex = lesson.current_check || 0;
      state.sessionXP = lesson.xp_earned || 0;
      if (lesson.stage === "challenge") await startQuestionSession(lesson);
      else renderLesson(lesson);
    } else {
      state.lesson = null;
      await startQuestionSession();
    }
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

async function startQuestionSession(lesson = null) {
  const requested = state.minutes === 10 ? 6 : state.minutes === 35 ? 20 : 12;
  const params = new URLSearchParams({limit: String(lesson ? 40 : requested), campaign: state.campaign});
  if (lesson) params.set("topic", lesson.topic);
  const session = await api(`/api/session?${params}`);
  if (!session.questions.length) {
    toast(state.dashboard?.questions_count ? "No questions in that track yet." : "Add a source and generate questions first.");
    return;
  }
  let questions = session.questions;
  if (lesson) {
    questions.sort((a, b) =>
      Number(b.topic === lesson.topic) - Number(a.topic === lesson.topic) ||
      Number(b.kind === "transfer") - Number(a.kind === "transfer") ||
      b.difficulty - a.difficulty
    );
    if (questions[0]?.topic === lesson.topic) questions[0].boss = true;
  }
  state.questions = questions.slice(0, requested);
  state.index = 0;
  state.sessionStartedAt = Date.now();
  startTimer();
  setView("study");
  renderQuestion();
}

function setLessonStage(stage) {
  $$(".lesson-stages li").forEach(item => {
    const order = {teach: 0, check: 1, challenge: 2};
    item.classList.toggle("is-current", item.dataset.stage === stage);
    item.classList.toggle("is-complete", order[item.dataset.stage] < order[stage]);
  });
}

function renderLesson(lesson) {
  setView("lesson");
  setLessonStage(lesson.stage === "check" ? "check" : "teach");
  $("#lesson-reading").hidden = false;
  $("#lesson-checks").hidden = true;
  $("#lesson-campaign").textContent = lesson.campaign;
  $("#lesson-topic").textContent = lesson.topic;
  $("#lesson-title").textContent = lesson.title;
  $("#lesson-objective").textContent = lesson.objective;
  $("#lesson-prerequisites").innerHTML = lesson.prerequisites.length
    ? lesson.prerequisites.map(item => `<li>${escapeHTML(item)}</li>`).join("")
    : "<li>Nothing is assumed. We will define every piece before using it.</li>";
  $("#lesson-motivation").textContent = lesson.motivation;
  $("#lesson-primitives").innerHTML = lesson.primitives.map(item => `
    <div><strong>${escapeHTML(item.term)}</strong><p>${escapeHTML(item.meaning)}</p></div>`).join("");
  $("#lesson-derivation").innerHTML = lesson.derivation_steps.map((step, index) => {
    const part = typeof step === "string" ? {claim: step, reason: ""} : step;
    return `<li>
      <span>${String(index + 1).padStart(2,"0")}</span>
      <div class="step-explanation">
        ${part.title ? `<strong>${escapeHTML(part.title)}</strong>` : ""}
        <p>${escapeHTML(part.claim || part.text || "")}</p>
        ${part.reason ? `<small><b>Why:</b> ${escapeHTML(part.reason)}</small>` : ""}
      </div>
    </li>`;
  }).join("");
  const example = lesson.worked_example;
  $("#worked-example").innerHTML = `
    <p class="example-problem">${escapeHTML(example.problem || "")}</p>
    <ol>${(example.steps || []).map(step => {
      const part = typeof step === "string" ? {action: step, reason: ""} : step;
      return `<li><div class="step-explanation"><p>${escapeHTML(part.action || part.text || "")}</p>${part.reason ? `<small><b>Because:</b> ${escapeHTML(part.reason)}</small>` : ""}</div></li>`;
    }).join("")}</ol>
    <p class="example-answer"><span>Therefore</span>${escapeHTML(example.answer || "")}</p>`;
  $("#lesson-misconception").textContent = lesson.misconception;
  $("#lesson-source-quote").textContent = lesson.source_quote;
  $("#lesson-material").textContent = lesson.material;
  $("#lesson-xp").textContent = `${state.sessionXP} XP`;
  renderMath($("#lesson-reading"));
  if (lesson.stage === "check") beginChecks();
  else window.scrollTo({top: 0});
}

function beginChecks() {
  const lesson = state.lesson;
  if (!lesson) return;
  setLessonStage("check");
  $("#lesson-reading").hidden = true;
  $("#lesson-checks").hidden = false;
  renderLessonCheck();
  window.scrollTo({top: 0, behavior: "smooth"});
}

function renderLessonCheck() {
  const lesson = state.lesson;
  const index = state.lessonCheckIndex;
  const check = lesson?.checks[index];
  if (!lesson || !check) return startQuestionSession(lesson);
  state.lessonCheckResult = null;
  $("#check-count").textContent = `${index + 1} / ${lesson.checks.length}`;
  $("#check-prompt").textContent = check.prompt;
  $("#check-feedback").hidden = true;
  $("#next-check").hidden = true;
  $("#check-choices").innerHTML = check.choices.map((choice, choiceIndex) => `
    <button data-index="${choiceIndex}"><kbd>${choiceIndex + 1}</kbd><span>${escapeHTML(choice)}</span></button>`).join("");
  $$("#check-choices button").forEach(button => button.addEventListener("click", () => submitLessonCheck(Number(button.dataset.index))));
  renderMath($("#lesson-checks"));
}

async function submitLessonCheck(selectedChoice) {
  const lesson = state.lesson;
  if (!lesson || state.lessonCheckResult) return;
  $$("#check-choices button").forEach(button => button.disabled = true);
  try {
    const result = await api("/api/lesson-check", {
      method: "POST",
      body: JSON.stringify({lesson_id: lesson.id, check_index: state.lessonCheckIndex, selected_choice: selectedChoice}),
    });
    state.lessonCheckResult = result;
    const buttons = $$("#check-choices button");
    buttons[result.correct_choice]?.classList.add("is-correct");
    if (!result.correct) buttons[selectedChoice]?.classList.add("is-wrong");
    $("#check-feedback").hidden = false;
    $("#check-result").textContent = result.correct ? "Yes — that is the structural idea." : "Not yet — repair this layer before moving on.";
    $("#check-explanation").textContent = result.explanation;
    $("#check-reward").textContent = result.xp_gained ? `+${result.xp_gained} understanding XP` : "No penalty. Read the distinction and try again.";
    state.sessionXP += result.xp_gained;
    $("#lesson-xp").textContent = `${state.sessionXP} XP`;
    $("#next-check").hidden = false;
    $("#next-check").innerHTML = result.ready_for_challenge
      ? 'Concept unlocked — enter the challenge <span>→</span>'
      : result.correct ? 'Next layer <span>→</span>' : 'Try this check again <span>↻</span>';
    playSound(result.ready_for_challenge ? "unlock" : result.correct ? "correct" : "incorrect");
    if (result.ready_for_challenge) showAchievement("Challenge unlocked", `${lesson.topic} · scaffold removed`);
    $("#next-check").focus();
  } catch (error) {
    toast(error.message);
    $$("#check-choices button").forEach(button => button.disabled = false);
  }
}

async function advanceLessonCheck() {
  const result = state.lessonCheckResult;
  if (!result) return;
  if (result.ready_for_challenge) {
    setLessonStage("challenge");
    return startQuestionSession(state.lesson);
  }
  if (result.correct) state.lessonCheckIndex = result.current_check;
  renderLessonCheck();
}

function startTimer() {
  clearInterval(state.timer);
  state.timer = setInterval(() => {
    const seconds = Math.floor((Date.now() - state.sessionStartedAt) / 1000);
    $("#session-timer").textContent = `${String(Math.floor(seconds / 60)).padStart(2,"0")}:${String(seconds % 60).padStart(2,"0")}`;
  }, 1000);
}

function renderQuestion() {
  const question = currentQuestion();
  $(".challenge-shell").classList.remove("has-feedback");
  if (!question) return finishSession();
  state.selectedChoice = null;
  state.startedAt = performance.now();
  state.committed = false;
  $("#feedback-panel").hidden = true;
  $("#manual-rating").hidden = true;
  $("#reward-strip").hidden = true;
  $("#next-question").hidden = true;
  $("#submit-answer").disabled = true;
  $("#submit-answer").hidden = false;
  $("#bury-question").hidden = false;
  $$("input[name=confidence]").forEach(input => input.disabled = false);
  $("#session-count").textContent = `${state.index + 1} / ${state.questions.length}`;
  $("#session-bar").style.width = `${state.index * 100 / state.questions.length}%`;
  $("#study-xp").textContent = `${state.sessionXP} XP`;
  $("#mode-badge").textContent = question.mode === "recognition" ? "Recognition" : "True recall";
  $("#challenge-track").textContent = question.campaign;
  $("#challenge-topic").textContent = question.topic;
  $("#question-heading").textContent = question.prompt;
  $("#question-material").textContent = `${question.material} · ${question.kind} · difficulty ${question.difficulty}/5 · mastery ${percent(question.mastery)}`;
  $("#boss-banner").hidden = !question.boss;
  $("#boss-target").textContent = `Beat ${question.target_seconds}s for bonus`;
  $("#heat").textContent = `Heat ×${state.dashboard?.profile.combo || 0}`;

  const choices = $("#choice-grid");
  const recall = $("#recall-box");
  if (question.mode === "recognition") {
    choices.hidden = false;
    recall.hidden = true;
    choices.innerHTML = question.choices.map((choice, index) => `
      <button class="choice" data-index="${index}" data-value="${escapeHTML(choice)}"><kbd>${index + 1}</kbd><span>${escapeHTML(choice)}</span></button>
    `).join("");
    $$(".choice", choices).forEach(button => button.addEventListener("click", () => selectChoice(Number(button.dataset.index))));
  } else {
    choices.hidden = true;
    choices.innerHTML = "";
    recall.hidden = false;
    $("#answer-input").value = "";
    $("#answer-input").focus();
  }
  renderMath($("#study-view"));
}

function selectChoice(index) {
  const question = currentQuestion();
  if (!question || state.committed) return;
  state.selectedChoice = index;
  $$(".choice").forEach((button, buttonIndex) => button.classList.toggle("is-selected", buttonIndex === index));
  $("#submit-answer").disabled = false;
}

function responseValue() {
  const question = currentQuestion();
  return question.mode === "recognition" ? (question.choices[state.selectedChoice] || "") : $("#answer-input").value.trim();
}

async function submitAnswer() {
  const question = currentQuestion();
  const response = responseValue();
  if (!question || !response || state.committed) return;
  const payload = {
    question_id: question.id,
    response,
    confidence: selectedConfidence(),
    response_seconds: (performance.now() - state.startedAt) / 1000,
    boss: question.boss,
    mode: question.mode,
    lesson_id: state.lesson && question.topic === state.lesson.topic ? state.lesson.id : 0,
  };
  const button = $("#submit-answer");
  button.disabled = true;
  button.textContent = "Checking…";
  try {
    const preview = await api("/api/review-preview", {method: "POST", body: JSON.stringify(payload)});
    showPreview(preview);
    if (preview.needs_rating) {
      $("#manual-rating").hidden = false;
      $("#manual-rating button").focus();
    } else {
      await commitReview(preview.suggested_rating, payload);
    }
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  } finally {
    button.innerHTML = 'Check answer <span>⌘↵</span>';
  }
}

function showPreview(preview) {
  const panel = $("#feedback-panel");
  $(".challenge-shell").classList.add("has-feedback");
  panel.hidden = false;
  $("#feedback-badge").textContent = preview.suggested_rating === "good" ? "Signal matched" : "Correction";
  $("#feedback-score").textContent = `estimated match ${Math.round(preview.score * 100)}%`;
  $("#expected-answer").textContent = preview.answer;
  $("#answer-explanation").textContent = preview.explanation;
  $("#source-quote").textContent = preview.source_quote;
  renderMath(panel);
  $("#submit-answer").hidden = true;
  $("#bury-question").hidden = true;
  $$("input[name=confidence]").forEach(input => input.disabled = true);
  panel.scrollIntoView({behavior: "smooth", block: "start"});
}

async function commitReview(rating, initialPayload = null) {
  const question = currentQuestion();
  if (!question || state.committed) return;
  const payload = initialPayload || {
    question_id: question.id,
    response: responseValue(),
    confidence: selectedConfidence(),
    response_seconds: (performance.now() - state.startedAt) / 1000,
    boss: question.boss,
    lesson_id: state.lesson && question.topic === state.lesson.topic ? state.lesson.id : 0,
  };
  payload.rating = rating;
  try {
    const result = await api("/api/reviews", {method: "POST", body: JSON.stringify(payload)});
    state.committed = true;
    state.sessionXP += result.xp_gained + (result.lesson_bonus_xp || 0);
    $("#manual-rating").hidden = true;
    $("#reward-strip").hidden = false;
    $("#next-question").hidden = false;
    const delta = result.mastery - result.old_mastery;
    const totalXP = result.xp_gained + (result.lesson_bonus_xp || 0);
    $("#mastery-delta").textContent = `Mastery +${Math.max(0, Math.round(delta * 100))}%`;
    $("#xp-delta").textContent = `+${totalXP} XP${result.shards_gained ? ` · ◆${result.shards_gained}` : ""}`;
    $("#calibration").textContent = result.calibration;
    $("#feedback-badge").textContent = rating === "again" ? "Weak spot found" : rating === "hard" ? "Rep complete" : rating === "easy" ? "Mastery strike" : "Clean hit";
    $("#study-xp").textContent = `${state.sessionXP} XP`;
    $("#heat").textContent = `Heat ×${result.profile.combo}`;
    playSound(result.lesson_completed ? "complete" : rating === "again" ? "incorrect" : "correct");
    if (result.lesson_completed) {
      showAchievement("Concept cleared", `${question.topic} · +${result.lesson_bonus_xp} mastery bonus`);
      state.lesson.stage = "complete";
    }
    $("#next-question").focus();
  } catch (error) {
    toast(error.message);
  }
}

function nextQuestion() {
  if (!state.committed) return;
  state.index += 1;
  renderQuestion();
}

function finishSession() {
  clearInterval(state.timer);
  const completed = state.questions.length;
  playSound("complete");
  toast(`Sprint clear — ${completed} challenges, +${state.sessionXP} XP.`);
  setView("dashboard");
  loadDashboard();
}

async function buryQuestion() {
  const question = currentQuestion();
  if (!question) return;
  try {
    await api("/api/bury", {method: "POST", body: JSON.stringify({question_id: question.id})});
    toast("Question buried. It will not return.");
    state.questions.splice(state.index, 1);
    if (state.index >= state.questions.length) state.index = 0;
    renderQuestion();
  } catch (error) {
    toast(error.message);
  }
}

function exitStudy() {
  clearInterval(state.timer);
  setView("dashboard");
  loadDashboard();
}

function openImport() {
  const dialog = $("#import-dialog");
  if (!dialog.open) dialog.showModal();
  setTimeout(() => $("#import-title-input").focus(), 50);
}

async function importMaterial(event) {
  event.preventDefault();
  const title = $("#import-title-input").value.trim();
  const content = $("#import-content").value;
  const campaign = $("#import-campaign").value;
  if (!content.trim() && !state.pendingFile) return toast("Paste or choose source material first.");
  const submit = $("#import-form .primary-small");
  submit.disabled = true;
  submit.textContent = "Importing…";
  try {
    let result;
    if (state.pendingFile) {
      result = await api("/api/material-files", {
        method: "POST",
        body: JSON.stringify({
          title,
          campaign,
          filename: state.pendingFile.name,
          data: state.pendingFile.data,
        }),
      });
    } else {
      result = await api("/api/materials", {method: "POST", body: JSON.stringify({title, content, campaign})});
    }
    if ($("#generate-now").checked) {
      try {
        await api("/api/generate", {method: "POST", body: JSON.stringify({material_id: result.material_id})});
        toast(result.created ? "Source imported. Grounded generation started." : "Source already exists. Generation restarted.");
      } catch (error) {
        toast(`Source imported. ${error.message}`);
      }
    } else {
      toast(result.created ? "Source imported." : "That source is already in the library.");
    }
    $("#import-dialog").close();
    $("#import-form").reset();
    state.pendingFile = null;
    await loadDashboard();
  } catch (error) {
    toast(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Import source";
  }
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("Could not read file"));
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.readAsDataURL(file);
  });
}

function bindEvents() {
  $$(".nav-item").forEach(button => button.addEventListener("click", () => setView(button.dataset.view)));
  $$(".duration-group button").forEach(button => button.addEventListener("click", () => {
    state.minutes = Number(button.dataset.minutes);
    $$(".duration-group button").forEach(item => item.classList.toggle("is-selected", item === button));
  }));
  $("#campaign-select").addEventListener("change", event => state.campaign = event.target.value);
  $("#start-sprint").addEventListener("click", startSprint);
  $("#exit-study").addEventListener("click", exitStudy);
  $("#exit-lesson").addEventListener("click", exitStudy);
  $("#begin-checks").addEventListener("click", beginChecks);
  $("#next-check").addEventListener("click", advanceLessonCheck);
  $("#submit-answer").addEventListener("click", submitAnswer);
  $("#next-question").addEventListener("click", nextQuestion);
  $("#bury-question").addEventListener("click", buryQuestion);
  $("#answer-input").addEventListener("input", event => $("#submit-answer").disabled = !event.target.value.trim());
  $$("#manual-rating button").forEach(button => button.addEventListener("click", () => commitReview(button.dataset.rating)));
  ["#open-import", "#rail-add", "#inline-import", "#library-import"].forEach(selector => $(selector).addEventListener("click", openImport));
  $("#refresh-dashboard").addEventListener("click", loadDashboard);
  $("#import-form").addEventListener("submit", importMaterial);
  const soundToggle = $("#sound-toggle");
  const volume = $("#volume-control");
  soundToggle.setAttribute("aria-pressed", String(sound.muted));
  soundToggle.textContent = sound.muted ? "♩̸" : "♪";
  volume.value = String(Math.round(sound.volume * 100));
  soundToggle.addEventListener("click", () => {
    sound.muted = !sound.muted;
    localStorage.setItem("intellect-muted", String(sound.muted));
    soundToggle.setAttribute("aria-pressed", String(sound.muted));
    soundToggle.setAttribute("aria-label", sound.muted ? "Enable sound effects" : "Mute sound effects");
    soundToggle.textContent = sound.muted ? "♩̸" : "♪";
    if (!sound.muted) playSound("correct");
  });
  volume.addEventListener("input", event => {
    sound.volume = Number(event.target.value) / 100;
    localStorage.setItem("intellect-volume", String(event.target.value));
  });
  $("#file-input").addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 24 * 1024 * 1024) {
      event.target.value = "";
      return toast("Files must be 24 MB or smaller.");
    }
    state.pendingFile = {name: file.name, data: await fileAsBase64(file)};
    $("#import-content").value = file.name.toLowerCase().endsWith(".pdf")
      ? `[PDF selected: ${file.name} — text will be extracted locally]`
      : await file.text();
    if (!$("#import-title-input").value) $("#import-title-input").value = file.name.replace(/\.[^.]+$/, "");
  });

  document.addEventListener("keydown", event => {
    const dialogOpen = $("#import-dialog").open;
    const studyVisible = $("#study-view").classList.contains("is-visible");
    const lessonVisible = $("#lesson-view").classList.contains("is-visible");
    if (dialogOpen) return;
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (studyVisible) submitAnswer();
      else if (lessonVisible && !$("#lesson-reading").hidden) beginChecks();
      else startSprint();
      return;
    }
    if (lessonVisible) {
      if (!state.lessonCheckResult && !$("#lesson-checks").hidden && /^[1-4]$/.test(event.key)) {
        event.preventDefault();
        submitLessonCheck(Number(event.key) - 1);
      }
      if (state.lessonCheckResult && event.key === "Enter") {
        event.preventDefault();
        advanceLessonCheck();
      }
      if (event.key === "Escape") exitStudy();
      return;
    }
    if (!studyVisible && !event.metaKey && !event.ctrlKey && !event.altKey) {
      if (event.key.toLowerCase() === "t") setView("dashboard");
      if (event.key.toLowerCase() === "l") setView("library");
      return;
    }
    if (!studyVisible) return;
    const question = currentQuestion();
    if (!question) return;
    if (!state.committed && question.mode === "recognition" && /^[1-4]$/.test(event.key)) {
      event.preventDefault();
      selectChoice(Number(event.key) - 1);
    }
    if (state.committed && event.key === "Enter") {
      event.preventDefault();
      nextQuestion();
    }
    if (event.key === "Escape") exitStudy();
  });
}

buildMasteryField();
bindEvents();
loadDashboard();
