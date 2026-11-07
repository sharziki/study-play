import { Fragment, useLayoutEffect, useRef } from "react";

/* Why single `$` is not a delimiter, preserved from the original app:
 * the stats questions are full of currency ("wins $0 with probability 0.5,
 * $10 with probability 0.3"). Treating `$` as math silently garbles the text
 * between two prices. Authors write \( ... \) for inline math, which is what
 * the generator already emits. */
const DELIMITERS = [
  { left: "$$", right: "$$", display: true },
  { left: "\\[", right: "\\]", display: true },
  { left: "\\(", right: "\\)", display: false },
];

declare global {
  interface Window {
    renderMathInElement?: (el: HTMLElement, options: unknown) => void;
  }
}

/* Inline code spans. The CS 18000 questions are full of real Java
 * (`for (int i = 0; i <= n; i++)`), and without this the learner reads the
 * backticks as literal characters. KaTeX ignores <code>, so a snippet
 * containing ^ or _ cannot be mistaken for maths either. */
/* A fenced block first, then an inline span. The model writes a multi-line
 * snippet as ```java ... ```, and an inline-only pattern cannot match one, so
 * the learner read the backticks and the word "java" as part of the sentence.
 * Fences are matched before spans because a fence contains no newline-free
 * run the inline pattern would find first. */
const CODE_BLOCK = /```[a-zA-Z]*\n?([\s\S]*?)```/g;
const CODE_SPAN = /`([^`\n]+)`/g;

type MathTextProps = {
  children: string | null | undefined;
  className?: string;
  as?: "p" | "h1" | "h2" | "span" | "div";
};

export const MathText = ({ children, className, as: Tag = "span" }: MathTextProps) => {
  const ref = useRef<HTMLElement>(null);
  const text = children == null ? "" : String(children);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || !window.renderMathInElement) return;
    try {
      window.renderMathInElement(node, {
        delimiters: DELIMITERS,
        throwOnError: false,
        // A malformed expression should look wrong, not blow up the session.
        errorColor: "#cf2626",
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
      });
    } catch {
      /* Math is a nicety. A failure here must never block answering. */
    }
  }, [text]);

  // Split on code spans and emit real <code> elements. Everything is rendered
  // as React children rather than innerHTML, so generated content can never
  // inject markup; KaTeX then rewrites only the delimited spans that remain.
  const parts: React.ReactNode[] = [];
  let last = 0;

  type Span = { start: number; end: number; code: string; block: boolean };
  const spans: Span[] = [];
  for (const match of text.matchAll(CODE_BLOCK)) {
    const start = match.index ?? 0;
    spans.push({ start, end: start + match[0].length, code: match[1].trimEnd(), block: true });
  }
  for (const match of text.matchAll(CODE_SPAN)) {
    const start = match.index ?? 0;
    // A backtick inside a fence is part of the fence, not a span of its own.
    if (spans.some((span) => span.block && start >= span.start && start < span.end)) continue;
    spans.push({ start, end: start + match[0].length, code: match[1], block: false });
  }
  spans.sort((a, b) => a.start - b.start);

  for (const span of spans) {
    if (span.start > last) parts.push(text.slice(last, span.start));
    parts.push(
      span.block ? (
        <pre
          key={`${span.start}-block`}
          className="my-2 overflow-x-auto rounded-lg border border-line bg-surface-raised p-3 font-mono text-[0.85em] leading-relaxed text-ink"
        >
          <code>{span.code}</code>
        </pre>
      ) : (
        <code
          key={`${span.start}-${span.code}`}
          className="whitespace-pre-wrap rounded bg-surface-raised px-1 py-0.5 font-mono text-[0.9em] text-ink"
        >
          {span.code}
        </code>
      )
    );
    last = span.end;
  }
  if (last < text.length) parts.push(text.slice(last));

  return (
    <Tag ref={ref as never} className={className}>
      {parts.map((part, index) => (
        <Fragment key={index}>{part}</Fragment>
      ))}
    </Tag>
  );
};
