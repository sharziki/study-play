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
      className={cn(
        "sticky top-0 z-10 flex w-full items-center justify-between gap-4 rounded-xl p-5 text-white",
        urgent ? "bg-rose-500" : soon ? "bg-amber-500" : "bg-green-500"
      )}
    >
      <div className="min-w-0 space-y-1.5">
        <p className="text-xs font-bold uppercase tracking-wide opacity-80">{course}</p>
        <h3 className="truncate text-xl font-bold lg:text-2xl">{title}</h3>
        {examTitle && (
          <p className="text-sm opacity-90">
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
