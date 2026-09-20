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
        "h-full cursor-pointer rounded-xl border-2 border-b-4 p-4 hover:bg-black/5 active:border-b-2 lg:p-6",
        selected && "border-sky-300 bg-sky-100 hover:bg-sky-100",
        selected && status === "correct" && "border-green-300 bg-green-100 hover:bg-green-100",
        selected && status === "wrong" && "border-rose-300 bg-rose-100 hover:bg-rose-100",
        disabled && "pointer-events-none hover:bg-white"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <MathText
          as="p"
          className={cn(
            "text-left text-sm leading-relaxed text-neutral-600 lg:text-base",
            selected && "text-sky-600",
            selected && status === "correct" && "text-green-600",
            selected && status === "wrong" && "text-rose-600"
          )}
        >
          {text}
        </MathText>

        <div
          className={cn(
            "flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded-lg border-2 text-xs font-semibold text-neutral-400 lg:h-[30px] lg:w-[30px] lg:text-[15px]",
            selected && "border-sky-300 text-sky-500",
            selected && status === "correct" && "border-green-500 text-green-500",
            selected && status === "wrong" && "border-rose-500 text-rose-500"
          )}
        >
          {shortcut}
        </div>
      </div>
    </div>
  );
};
