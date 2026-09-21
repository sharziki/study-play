import { cn } from "@/lib/utils";
import type { Assessment } from "@/lib/api";

/* What is coming, and how ready each one is.
 *
 * A course is not preparing for one thing. MA 261 runs a recitation quiz over
 * three named lessons most Tuesdays AND a midterm over sixteen, and those are
 * different pieces of work. Showing only whichever is nearest hides the
 * midterm until the quiz has passed, which is exactly when it is too late to
 * have been revising for it.
 *
 * Readiness is mastery over that assessment's own sections, not over the whole
 * course, because only the first number answers "am I ready for Tuesday".
 */

const KIND_LABEL: Record<string, string> = {
  quiz: "Quiz",
  exam: "Midterm",
  final: "Final",
};

/* A quiz is numbered; an exam usually is not. Pulling the first number out of
 * any title turned "Evening exam 2026-09-30" into "Midterm 2026", which reads
 * as a year. Only a leading "Quiz N" or "Midterm N" counts. */
const label = (item: Assessment) => {
  const base = KIND_LABEL[item.kind] ?? "Exam";
  const numbered = item.exam_title.match(/^(?:quiz|midterm|exam)\s+(\d{1,2})\b/i);
  return numbered ? `${base} ${numbered[1]}` : base;
};

const when = (days: number) =>
  days <= 0 ? "today" : days === 1 ? "tomorrow" : days < 14 ? `in ${days} days` : `in ${Math.round(days / 7)} weeks`;

type Props = {
  assessments: Assessment[];
  onStart: (assessment: Assessment) => void;
};

export const UpNext = ({ assessments, onStart }: Props) => {
  if (!assessments.length) return null;
  // Viewing every class at once, the course matters as much as the kind:
  // "Quiz 4" and "Midterm" from two different courses are otherwise
  // indistinguishable in a three-row list.
  const showCourse = new Set(assessments.map((item) => item.course_code)).size > 1;
  // Three is enough to show the quiz, the midterm behind it, and one more.
  // A full semester of Tuesdays is a calendar, not a study aid.
  const shown = assessments.slice(0, 3);

  return (
    <section className="rounded-xl border border-line bg-surface p-3 lift">
      <p className="mb-2.5 text-xs font-bold uppercase tracking-wide text-ink-faint">Up next</p>
      <ul className="flex flex-col gap-2">
        {shown.map((item) => {
          const urgent = item.days_left <= 2;
          const soon = item.days_left <= 7;
          const percent = Math.round(item.readiness * 100);
          return (
            <li key={item.exam_id}>
              <button
                onClick={() => onStart(item)}
                disabled={!item.questions}
                className={cn(
                  "w-full rounded-lg border border-line bg-surface-raised p-2.5 text-left transition-colors",
                  "hover:border-line-strong hover:bg-surface-hover",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                  urgent && "border-wrong/50"
                )}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm font-bold text-ink">
                    {showCourse && (
                      <span className="mr-1.5 text-ink-faint">{item.course_code}</span>
                    )}
                    {label(item)}
                  </span>
                  <span
                    className={cn(
                      "tabular shrink-0 text-xs font-bold",
                      urgent ? "text-wrong" : soon ? "text-amber-400" : "text-ink-faint"
                    )}
                  >
                    {when(item.days_left)}
                  </span>
                </div>

                <p className="mt-0.5 truncate text-xs text-ink-faint">
                  {item.scope.length ? item.scope.join(" · ") : "scope not published yet"}
                </p>

                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-canvas">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        percent >= 70 ? "bg-correct" : percent >= 35 ? "bg-amber-400" : "bg-wrong"
                      )}
                      style={{ width: `${Math.max(2, percent)}%` }}
                    />
                  </div>
                  <span className="tabular w-16 shrink-0 text-right text-[11px] text-ink-faint">
                    {percent}% · {item.questions}q
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
