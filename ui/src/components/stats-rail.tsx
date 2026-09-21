
import { Flame } from "lucide-react";

import { cn } from "@/lib/utils";
import { usePlayer } from "@/store/player";
import { UpNext } from "@/learn/up-next";
import type { Assessment, ClassSummary, Dashboard } from "@/lib/api";

const heart = "/assets/heart.svg";
const points = "/assets/points.svg";

type StatsRailProps = {
  dashboard: Dashboard | null;
  classes: ClassSummary[];
  assessments: Assessment[];
  onStartExam: (assessment: Assessment) => void;
};

export const StatsRail = ({ dashboard, classes, assessments, onStartExam }: StatsRailProps) => {
  const { hearts, goalXP, goalTarget, campaign, setCampaign } = usePlayer();
  const profile = dashboard?.profile;

  return (
    <div className="sticky top-0 flex flex-col gap-y-4 pt-4">
      <div className="lift flex items-center justify-between gap-2 rounded-xl border border-line bg-surface p-3 tabular-nums">
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

      <div className="lift rounded-xl border border-line bg-surface p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <p className="text-xs font-bold uppercase tracking-wide text-ink-faint">Today</p>
          <p className="text-xs font-bold text-ink-muted">
            {goalXP}/{goalTarget} XP
          </p>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-surface-raised">
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
              campaign === ""
                ? "border-accent/50 bg-accent/15 text-accent"
                : "border-line text-ink-muted hover:border-line-strong"
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
                campaign === item.name
                  ? "border-accent/50 bg-accent/15 text-accent"
                  : "border-line text-ink-muted hover:border-line-strong",
                // An exam inside two days outranks whatever is selected.
                item.days_left != null && item.days_left <= 2 && "border-wrong/60 text-wrong"
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

      <UpNext assessments={assessments} onStart={onStartExam} />

      {dashboard && (
        <div className="rounded-xl border border-line bg-surface p-3 text-sm text-ink-muted lift">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-faint">Queue</p>
          <p>
            <b className="text-ink">{dashboard.due_count}</b> due ·{" "}
            <b className="text-ink">{dashboard.questions_count}</b> questions
          </p>
        </div>
      )}
    </div>
  );
};
