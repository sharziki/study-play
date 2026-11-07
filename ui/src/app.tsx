import { useCallback, useEffect, useState } from "react";
import { Flame } from "lucide-react";
import { Toaster, toast } from "sonner";

import { StatsRail } from "@/components/stats-rail";
import { Button } from "@/components/ui/button";
import { Learn } from "@/learn/learn";
import { UpNext } from "@/learn/up-next";
import { LessonView } from "@/lesson/lesson-view";
import { Quiz } from "@/lesson/quiz";
import { api, type Assessment, type ClassSummary, type Dashboard, type Question } from "@/lib/api";
import { usePlayer } from "@/store/player";

const SESSION_LENGTH = 10;

export const App = () => {
  const campaign = usePlayer((state) => state.campaign);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [session, setSession] = useState<Question[] | null>(null);
  const [starting, setStarting] = useState(false);
  const [teaching, setTeaching] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [dash, cls, next] = await Promise.all([
        api.dashboard(),
        api.classes(),
        api.assessments(campaign || undefined),
      ]);
      setDashboard(dash);
      setClasses(cls.classes);
      setAssessments(next.assessments);
    } catch {
      /* The path screen reports its own failure; the rail can stay empty. */
    }
    // Selecting a class must re-fetch, or Up Next keeps offering another
    // course's exams after the switch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const start = useCallback(
    async (params: { campaign?: string; topic?: string; exam?: number }) => {
      if (starting) return;
      setStarting(true);
      try {
        const data = await api.session({ ...params, limit: SESSION_LENGTH });
        if (!data.questions.length) {
          toast("Nothing due there. Pick another node or import material.");
          return;
        }
        setSession(data.questions);
      } catch {
        toast.error("Could not start a session.");
      } finally {
        setStarting(false);
      }
    },
    [starting]
  );

  // `?start=1` drops straight into a session, which is what a phone
  // home-screen shortcut points at: studying is one tap from the lock screen
  // rather than three. `?start=CS 18000` pins it to one class, so a class with
  // a distant exam is still reachable in one tap during a week when another
  // class dominates the queue.
  // `?lesson=N` opens one teach step directly. A home-screen shortcut can
  // point at the lesson being worked through, and it is what makes a single
  // lesson checkable in a browser without clicking down the whole path.
  useEffect(() => {
    const lesson = new URLSearchParams(window.location.search).get("lesson");
    if (lesson && Number.isFinite(Number(lesson))) setTeaching(Number(lesson));
  }, []);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("start");
    if (requested === null) return;
    const pinned = requested && requested !== "1" ? requested : undefined;
    void start({ campaign: pinned ?? usePlayer.getState().campaign ?? undefined });
    // Only ever once per load; the param stays in the URL for the shortcut.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exit = useCallback(() => {
    setSession(null);
    setTeaching(null);
    void refresh();
  }, [refresh]);

  if (teaching !== null) {
    return (
      <div className="flex h-[100dvh] flex-col">
        <LessonView lessonId={teaching} campaign={campaign || undefined} onExit={exit} />
        <Toaster position="top-center" />
      </div>
    );
  }

  if (session) {
    return (
      <div className="flex h-[100dvh] flex-col">
        <Quiz questions={session} onExit={exit} />
        <Toaster position="top-center" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[100dvh] max-w-[1056px] flex-col">
      <main className="flex flex-1 gap-x-8 overflow-y-auto px-4 lg:px-6">
        <div className="min-w-0 flex-1">
          {/* On a phone the rail is hidden, so this rides above the path.
              What is on Tuesday's quiz is the most useful thing on the
              screen, and the phone is where he actually studies. */}
          <div className="pt-4 lg:hidden">
            <UpNext assessments={assessments} onStart={(item) => void start({ exam: item.exam_id })} />
          </div>
          <Learn onStart={start} onTeach={setTeaching} />
        </div>
        <aside className="hidden w-[320px] shrink-0 lg:block">
          <StatsRail
            dashboard={dashboard}
            classes={classes}
            assessments={assessments}
            onStartExam={(item) => void start({ exam: item.exam_id })}
          />
        </aside>
      </main>

      {/* On a phone the rail becomes a bar. Same numbers, no second layout. */}
      <div className="border-t-2 px-4 pb-[env(safe-area-inset-bottom)] lg:hidden">
        <div className="flex items-center justify-between gap-3 py-3">
          <StatsRailCompact dashboard={dashboard} />
          <Button variant="secondary" size="sm" disabled={starting} onClick={() => void start({ campaign: campaign || undefined })}>
            {starting ? "Starting…" : "Study now"}
          </Button>
        </div>
      </div>

      <Toaster position="top-center" />
    </div>
  );
};

const StatsRailCompact = ({ dashboard }: { dashboard: Dashboard | null }) => {
  const { hearts, goalXP, goalTarget } = usePlayer();
  return (
    <div className="flex min-w-0 items-center gap-4 text-sm font-bold tabular-nums">
      <span className="flex items-center gap-1.5 text-orange-500">
        <img src="/assets/points.svg" alt="" aria-hidden width={18} height={18} />
        {dashboard?.profile.xp ?? 0}
      </span>
      <span className="flex items-center gap-1.5 text-rose-500">
        <img src="/assets/heart.svg" alt="" aria-hidden width={18} height={18} />
        {hearts}
      </span>
      <span className="flex items-center gap-1.5 text-amber-500">
        <Flame className="h-4 w-4 fill-amber-500" />
        {dashboard?.profile.daily_streak ?? 0}
      </span>
      <span className="truncate text-ink-faint">
        {goalXP}/{goalTarget}
      </span>
    </div>
  );
};
