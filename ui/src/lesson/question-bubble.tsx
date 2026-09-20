
import { MathText } from "@/components/math-text";

const mascot = "/assets/mascot.svg";

type QuestionBubbleProps = { question: string };

export const QuestionBubble = ({ question }: QuestionBubbleProps) => {
  return (
    <div className="mb-6 flex items-center gap-x-4">
      <img src={mascot} alt="" aria-hidden width={60} height={60} className="hidden shrink-0 lg:block" />
      <img src={mascot} alt="" aria-hidden width={40} height={40} className="block shrink-0 lg:hidden" />

      <div className="relative rounded-xl border-2 px-4 py-2 text-sm lg:text-base">
        <MathText>{question}</MathText>
        <div
          className="absolute -left-3 top-1/2 h-0 w-0 -translate-y-1/2 rotate-90 transform border-x-8 border-t-8 border-x-transparent"
          aria-hidden
        />
      </div>
    </div>
  );
};
