import { useCallback, useEffect, useState } from "react";
import { Flame } from "lucide-react";
import { Toaster, toast } from "sonner";

import { StatsRail } from "@/components/stats-rail";
import { Button } from "@/components/ui/button";
import { Learn } from "@/learn/learn";
import { Quiz } from "@/lesson/quiz";
import { api, type ClassSummary, type Dashboard, type Question } from "@/lib/api";
import { usePlayer } from "@/store/player";

const SESSION_LENGTH = 10;

export const App = () => {
  const campaign = usePlayer((state) => state.campaign);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [session, setSession] = useState<Question[] | null>(null);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [dash, cls] = await Promise.all([api.dashboard(), api.classes()]);
      setDashboard(dash);
      setClasses(cls.classes);
    } catch {
      /* The path screen reports its own failure; the rail can stay empty. */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const start = useCallback(
    async (params: { campaign?: string; topic?: string }) => {
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

  // `?start=1` drops straight into a session. This is what a phone home-screen
  // shortcut points at, so studying is one tap from the lock screen rather
  // than three.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("start") === null) return;
    void start({ campaign: usePlayer.getState().campaign || undefined });
    // Only ever once per load; the param stays in the URL for the shortcut.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exit = useCallback(() => {
    setSession(null);
    void refresh();
  }, [refresh]);

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
          <Learn onStart={start} />
        </div>
        <aside className="hidden w-[320px] shrink-0 lg:block">
          <StatsRail dashboard={dashboard} classes={classes} />
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
      <span className="truncate text-slate-400">
        {goalXP}/{goalTarget}
      </span>
    </div>
  );
};
