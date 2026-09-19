/* Math rendering, one place.
 *
 * Real bug this module exists to prevent: the stats questions are full of
 * currency ("wins $0 with probability 0.5, $10 with probability 0.3"), and a
 * single-dollar math delimiter turns the text between two prices into silent
 * garbled math. Single `$` is therefore NOT a delimiter. Authors who want
 * inline math write \( ... \), which is unambiguous and is what the generator
 * already emits.
 *
 * Everything user-visible goes through renderMath(), so there is exactly one
 * definition of what counts as math in this app.
 */

const DELIMITERS = [
  { left: "$$", right: "$$", display: true },
  { left: "\\[", right: "\\]", display: true },
  { left: "\\(", right: "\\)", display: false },
];

const MATH_HINT = /\\[a-zA-Z]{2,}|\$\$|\\\(|\\\[/;

export function hasMath(text) {
  return typeof text === "string" && MATH_HINT.test(text);
}

/** Set text content safely, then typeset any math inside it. */
export function setMath(node, text) {
  if (!node) return;
  node.textContent = text == null ? "" : String(text);
  renderMath(node);
}

/** Typeset an element that already has its content in place. */
export function renderMath(node) {
  if (!node || !window.renderMathInElement) return;
  try {
    window.renderMathInElement(node, {
      delimiters: DELIMITERS,
      throwOnError: false,
      // A malformed expression should look wrong, not blow up the session.
      errorColor: "#cf2626",
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
    });
  } catch (_) {
    /* Math is a nicety. A failure here must never block answering. */
  }
}

export const mathDelimiters = DELIMITERS;
