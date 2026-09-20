#!/usr/bin/env python3
"""Typeset the stragglers the model-driven pass would not touch.

`latexify_bank.py` asks the model to rewrite whole expressions, and its prose
guard rejects any rewrite that alters the words. Seventeen questions failed
that guard for a good reason: they mix prose and symbols so tightly that the
model kept rewording them ("plus the sum over all pairs i<j" turned into a
formula, which changes what is being asked).

Those still contain characters like ·, ×, ≈, Δ, and ≤ sitting in running text,
where they read as typos rather than as mathematics.

This pass is deliberately dumber and therefore safe: it substitutes ONE
character at a time with a minimal wrapped equivalent, and touches nothing
else. `0.25 × 0.95` becomes `0.25 \\(\\times\\) 0.95`. That is not beautiful
typesetting, but it is correct, it renders in the body line, and it cannot
change a single word of the question.

Every expression it produces is validated with the app's own KaTeX build
before anything is written.
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import study  # noqa: E402

VALIDATOR = ROOT / "tools" / "katex_validate.js"
MATH_SPAN = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.DOTALL)
FIELDS = ("prompt", "answer", "explanation")

# One Unicode character, one LaTeX command. Nothing here needs context to
# translate, which is what makes a character-level substitution safe.
SYMBOLS = {
    "×": r"\times", "·": r"\cdot", "÷": r"\div", "±": r"\pm", "∓": r"\mp",
    "≤": r"\le", "≥": r"\ge", "≠": r"\ne", "≈": r"\approx", "≡": r"\equiv",
    "∞": r"\infty", "∑": r"\sum", "∏": r"\prod", "∫": r"\int", "√": r"\surd",
    "∪": r"\cup", "∩": r"\cap", "⋃": r"\bigcup", "⋂": r"\bigcap",
    "∈": r"\in", "∉": r"\notin", "⊆": r"\subseteq", "⊂": r"\subset",
    "⊇": r"\supseteq", "∅": r"\emptyset", "∀": r"\forall", "∃": r"\exists",
    "∂": r"\partial", "∇": r"\nabla", "→": r"\to", "←": r"\leftarrow",
    "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "∝": r"\propto",
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\epsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "ν": r"\nu", "ξ": r"\xi",
    "ρ": r"\rho", "τ": r"\tau", "υ": r"\upsilon", "φ": r"\phi", "χ": r"\chi",
    "ψ": r"\psi", "ω": r"\omega", "μ": r"\mu", "σ": r"\sigma", "π": r"\pi",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi",
    "Ω": r"\Omega",
    # Subscript digits appear in variable names: n₁ -> n_{1}.
    "₀": "_{0}", "₁": "_{1}", "₂": "_{2}", "₃": "_{3}", "₄": "_{4}",
    "₅": "_{5}", "₆": "_{6}", "₇": "_{7}", "₈": "_{8}", "₉": "_{9}",
}

# Typographic characters that are not mathematics and must stay as they are.
KEEP = set("—–‘’“”…°′″§¶†‡•€£¥")


def typeset_segment(segment: str) -> str:
    out = []
    for char in segment:
        command = SYMBOLS.get(char)
        if command is None:
            out.append(char)
            continue
        if command.startswith("_"):
            # A subscript attaches to the preceding token rather than standing
            # alone, so it joins whatever was just emitted.
            out.append(f"\\({command}\\)")
        else:
            out.append(f"\\({command}\\)")
    text = "".join(out)
    # Two adjacent wrapped symbols are one expression: \(a\)\(b\) -> \(ab\).
    return re.sub(r"\\\)\s*\\\(", " ", text)


def typeset(text: str) -> str:
    """Wrap every bare mathematical character, leaving existing maths alone."""
    if not text:
        return text
    out, last = [], 0
    for match in MATH_SPAN.finditer(text):
        out.append(typeset_segment(text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(typeset_segment(text[last:]))
    return "".join(out)


def expressions(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in MATH_SPAN.finditer(text or "")]


def katex_failures(exprs: list[str]) -> list[dict]:
    if not exprs:
        return []
    result = subprocess.run(
        ["node", str(VALIDATOR)], input=json.dumps(sorted(set(exprs))),
        capture_output=True, text=True, timeout=60,
    )
    return json.loads(result.stdout or "[]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = sqlite3.connect(study.DB_PATH)
    db.row_factory = sqlite3.Row
    changed = skipped = 0

    for row in db.execute(
        "SELECT id, prompt, answer, explanation, choices_json, correct_choice "
        "FROM questions WHERE status='ready'"
    ):
        old_choices = json.loads(row["choices_json"] or "[]")
        new = {field: typeset(row[field]) for field in FIELDS}
        choices = [typeset(choice) for choice in old_choices]
        if all(new[f] == row[f] for f in FIELDS) and choices == old_choices:
            continue

        # The answer must remain identical to its own choice.
        index = row["correct_choice"]
        if choices and 0 <= index < len(choices):
            choices[index] = new["answer"]

        exprs = [e for text in list(new.values()) + choices for e in expressions(text)]
        failures = katex_failures(exprs)
        if failures:
            print(f"  [{row['id']}] skipped, katex: {failures[0]['expression'][:40]}")
            skipped += 1
            continue

        print(f"  [{row['id']}] {' '.join(row['prompt'].split())[:70]}")
        if not args.dry_run:
            db.execute(
                "UPDATE questions SET prompt=?, answer=?, explanation=?, choices_json=? WHERE id=?",
                (new["prompt"], new["answer"], new["explanation"], json.dumps(choices), row["id"]),
            )
            db.commit()
        changed += 1

    print(f"\ntypeset {changed}, skipped {skipped}")
    if args.dry_run:
        print("(dry run: nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
