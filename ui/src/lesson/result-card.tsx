
import { cn } from "@/lib/utils";

const heart = "/assets/heart.svg";
const points = "/assets/points.svg";

type ResultCardProps = { value: number | string; variant: "points" | "hearts" | "accuracy" };

const LABELS = { points: "Total XP", hearts: "Hearts left", accuracy: "Accuracy" } as const;

export const ResultCard = ({ value, variant }: ResultCardProps) => {
  return (
    <div
      className={cn(
        "w-full rounded-2xl border-2",
        variant === "points" && "border-orange-400 bg-orange-400",
        variant === "hearts" && "border-rose-500 bg-rose-500",
        variant === "accuracy" && "border-sky-500 bg-sky-500"
      )}
    >
      <div
        className={cn(
          "rounded-t-xl p-1.5 text-center text-xs font-bold uppercase text-white",
          variant === "points" && "bg-orange-400",
          variant === "hearts" && "bg-rose-500",
          variant === "accuracy" && "bg-sky-500"
        )}
      >
        {LABELS[variant]}
      </div>

      <div
        className={cn(
          "flex items-center justify-center rounded-2xl bg-white p-6 text-lg font-bold",
          variant === "points" && "text-orange-400",
          variant === "hearts" && "text-rose-500",
          variant === "accuracy" && "text-sky-500"
        )}
      >
        {variant !== "accuracy" && (
          <img src={variant === "points" ? points : heart} alt="" aria-hidden height={30} width={30} className="mr-1.5" />
        )}
        {value}
      </div>
    </div>
  );
};
