import { useCallback } from "react";
import { useKey } from "react-use";

import { MathText } from "@/components/math-text";
import { cn } from "@/lib/utils";

type CardProps = {
  text: string;
  shortcut: string;
  selected?: boolean;
  onClick: () => void;
  status?: "correct" | "wrong" | "none";
  disabled?: boolean;
};

export const Card = ({ text, shortcut, selected, onClick, status, disabled }: CardProps) => {
  const handleClick = useCallback(() => {
    if (disabled) return;
    onClick();
  }, [disabled, onClick]);

  useKey(shortcut, handleClick, {}, [handleClick]);

  return (
    <div
      onClick={handleClick}
      className={cn(
        "lift h-full cursor-pointer rounded-xl border border-b-2 border-line bg-surface p-4",
        "transition-all duration-150 hover:border-line-strong hover:bg-surface-hover",
        "active:translate-y-px active:border-b lg:p-6",
        selected && "border-accent bg-accent/10 ring-1 ring-accent/60 hover:bg-accent/10",
        selected && status === "correct" && "border-correct bg-correct/15 ring-correct/60 hover:bg-correct/15",
        selected && status === "wrong" && "border-wrong bg-wrong/15 ring-wrong/60 hover:bg-wrong/15",
        disabled && "pointer-events-none hover:bg-surface"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <MathText
          as="p"
          className={cn(
            "text-left text-sm leading-relaxed text-ink-muted lg:text-base",
            selected && "text-ink",
            selected && status === "correct" && "text-correct",
            selected && status === "wrong" && "text-wrong"
          )}
        >
          {text}
        </MathText>

        <div
          className={cn(
            "flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded-lg border-2 border-line-strong text-xs font-semibold text-ink-faint lg:h-[30px] lg:w-[30px] lg:text-[15px]",
            selected && "border-accent text-accent",
            selected && status === "correct" && "border-correct text-correct",
            selected && status === "wrong" && "border-wrong text-wrong"
          )}
        >
          {shortcut}
        </div>
      </div>
    </div>
  );
};
