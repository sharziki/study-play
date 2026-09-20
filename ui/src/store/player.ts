/* Per-device state only: hearts, daily goal, last chosen class.
 *
 * Nothing here is authoritative. Mastery, scheduling, XP totals, and streak
 * live in SQLite on the server, so a cleared browser costs a heart and a goal
 * target, never progress.
 */
import { create } from "zustand";

export const MAX_HEARTS = 5;
export const DEFAULT_DAILY_GOAL = 40;

const KEY_HEARTS = "intellect.hearts";
const KEY_GOAL = "intellect.goal";
const KEY_GOAL_TARGET = "intellect.goalTarget";
const KEY_CLASS = "intellect.campaign";

const today = () => new Date().toISOString().slice(0, 10);

function read<T extends object>(key: string, fallback: T): T {
  try {
    return { ...fallback, ...(JSON.parse(localStorage.getItem(key) || "{}") as T) };
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Private mode. The session still works, it just will not remember. */
  }
}

function initialHearts() {
  const saved = read(KEY_HEARTS, { date: "", hearts: MAX_HEARTS });
  // Hearts refill daily. They exist to slow guess-spamming, not to sell
  // refills, so the penalty never blocks studying for more than one day.
  return saved.date === today() ? Math.max(0, Math.min(MAX_HEARTS, saved.hearts)) : MAX_HEARTS;
}

function initialGoalXP() {
  const saved = read(KEY_GOAL, { date: "", xp: 0 });
  return saved.date === today() ? saved.xp : 0;
}

type PlayerState = {
  hearts: number;
  goalXP: number;
  goalTarget: number;
  campaign: string;
  loseHeart: () => void;
  gainHeart: () => void;
  addGoalXP: (amount: number) => void;
  setGoalTarget: (value: number) => void;
  setCampaign: (value: string) => void;
};

export const usePlayer = create<PlayerState>((set, get) => ({
  hearts: initialHearts(),
  goalXP: initialGoalXP(),
  goalTarget: Number(localStorage.getItem(KEY_GOAL_TARGET)) || DEFAULT_DAILY_GOAL,
  campaign: localStorage.getItem(KEY_CLASS) || "",

  loseHeart: () => {
    const hearts = Math.max(0, get().hearts - 1);
    write(KEY_HEARTS, { date: today(), hearts });
    set({ hearts });
  },
  gainHeart: () => {
    const hearts = Math.min(MAX_HEARTS, get().hearts + 1);
    write(KEY_HEARTS, { date: today(), hearts });
    set({ hearts });
  },
  addGoalXP: (amount) => {
    const goalXP = get().goalXP + Math.max(0, amount || 0);
    write(KEY_GOAL, { date: today(), xp: goalXP });
    set({ goalXP });
  },
  setGoalTarget: (goalTarget) => {
    localStorage.setItem(KEY_GOAL_TARGET, String(goalTarget));
    set({ goalTarget });
  },
  setCampaign: (campaign) => {
    localStorage.setItem(KEY_CLASS, campaign);
    set({ campaign });
  },
}));
