import { X } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const heart = "/assets/heart.svg";

type HeaderProps = {
  hearts: number;
  percentage: number;
  /* The exam clock is the whole reason this app schedules the way it does, so
     it stays visible while answering rather than only on the path screen. */
  examLabel?: string | null;
  daysLeft?: number | null;
  onExit: () => void;
};

export const Header = ({ hearts, percentage, examLabel, daysLeft, onExit }: HeaderProps) => {
  return (
    <header className="mx-auto w-full max-w-[1140px] px-6 pt-5 lg:px-10 lg:pt-[50px]">
      <div className="flex items-center justify-between gap-x-7">
        <button onClick={onExit} aria-label="Exit session" className="text-slate-500 transition hover:opacity-75">
          <X />
        </button>

        <Progress value={percentage} />

        <div className="flex items-center font-bold text-rose-500">
          <img src={heart} height={28} width={28} alt="" aria-hidden className="mr-2" />
          {hearts}
        </div>
      </div>

      {examLabel && (
        <p
          className={cn(
            "mt-2 text-center text-xs font-bold uppercase tracking-wide text-slate-400",
            daysLeft != null && daysLeft <= 7 && "text-amber-500",
            daysLeft != null && daysLeft <= 2 && "text-rose-500"
          )}
        >
          {examLabel}
        </p>
      )}
    </header>
  );
};
