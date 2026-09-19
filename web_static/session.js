/* The study session, as a state machine with no DOM in it.
 *
 * Keeping this free of rendering is what lets the same loop drive a phone
 * screen and a laptop window without forking the logic. The UI asks it what
 * to show and tells it what the learner did; it never reaches back.
 *
 * Phases: teach -> question -> verdict -> (question | done)
 */

import { api } from "./api.js";
import { addGoalXP, hearts, loseHeart } from "./player.js";

export const PHASES = { TEACH: "teach", QUESTION: "question", VERDICT: "verdict", DONE: "done" };

export class Session {
  constructor({ questions, lesson = null, label = "Study" }) {
    if (!questions || !questions.length) throw new Error("a session needs at least one question");
    this.questions = [...questions];
    this.lesson = lesson;
    this.label = label;
    this.index = 0;
    this.taughtShown = false;
    this.xp = 0;
    this.correct = 0;
    this.answered = 0;
    this.startedAt = Date.now();
    this.questionStartedAt = Date.now();
    this.response = "";
    this.preview = null;
    this.phase = lesson ? PHASES.TEACH : PHASES.QUESTION;
  }

  get question() {
    return this.questions[this.index] || null;
  }

  get total() {
    return this.questions.length + (this.lesson ? 1 : 0);
  }

  get progress() {
    const done = this.index + (this.lesson && this.taughtShown ? 1 : 0);
    return Math.min(1, done / Math.max(1, this.total));
  }

  get accuracy() {
    return this.answered ? this.correct / this.answered : null;
  }

  get elapsedSeconds() {
    return Math.round((Date.now() - this.startedAt) / 1000);
  }

  acknowledgeLesson() {
    this.taughtShown = true;
    this.beginQuestion();
  }

  beginQuestion() {
    this.phase = PHASES.QUESTION;
    this.response = "";
    this.preview = null;
    this.questionStartedAt = Date.now();
  }

  setResponse(value) {
    this.response = value == null ? "" : String(value);
  }

  get canSubmit() {
    const question = this.question;
    if (!question) return false;
    if (question.mode === "recognition") return this.response.length > 0;
    return this.response.trim().length >= 2;
  }

  /** Grade without committing, so the learner sees the verdict before the
   *  scheduler is touched. A commit still has to follow. */
  async check() {
    const question = this.question;
    const seconds = (Date.now() - this.questionStartedAt) / 1000;
    const preview = await api.post("/api/review-preview", {
      question_id: question.id,
      response: this.response,
      confidence: 4,
      mode: question.mode,
    });
    const right = question.mode === "recognition"
      ? this.response === preview.answer
      : ["good", "easy"].includes(preview.suggested_rating);

    this.preview = { ...preview, right, seconds, response: this.response };
    this.phase = PHASES.VERDICT;

    if (!right) {
      loseHeart();
      // A missed item comes back at the end of the set. Getting it right once
      // after failing is what actually moves it, and it stops the set from
      // ending on a miss the learner never saw resolved.
      this.questions.push(question);
    }
    return this.preview;
  }

  get needsSelfRating() {
    return !!(this.preview && this.preview.needs_rating);
  }

  get suggestedRating() {
    if (!this.preview) return "good";
    return this.preview.suggested_rating || (this.preview.right ? "good" : "again");
  }

  /** Commit the rating, advance, and report what changed. */
  async commit(rating) {
    const question = this.question;
    const preview = this.preview;
    if (!preview) throw new Error("nothing to commit yet");
    const result = await api.post("/api/reviews", {
      question_id: question.id,
      rating,
      confidence: 4,
      response: preview.response,
      response_seconds: preview.seconds,
      boss: !!question.boss,
    });
    const gained = (result.xp_gained || 0) + (result.lesson_bonus_xp || 0);
    this.xp += gained;
    this.answered += 1;
    if (["good", "easy"].includes(rating)) this.correct += 1;
    addGoalXP(result.xp_gained || 0);

    this.index += 1;
    if (this.index >= this.questions.length) this.phase = PHASES.DONE;
    else this.beginQuestion();
    return { ...result, gained, phase: this.phase };
  }

  get heartsLeft() {
    return hearts();
  }
}

/** Build a session from the server. The only place session assembly happens. */
export async function loadSession({ topic = null, campaign = null, label = "", lessonId = null, limit = 8 } = {}) {
  const data = await api.query("/api/session", { limit, campaign, topic });
  if (!data.questions || !data.questions.length) return null;

  let lesson = null;
  if (lessonId) {
    try {
      const candidate = await api.query("/api/lesson", { campaign });
      if (candidate.available && candidate.topic === topic) lesson = candidate;
    } catch (_) {
      /* A missing lesson just means straight to practice. */
    }
  }
  return new Session({ questions: data.questions, lesson, label: label || campaign || "Study" });
}
