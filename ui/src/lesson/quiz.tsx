import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Confetti from "react-confetti";
import { useAudio, useKey, useMedia, useWindowSize } from "react-use";
import { toast } from "sonner";


import { MathText } from "@/components/math-text";
import { Button } from "@/components/ui/button";
import { api, type Preview, type Question, type Rating } from "@/lib/api";
import { cn } from "@/lib/utils";
import { usePlayer } from "@/store/player";

import { Challenge } from "./challenge";
import { Footer } from "./footer";
import { Header } from "./header";
import { QuestionBubble } from "./question-bubble";
import { ResultCard } from "./result-card";

const finishSvg = "/assets/finish.svg";

type QuizProps = {
  questions: Question[];
  onExit: () => void;
};

type Status = "none" | "correct" | "wrong";

/* Ratings the learner picks when a free-recall answer cannot be graded by
 * string match. These feed the scheduler directly, which is why the wording
 * is about recall quality rather than about feeling good. */
const SELF_RATINGS: { rating: Rating; label: string }[] = [
  { rating: "again", label: "Missed it" },
  { rating: "hard", label: "Barely" },
  { rating: "good", label: "Got it" },
  { rating: "easy", label: "Instant" },
];

export const Quiz = ({ questions, onExit }: QuizProps) => {
  const [correctAudio, , correctControls] = useAudio({ src: "/assets/correct.wav" });
  const [incorrectAudio, , incorrectControls] = useAudio({ src: "/assets/incorrect.wav" });
  const { width, height } = useWindowSize();

  const { hearts, loseHeart, addGoalXP } = usePlayer();
  const reducedMotion = useMedia("(prefers-reduced-motion: reduce)", false);

  // Escape leaves the session. Without it a keyboard user is trapped once the
  // laptop layout hides nothing but the small X.
  useKey("Escape", () => onExit(), {}, [onExit]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number>();
  const [typed, setTyped] = useState("");
  const [status, setStatus] = useState<Status>("none");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [pending, setPending] = useState(false);
  const [xp, setXP] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [answered, setAnswered] = useState(0);

  const askedAt = useRef(Date.now());
  const startedAt = useRef(Date.now());
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const question = questions[activeIndex];
  const percentage = (activeIndex / questions.length) * 100;

  useEffect(() => {
    askedAt.current = Date.now();
    // Focus is right on a laptop and wrong on a phone, where it throws up the
    // keyboard before the learner has even read the question.
    if (window.matchMedia("(min-width: 900px)").matches) inputRef.current?.focus();
  }, [activeIndex]);

  const response = question?.mode === "recognition" ? (question.choices?.[selectedOption ?? -1] ?? "") : typed.trim();
  const canSubmit = response.length > 0;

  const examLabel = useMemo(() => {
    if (!question?.exam_days_left && question?.exam_days_left !== 0) return null;
    const days = question.exam_days_left;
    const when = days <= 0 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`;
    return `${question.course ?? question.campaign} · exam ${when}`;
  }, [question]);

  const commit = useCallback(
    async (rating: Rating, graded: Preview) => {
      try {
        const result = await api.commitReview({
          question_id: question.id,
          rating,
          response,
          confidence: 4,
          response_seconds: (Date.now() - askedAt.current) / 1000,
          boss: question.boss,
        });
        setXP((prev) => prev + result.xp_gained + result.pressure_bonus);
        addGoalXP(result.xp_gained + result.pressure_bonus);
      } catch {
        // The answer is graded and shown either way. Losing the write would
        // corrupt scheduling silently, so say so out loud.
        toast.error("Answer not saved. Check the connection.");
      }
      const right = rating !== "again";
      setStatus(right ? "correct" : "wrong");
      setAnswered((prev) => prev + 1);
      if (right) {
        setCorrectCount((prev) => prev + 1);
        void correctControls.play();
      } else {
        void incorrectControls.play();
        loseHeart();
      }
      setPreview(graded);
    },
    [addGoalXP, correctControls, incorrectControls, loseHeart, question, response]
  );

  const onCheck = useCallback(async () => {
    if (!canSubmit || pending) return;
    setPending(true);
    try {
      const graded = await api.reviewPreview({
        question_id: question.id,
        response,
        confidence: 4,
        mode: question.mode,
      });
      // Recognition grades itself. Free recall that the server cannot grade by
      // string match waits for the learner's own rating before it is written,
      // because an ungraded write would poison the schedule.
      if (graded.needs_rating) {
        setPreview(graded);
        setStatus("none");
      } else {
        await commit(graded.suggested_rating, graded);
      }
    } catch {
      toast.error("Could not grade that. Try again.");
    } finally {
      setPending(false);
    }
  }, [canSubmit, commit, pending, question, response]);

  const onNext = useCallback(() => {
    setStatus("none");
    setPreview(null);
    setSelectedOption(undefined);
    setTyped("");
    setActiveIndex((current) => current + 1);
  }, []);

  if (!question) {
    const seconds = Math.round((Date.now() - startedAt.current) / 1000);
    const accuracy = answered ? Math.round((correctCount / answered) * 100) : 0;
    return (
      <>
        {!reducedMotion && (
          <Confetti recycle={false} numberOfPieces={400} tweenDuration={8000} width={width} height={height} />
        )}
        <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center gap-y-5 px-6 text-center lg:gap-y-8">
          <img src={finishSvg} alt="" aria-hidden height={100} width={100} />
          <h1 className="text-lg font-bold text-neutral-700 lg:text-3xl">
            Session complete.
            <br />
            {Math.floor(seconds / 60)}m {seconds % 60}s of retrieval.
          </h1>
          <div className="flex w-full items-center gap-x-3">
            <ResultCard variant="points" value={xp} />
            <ResultCard variant="accuracy" value={`${accuracy}%`} />
            <ResultCard variant="hearts" value={hearts} />
          </div>
        </div>
        <Footer status="completed" onCheck={onExit} checkLabel="Done" />
      </>
    );
  }

  const awaitingSelfRating = preview?.needs_rating && status === "none";

  return (
    <>
      {correctAudio}
      {incorrectAudio}
      <Header
        hearts={hearts}
        percentage={percentage}
        examLabel={examLabel}
        daysLeft={question.exam_days_left}
        onExit={onExit}
      />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[600px] flex-col gap-y-8 px-6 py-8 lg:px-0">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">
              {question.topic}
              {question.boss && <span className="ml-2 text-amber-500">Boss round</span>}
            </p>
            <MathText as="h1" className="block text-lg font-bold leading-snug text-neutral-700 lg:text-2xl">
              {question.prompt}
            </MathText>
          </div>

          {question.kind === "transfer" && <QuestionBubble question="New form. Reason it out before answering." />}

          {question.mode === "recognition" ? (
            <Challenge
              options={question.choices ?? []}
              onSelect={(index) => status === "none" && !preview && setSelectedOption(index)}
              status={status}
              selectedOption={selectedOption}
              disabled={pending || status !== "none" || !!preview}
            />
          ) : (
            <textarea
              ref={inputRef}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              disabled={pending || status !== "none" || !!preview}
              rows={4}
              placeholder="Answer from memory, then check."
              className="w-full resize-none rounded-xl border-2 border-b-4 p-4 text-base leading-relaxed outline-none focus:border-sky-300 disabled:bg-slate-50"
            />
          )}

          {awaitingSelfRating && (
            <div className="rounded-xl border-2 border-b-4 p-4">
              <p className="mb-3 text-sm font-bold text-neutral-700">Answer</p>
              <MathText as="p" className="block text-sm leading-relaxed text-neutral-600">
                {preview.answer}
              </MathText>
              <p className="mb-2 mt-4 text-xs font-bold uppercase tracking-wide text-slate-400">
                How did that recall go?
              </p>
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                {SELF_RATINGS.map((item) => (
                  <Button
                    key={item.rating}
                    size="sm"
                    variant={item.rating === "again" ? "dangerOutline" : "primaryOutline"}
                    onClick={() => void commit(item.rating, preview)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {status !== "none" && preview && (
            <div
              className={cn(
                "rounded-xl border-2 border-b-4 p-4",
                status === "correct" ? "border-green-300 bg-green-50" : "border-rose-300 bg-rose-50"
              )}
            >
              {status === "wrong" && (
                <>
                  <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-400">Answer</p>
                  <MathText as="p" className="mb-3 block text-sm leading-relaxed text-neutral-700">
                    {preview.answer}
                  </MathText>
                </>
              )}
              <MathText as="p" className="block text-sm leading-relaxed text-neutral-600">
                {preview.explanation}
              </MathText>
              {preview.source_quote && (
                /* Every question is generated from real course material and
                   must show the exact sentence it came from. This is the line
                   between a tutor and a plausible-sounding guess. */
                <blockquote className="mt-3 border-l-4 border-slate-200 pl-3 text-xs italic leading-relaxed text-slate-500">
                  <MathText>{preview.source_quote}</MathText>
                </blockquote>
              )}
            </div>
          )}
        </div>
      </div>

      <Footer
        status={status}
        disabled={pending || (awaitingSelfRating ? true : status === "none" ? !canSubmit : false)}
        onCheck={status === "none" ? () => void onCheck() : onNext}
        checkLabel={status === "none" ? "Check" : activeIndex === questions.length - 1 ? "Finish" : "Continue"}
      />
    </>
  );
};
