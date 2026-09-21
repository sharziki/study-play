import { Check, Crown, Star } from "lucide-react";
import { CircularProgressbarWithChildren } from "react-circular-progressbar";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import "react-circular-progressbar/dist/styles.css";

type LessonButtonProps = {
  index: number;
  totalCount: number;
  locked?: boolean;
  current?: boolean;
  percentage: number;
  label: string;
  onClick: () => void;
};

export const LessonButton = ({
  index,
  totalCount,
  locked,
  current,
  percentage,
  label,
  onClick,
}: LessonButtonProps) => {
  // The snaking trail: nodes drift right, then back left, on an 8-node cycle.
  const cycleIndex = index % 8;
  let indentationLevel: number;
  if (cycleIndex <= 2) indentationLevel = cycleIndex;
  else if (cycleIndex <= 6) indentationLevel = 4 - cycleIndex;
  else indentationLevel = cycleIndex - 8;

  const isFirst = index === 0;
  const isLast = index === totalCount - 1;
  const isCompleted = !current && !locked;
  const Icon = isCompleted ? Check : isLast ? Crown : Star;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={locked}
      aria-label={label}
      title={label}
      className="disabled:pointer-events-none"
    >
      <div
        className="relative"
        style={{
          right: `${indentationLevel * 40}px`,
          // The "Start" badge floats above the node, so a current node needs
          // clearance or the badge lands on top of the node above it.
          marginTop: isFirst ? 60 : current ? 48 : 24,
        }}
      >
        {current ? (
          <div className="relative h-[102px] w-[102px]">
            <div className="lift absolute -top-6 left-2.5 z-10 animate-bounce rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-sm font-bold uppercase tracking-wide text-correct">
              Start
              <div
                className="absolute -bottom-2 left-1/2 h-0 w-0 -translate-x-1/2 transform border-x-8 border-t-8 border-x-transparent border-t-line"
                aria-hidden
              />
            </div>
            <CircularProgressbarWithChildren
              value={Number.isNaN(percentage) ? 0 : percentage}
              /* The trail was a hardcoded light grey, which on a dark page
                 reads as a bright white ring around the current node — the
                 single loudest thing on the screen, for a progress track. */
              styles={{
                path: { stroke: "hsl(152 60% 46%)" },
                trail: { stroke: "hsl(225 10% 20%)" },
              }}
            >
              <Button size="rounded" variant="secondary" className="h-[70px] w-[70px]">
                <Icon className="h-10 w-10 fill-primary-foreground text-primary-foreground" />
              </Button>
            </CircularProgressbarWithChildren>
          </div>
        ) : (
          <Button
            size="rounded"
            variant={locked ? "locked" : "secondary"}
            className="h-[70px] w-[70px]"
          >
            <Icon
              className={cn(
                "h-10 w-10",
                locked
                  ? "fill-ink-faint/40 stroke-ink-faint text-ink-faint"
                  : "fill-primary-foreground text-primary-foreground",
                isCompleted && "fill-none stroke-[4]"
              )}
            />
          </Button>
        )}
      </div>
    </button>
  );
};
