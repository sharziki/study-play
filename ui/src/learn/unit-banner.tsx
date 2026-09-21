import { NotebookText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type UnitBannerProps = {
  title: string;
  course: string;
  examTitle: string | null;
  daysLeft: number | null;
  onContinue: () => void;
};

export const UnitBanner = ({ title, course, examTitle, daysLeft, onContinue }: UnitBannerProps) => {
  // Colour is the exam clock. Green is normal, amber is inside a week, red is
  // inside two days. Same thresholds the scheduler uses to reorder the queue.
  const urgent = daysLeft != null && daysLeft <= 2;
  const soon = daysLeft != null && daysLeft <= 7;

  return (
    <div
      /* A slab of saturated colour is loud on a dark page and makes its own
         text hard to read. The urgency reads from a coloured left edge and a
         tinted surface instead, which also keeps every banner distinct when
         several are on screen at once. */
      className={cn(
        "lift sticky top-0 z-10 mb-2 flex w-full items-center justify-between gap-4",
        "rounded-xl border border-l-4 bg-surface p-5 text-ink backdrop-blur",
        urgent
          ? "border-line border-l-wrong bg-wrong/10"
          : soon
            ? "border-line border-l-amber-400 bg-amber-400/10"
            : "border-line border-l-correct bg-correct/10"
      )}
    >
      <div className="min-w-0 space-y-1.5">
        <p className="text-xs font-bold uppercase tracking-wide text-ink-faint">{course}</p>
        <h3 className="text-balance text-xl font-bold leading-snug lg:text-2xl">{title}</h3>
        {examTitle && (
          <p className={cn(
            "tabular text-sm",
            urgent ? "text-wrong" : soon ? "text-amber-400" : "text-ink-muted"
          )}>
            {examTitle}
            {daysLeft != null &&
              ` · ${daysLeft <= 0 ? "today" : daysLeft === 1 ? "tomorrow" : `in ${daysLeft} days`}`}
          </p>
        )}
      </div>

      <Button
        size="lg"
        variant="secondary"
        onClick={onContinue}
        className="hidden shrink-0 border-2 border-b-4 active:border-b-2 xl:flex"
      >
        <NotebookText className="mr-2" />
        Continue
      </Button>
    </div>
  );
};
