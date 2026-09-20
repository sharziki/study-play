import { useLayoutEffect, useRef } from "react";

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

  // Text is set as a child, never as innerHTML, so generated content cannot
  // inject markup. KaTeX then rewrites only the delimited spans.
  return (
    <Tag ref={ref as never} className={className}>
      {text}
    </Tag>
  );
};
