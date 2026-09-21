import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Check, Lightbulb, TriangleAlert, X } from "lucide-react";

import { MathText } from "@/components/math-text";
import { Button } from "@/components/ui/button";
import { Card } from "@/lesson/card";
import { Footer } from "@/lesson/footer";
import { api, type CheckResult, type Lesson } from "@/lib/api";
import { cn } from "@/lib/utils";

/* The teach step.
 *
 * Every lesson the generator writes was unreachable: `/api/lesson` returned a
 * full first-principles lesson — motivation, primitives, a derivation, a
 * worked example, the misconception, and graded checks — and nothing in the
 * interface ever called it. The app could only quiz. This is the half of
 * "teach then test" that was missing.
 *
 * Reading is not learning, so the teach pane ends in checks that are graded by
 * the server. The answer key never reaches the browser: `/api/lesson` omits
 * `correct_choice`, and `/api/lesson-check` returns it only after an attempt.
 */

type LessonViewProps = {
  lessonId?: number;
  campaign?: string;
  onExit: () => void;
};

const Section = ({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof BookOpen;
  label: string;
  children: React.ReactNode;
}) => (
  <section className="space-y-2">
    <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-ink-faint">
      <Icon className="h-3.5 w-3.5" />
      {label}
    </p>
    {children}
  </section>
);

export const LessonView = ({ lessonId, campaign, onExit }: LessonViewProps) => {
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [failed, setFailed] = useState(false);
  const [reading, setReading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [pending, setPending] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .lesson(campaign, lessonId)
      .then((data) => !cancelled && (data.available ? setLesson(data) : setFailed(true)))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [campaign, lessonId]);

  const checkIndex = result?.correct ? result.current_check : lesson?.current_check ?? 0;
  const check = lesson?.checks[checkIndex];

  const submit = useCallback(async () => {
    if (!lesson || selected === null || pending) return;
    setPending(true);
    try {
      setResult(await api.lessonCheck({
        lesson_id: lesson.id,
        check_index: checkIndex,
        selected_choice: selected,
      }));
    } finally {
      setPending(false);
    }
  }, [lesson, selected, pending, checkIndex]);

  const next = useCallback(() => {
    if (result?.correct && result.ready_for_challenge) {
      onExit();
      return;
    }
    setResult(null);
    setSelected(null);
    scroller.current?.scrollTo({ top: 0 });
  }, [result, onExit]);

  if (failed) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-ink-muted">No lesson is ready for this class yet.</p>
        <Button variant="primaryOutline" onClick={onExit}>
          Back to the path
        </Button>
      </div>
    );
  }

  if (!lesson) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-ink-faint">Loading the lesson…</p>
      </div>
    );
  }

  return (
    <>
      <header className="mx-auto w-full max-w-[1140px] px-6 pt-5 lg:px-10 lg:pt-[50px]">
        <div className="flex items-center justify-between gap-4">
          <button onClick={onExit} aria-label="Exit lesson" className="text-ink-muted transition hover:opacity-75">
            <X />
          </button>
          <p className="truncate text-xs font-bold uppercase tracking-wide text-ink-faint">
            {lesson.campaign} · {reading ? "Teach" : `Check ${checkIndex + 1} of ${lesson.checks.length}`}
          </p>
          <span className="w-6" />
        </div>
      </header>

      <div ref={scroller} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[640px] flex-col gap-y-7 px-6 py-8 lg:px-0">
          {reading ? (
            <>
              <div>
                <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-accent">{lesson.topic}</p>
                <MathText as="h1" className="block text-xl font-bold leading-snug text-ink lg:text-3xl">
                  {lesson.title}
                </MathText>
                <MathText as="p" className="mt-3 block leading-relaxed text-ink-muted">
                  {lesson.objective}
                </MathText>
              </div>

              <Section icon={Lightbulb} label="Why it matters">
                <MathText as="p" className="block leading-relaxed text-ink-muted">
                  {lesson.motivation}
                </MathText>
              </Section>

              {lesson.primitives?.length > 0 && (
                <Section icon={BookOpen} label="The pieces">
                  <dl className="space-y-2.5">
                    {lesson.primitives.map((item) => (
                      <div key={item.term} className="lift rounded-xl border border-line bg-surface p-3.5">
                        <MathText as="p" className="block text-sm font-bold text-ink">
                          {item.term}
                        </MathText>
                        <MathText as="p" className="mt-1 block text-sm leading-relaxed text-ink-muted">
                          {item.meaning}
                        </MathText>
                      </div>
                    ))}
                  </dl>
                </Section>
              )}

              {lesson.derivation_steps?.length > 0 && (
                <Section icon={BookOpen} label="Derivation">
                  <ol className="space-y-3">
                    {lesson.derivation_steps.map((step, index) => (
                      <li key={step.title} className="flex gap-3">
                        <span className="tabular mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-line-strong text-xs font-bold text-ink-faint">
                          {index + 1}
                        </span>
                        <div className="min-w-0">
                          <MathText as="p" className="block text-sm font-bold text-ink">
                            {step.title}
                          </MathText>
                          <MathText as="p" className="mt-1 block text-sm leading-relaxed text-ink-muted">
                            {step.claim}
                          </MathText>
                          {step.reason && (
                            <MathText as="p" className="mt-1 block text-sm leading-relaxed text-ink-faint">
                              {step.reason}
                            </MathText>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                </Section>
              )}

              {lesson.worked_example?.problem && (
                <Section icon={BookOpen} label="Worked example">
                  <div className="lift rounded-xl border border-line bg-surface p-4">
                    <MathText as="p" className="block text-sm font-bold text-ink">
                      {lesson.worked_example.problem}
                    </MathText>
                    <ol className="mt-3 space-y-2">
                      {(lesson.worked_example.steps ?? []).map((step, index) => (
                        <li key={index}>
                          <MathText as="p" className="block text-sm leading-relaxed text-ink-muted">
                            {step.action}
                          </MathText>
                          {step.why && (
                            <MathText as="p" className="block text-sm leading-relaxed text-ink-faint">
                              {step.why}
                            </MathText>
                          )}
                        </li>
                      ))}
                    </ol>
                    {lesson.worked_example.answer && (
                      <MathText as="p" className="mt-3 block text-sm font-bold text-correct">
                        {lesson.worked_example.answer}
                      </MathText>
                    )}
                  </div>
                </Section>
              )}

              {lesson.misconception && (
                <Section icon={TriangleAlert} label="The trap">
                  <div className="rounded-xl border border-l-4 border-line border-l-amber-400 bg-amber-400/10 p-4">
                    <MathText as="p" className="block text-sm leading-relaxed text-ink-muted">
                      {lesson.misconception}
                    </MathText>
                  </div>
                </Section>
              )}

              {lesson.source_quote && (
                /* Every lesson is written from real course material and shows
                   the sentence it came from. This is the line between a tutor
                   and a plausible-sounding guess. */
                <blockquote className="border-l-4 border-line-strong pl-3 text-xs italic leading-relaxed text-ink-faint">
                  <MathText>{lesson.source_quote}</MathText>
                </blockquote>
              )}
            </>
          ) : (
            <>
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-faint">{lesson.topic}</p>
                <MathText as="h1" className="block text-lg font-bold leading-snug text-ink lg:text-2xl">
                  {check?.prompt ?? ""}
                </MathText>
              </div>

              <div className="grid grid-cols-1 gap-2">
                {(check?.choices ?? []).map((choice, index) => (
                  <Card
                    key={`${index}-${choice.slice(0, 24)}`}
                    text={choice}
                    shortcut={`${index + 1}`}
                    selected={selected === index}
                    status={result ? (result.correct ? "correct" : "wrong") : "none"}
                    disabled={!!result}
                    onClick={() => !result && setSelected(index)}
                  />
                ))}
              </div>

              {result && (
                <div
                  className={cn(
                    "state-panel rounded-xl border-2 border-b-4 p-4",
                    result.correct
                      ? "border-correct/50 bg-correct/10 text-correct"
                      : "border-wrong/50 bg-wrong/10 text-wrong"
                  )}
                >
                  {!result.correct && (
                    <>
                      <p className="mb-1 text-xs font-bold uppercase tracking-wide text-ink-faint">Answer</p>
                      <MathText as="p" className="mb-3 block text-sm font-semibold leading-relaxed text-ink">
                        {check?.choices[result.correct_choice] ?? ""}
                      </MathText>
                    </>
                  )}
                  <MathText as="p" className="block text-sm leading-relaxed text-ink-muted">
                    {result.explanation}
                  </MathText>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {reading ? (
        <footer className="h-[100px] border-t-2 border-line pb-[env(safe-area-inset-bottom)] lg:h-[140px]">
          <div className="mx-auto flex h-full max-w-[1140px] items-center justify-between gap-4 px-6 lg:px-10">
            <p className="hidden text-sm text-ink-faint sm:block">
              {lesson.checks.length} check{lesson.checks.length === 1 ? "" : "s"} after this.
            </p>
            <Button variant="secondary" className="ml-auto" onClick={() => setReading(false)}>
              <Check className="mr-2 h-4 w-4" />
              Got it
            </Button>
          </div>
        </footer>
      ) : (
        <Footer
          status={result ? (result.correct ? "correct" : "wrong") : "none"}
          disabled={pending || (!result && selected === null)}
          onCheck={result ? next : () => void submit()}
          checkLabel={
            result
              ? result.correct && result.ready_for_challenge
                ? "Finish"
                : result.correct
                  ? "Continue"
                  : "Try again"
              : "Check"
          }
        />
      )}
    </>
  );
};
