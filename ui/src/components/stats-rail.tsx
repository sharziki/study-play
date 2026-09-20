
import { Flame } from "lucide-react";

import { cn } from "@/lib/utils";
import { usePlayer } from "@/store/player";
import type { ClassSummary, Dashboard } from "@/lib/api";

const heart = "/assets/heart.svg";
const points = "/assets/points.svg";

type StatsRailProps = {
  dashboard: Dashboard | null;
  classes: ClassSummary[];
};

export const StatsRail = ({ dashboard, classes }: StatsRailProps) => {
  const { hearts, goalXP, goalTarget, campaign, setCampaign } = usePlayer();
  const profile = dashboard?.profile;

  return (
    <div className="sticky top-0 flex flex-col gap-y-4 pt-4">
      <div className="flex items-center justify-between gap-2 rounded-xl border-2 p-3 tabular-nums">
        <div className="flex items-center gap-1.5 font-bold text-orange-500">
          <img src={points} alt="" aria-hidden width={22} height={22} />
          {profile?.xp ?? 0}
        </div>
        <div className="flex items-center gap-1.5 font-bold text-amber-500">
          <Flame className="h-5 w-5 fill-amber-500" />
          {profile?.daily_streak ?? 0}
        </div>
        <div className="flex items-center gap-1.5 font-bold text-rose-500">
          <img src={heart} alt="" aria-hidden width={22} height={22} />
          {hearts}
        </div>
      </div>

      <div className="rounded-xl border-2 p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Today</p>
          <p className="text-xs font-bold text-slate-500">
            {goalXP}/{goalTarget} XP
          </p>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-green-500 transition-all"
            style={{ width: `${Math.min(100, (goalXP / goalTarget) * 100)}%` }}
          />
        </div>
      </div>

      {classes.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCampaign("")}
            className={cn(
              "rounded-full border-2 px-3 py-1 text-xs font-bold uppercase tracking-wide",
              campaign === "" ? "border-sky-300 bg-sky-500/15 text-sky-600" : "text-slate-500"
            )}
          >
            All
          </button>
          {classes.map((item) => (
            <button
              key={item.name}
              onClick={() => setCampaign(item.name)}
              title={`${item.title} · ${item.due} due`}
              className={cn(
                "rounded-full border-2 px-3 py-1 text-xs font-bold uppercase tracking-wide",
                campaign === item.name ? "border-sky-300 bg-sky-500/15 text-sky-600" : "text-slate-500",
                // An exam inside two days outranks whatever is selected.
                item.days_left != null && item.days_left <= 2 && "border-rose-300 text-rose-500"
              )}
            >
              {item.short}
              {item.days_left != null && item.days_left <= 7 && (
                <span className="ml-1 opacity-70">{item.days_left}d</span>
              )}
            </button>
          ))}
        </div>
      )}

      {dashboard && (
        <div className="rounded-xl border-2 p-3 text-sm text-slate-500">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Queue</p>
          <p>
            <b className="text-slate-700">{dashboard.due_count}</b> due ·{" "}
            <b className="text-slate-700">{dashboard.questions_count}</b> questions
          </p>
        </div>
      )}
    </div>
  );
};
