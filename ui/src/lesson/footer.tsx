import { CheckCircle, XCircle } from "lucide-react";
import { useKey, useMedia } from "react-use";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type FooterProps = {
  onCheck: () => void;
  status: "correct" | "wrong" | "none" | "completed";
  disabled?: boolean;
  checkLabel?: string;
};

export const Footer = ({ onCheck, status, disabled, checkLabel }: FooterProps) => {
  useKey("Enter", () => !disabled && onCheck(), {}, [onCheck, disabled]);
  const isMobile = useMedia("(max-width: 1024px)", false);

  return (
    <footer
      className={cn(
        "h-[100px] border-t-2 border-line pb-[env(safe-area-inset-bottom)] lg:h-[140px]",
        status === "correct" && "border-correct/40 bg-correct/10",
        status === "wrong" && "border-wrong/40 bg-wrong/10"
      )}
    >
      <div className="mx-auto flex h-full max-w-[1140px] items-center justify-between px-6 lg:px-10">
        {status === "correct" && (
          <div className="flex items-center text-base font-bold text-correct lg:text-2xl">
            <CheckCircle className="mr-4 h-6 w-6 lg:h-10 lg:w-10" />
            Nicely done!
          </div>
        )}

        {status === "wrong" && (
          <div className="flex items-center text-base font-bold text-wrong lg:text-2xl">
            <XCircle className="mr-4 h-6 w-6 lg:h-10 lg:w-10" />
            Not quite.
          </div>
        )}

        <Button
          disabled={disabled}
          aria-disabled={disabled}
          className="ml-auto"
          onClick={onCheck}
          size={isMobile ? "sm" : "lg"}
          variant={status === "wrong" ? "danger" : "secondary"}
        >
          {checkLabel ??
            (status === "none" ? "Check" : status === "completed" ? "Continue" : "Continue")}
        </Button>
      </div>
    </footer>
  );
};
