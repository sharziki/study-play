/* Local-only player state: daily goal, hearts, last chosen class.
 *
 * Nothing here is authoritative. Mastery, scheduling, XP totals, and streak
 * all live in SQLite on the server. This file holds only the things that are
 * per-device and worthless if lost, so a cleared browser never costs progress.
 */

const KEY_GOAL = "intellect.goal";
const KEY_HEARTS = "intellect.hearts";
const KEY_CLASS = "intellect.campaign";
const KEY_GOAL_TARGET = "intellect.goalTarget";

export const DEFAULT_DAILY_GOAL = 40;
export const MAX_HEARTS = 5;

export function today() {
  return new Date().toISOString().slice(0, 10);
}

function read(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "{}");
  } catch (_) {
    return {};
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    /* Private mode. The session still works, it just will not remember. */
  }
}

export function dailyGoalTarget() {
  const saved = Number(localStorage.getItem(KEY_GOAL_TARGET));
  return Number.isFinite(saved) && saved > 0 ? saved : DEFAULT_DAILY_GOAL;
}

export function setDailyGoalTarget(value) {
  localStorage.setItem(KEY_GOAL_TARGET, String(value));
}

export function goalXP() {
  const saved = read(KEY_GOAL);
  return saved.date === today() ? saved.xp || 0 : 0;
}

export function addGoalXP(amount) {
  const value = goalXP() + Math.max(0, amount || 0);
  write(KEY_GOAL, { date: today(), xp: value });
  return value;
}

export function hearts() {
  const saved = read(KEY_HEARTS);
  // Hearts refill daily. They exist to slow down guess-spamming, not to sell
  // refills, so the penalty never blocks studying for more than one day.
  if (saved.date !== today()) return MAX_HEARTS;
  return Math.max(0, Math.min(MAX_HEARTS, saved.hearts ?? MAX_HEARTS));
}

export function loseHeart() {
  const value = Math.max(0, hearts() - 1);
  write(KEY_HEARTS, { date: today(), hearts: value });
  return value;
}

export function selectedClass() {
  return localStorage.getItem(KEY_CLASS) || "All";
}

export function setSelectedClass(name) {
  localStorage.setItem(KEY_CLASS, name);
}
