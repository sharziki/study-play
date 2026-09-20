/* The only place the UI talks to the server.
 *
 * SQLite behind web.py owns mastery, scheduling, XP, and streak. Nothing in
 * this app may invent those numbers locally, or a cleared browser would
 * silently rewrite six weeks of review history.
 */

export type PathNode = {
  topic: string;
  questions: number;
  mastery: number;
  due: number;
  reviews: number;
  lesson_id: number | null;
  kind: "practice" | "transfer" | "lesson";
  state: "current" | "open" | "locked" | "done";
};

export type PathUnit = {
  material_id: number;
  title: string;
  campaign: string;
  course: string | null;
  days_left: number | null;
  exam_title: string | null;
  nodes: PathNode[];
};

export type Question = {
  id: number;
  prompt: string;
  topic: string;
  kind: string;
  difficulty: number;
  material: string;
  campaign: string;
  course: string | null;
  exam_days_left: number | null;
  mastery: number;
  mode: "recognition" | "recall";
  choices?: string[];
  boss: boolean;
  target_seconds: number;
};

export type Profile = {
  xp: number;
  combo: number;
  best_combo: number;
  shards: number;
  daily_streak: number;
  rank: string;
  next_rank_xp: number;
  companion: string;
};

export type Dashboard = {
  profile: Profile;
  due_count: number;
  materials_count: number;
  questions_count: number;
  reviews_count: number;
  strong_recall: number;
  tracks: { name: string; materials: number; questions: number; mastery: number; due: number }[];
  topics: { name: string; campaign: string; mastery: number; questions: number; lapses: number }[];
};

export type Rating = "again" | "hard" | "good" | "easy";

export type Preview = {
  question_id: number;
  answer: string;
  explanation: string;
  source_quote: string;
  score: number;
  missing_terms: string[];
  suggested_rating: Rating;
  /* Recognition grades itself. Free recall sometimes cannot be graded by
     string match, and then the learner rates their own attempt. */
  needs_rating: boolean;
};

export type Commit = {
  question_id: number;
  rating: Rating;
  answer: string;
  explanation: string;
  source_quote: string;
  xp_gained: number;
  pressure_bonus: number;
  shards_gained: number;
  lesson_completed: boolean;
  lesson_bonus_xp: number;
  old_mastery: number;
  mastery: number;
  next_due_at: string;
  interval_days: number;
  calibration: string;
  profile: Profile;
};

export type ClassSummary = {
  name: string;
  title: string;
  short: string;
  materials: number;
  questions: number;
  topics: number;
  mastery: number;
  due: number;
  next_exam: string | null;
  exam_date: string | null;
  days_left: number | null;
};

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    // The server sends a human-readable reason for generation and import
    // failures. Surfacing it beats a generic "something went wrong".
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) detail = body.error;
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail);
  }
  return (await res.json()) as T;
}

function query(path: string, params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

export const api = {
  dashboard: () => request<Dashboard>("/api/dashboard"),

  classes: () => request<{ classes: ClassSummary[] }>("/api/classes"),

  path: (campaign?: string) => request<{ units: PathUnit[] }>(query("/api/path", { campaign })),

  session: (params: { campaign?: string; topic?: string; limit?: number }) =>
    request<{ questions: Question[] }>(query("/api/session", params)),

  reviewPreview: (payload: {
    question_id: number;
    response: string;
    confidence: number;
    mode: "recognition" | "recall";
  }) => request<Preview>("/api/review-preview", { method: "POST", body: JSON.stringify(payload) }),

  commitReview: (payload: {
    question_id: number;
    rating: Rating;
    response: string;
    confidence: number;
    response_seconds: number;
    boss: boolean;
    lesson_id?: number;
  }) => request<Commit>("/api/reviews", { method: "POST", body: JSON.stringify(payload) }),

  bury: (questionId: number) =>
    request<{ ok: boolean }>("/api/bury", { method: "POST", body: JSON.stringify({ question_id: questionId }) }),

  importText: (payload: { title: string; text: string; campaign?: string }) =>
    request<{ material_id: number }>("/api/materials", { method: "POST", body: JSON.stringify(payload) }),
};
