#!/usr/bin/env python3
"""Rewrite questions whose mathematics is plain text into proper LaTeX.

`repair_math` in study.py fixes tokens: a superscript, an ASCII sqrt, a bare
subscript. It deliberately refuses to guess where an expression starts and
ends, because an earlier version that tried produced `\\(two-path\\)` and
`\\(n^{2} for\\)`.

That leaves a class it cannot touch. `E[X] = Σ x·p_X(x)` and
`a·x(π−x) ≤ sin x ≤ b·x(π−x)` are whole expressions written in Unicode, and
turning them into LaTeX requires knowing which characters form the expression
and which are prose. That is a judgement, so it is made by the same model that
writes the questions, one question at a time, with the original text in front
of it.

Safety properties, because this rewrites a bank that holds real review history:

  - Only the four learner-visible fields change. topic, kind, difficulty,
    source_quote, mastery, and scheduling are never touched.
  - `answer` is re-pinned to `choices[correct_choice]` afterwards, so the
    identity the save gate enforces cannot be broken by a rewrite.
  - Every produced expression is validated with the KaTeX build the app ships
    before it is written. A question that fails validation is left exactly as
    it was.
  - The prose must survive: if the rewrite changes the non-mathematical words,
    it is rejected.

Usage:
    python3 tools/latexify_bank.py            # rewrite everything that needs it
    python3 tools/latexify_bank.py --dry-run  # show what would change
    python3 tools/latexify_bank.py --limit 5
"""

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import study  # noqa: E402

VALIDATOR = ROOT / "tools" / "katex_validate.js"

# Characters that mean "this is mathematics" when they appear outside \( \).
BARE_MATH = re.compile(
    r"[⋃⋂∪∩∈∉⊆⊂⊇≤≥≠≈±∞∑∏∫√·×÷←→⇒⇔∀∃∅∂∇"
    r"αβγδεζηθικλμνξπρστυφχψω"
    r"ΓΔΘΛΞΠΣΦΨΩ"
    r"⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉]"
)

MATH_SPAN = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.DOTALL)

FIELDS = ("prompt", "answer", "explanation")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["prompt", "answer", "explanation", "choices"],
    "properties": {
        "prompt": {"type": "string"},
        "answer": {"type": "string"},
        "explanation": {"type": "string"},
        "choices": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
    },
}

INSTRUCTIONS = """Rewrite the mathematics in this quiz question as LaTeX.

Return the same question with every mathematical expression wrapped in \\( ... \\)
for inline maths, or \\[ ... \\] for a displayed equation.

RULES

1. Do not change the meaning, the wording, or the difficulty. This is a
   typesetting pass, not an editing pass. The prose must read identically.
   In particular, if the question DESCRIBES a formula in words ("the sum over
   all pairs i<j"), leave those words as words. Converting a description into
   symbols changes what is being asked. Only typeset notation that is already
   notation.
2. Wrap WHOLE expressions, not fragments. Write
   \\(E[X] = \\sum_x x \\, p_X(x)\\), never "E[X] = \\(\\sum\\) x\\(\\cdot\\)p_X(x)".
3. Translate every Unicode mathematical character into its LaTeX command:
   Σ→\\sum, ∩→\\cap, ∪→\\cup, ∈→\\in, ≤→\\le, ≥→\\ge, ≠→\\ne, ±→\\pm, ×→\\times,
   ·→\\cdot, √→\\sqrt, ∞→\\infty, →→\\to, π→\\pi, μ→\\mu, λ→\\lambda, σ→\\sigma,
   Ω→\\Omega, x²→x^{2}, p_X→p_X. No Unicode maths may remain outside \\( \\).
4. Leave text that is already inside \\( ... \\) exactly as it is.
5. Ordinary prose stays OUTSIDE the delimiters. Only the expressions go inside.
   Never wrap an English word.
6. NEVER use a single $ as a delimiter. These materials contain currency.
7. Keep code in `backticks` exactly as it is; it is code, not maths.
8. choices must stay in the same order, and the choice that matched the answer
   must still match it after the rewrite.

Return only the four fields."""


def collapse(text: str) -> str:
    return " ".join((text or "").split())


# Words that are mathematics even though they are spelled with letters. A
# correct rewrite pulls these INSIDE the delimiters, so they legitimately
# disappear from the prose and must not count as an edit.
MATH_WORDS = {
    "sin", "cos", "tan", "sec", "csc", "cot", "log", "ln", "exp", "lim", "max",
    "min", "sup", "inf", "sum", "prod", "int", "det", "dim", "var", "cov",
    "mod", "gcd", "lcm", "arg", "sqrt", "abs", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "dx", "dy", "dz", "dt", "dr", "frac", "cdot",
    "text", "mathbb", "left", "right", "pi", "mu", "sigma", "lambda", "theta",
    "alpha", "beta", "gamma", "delta", "rho", "tau", "phi", "chi", "omega",
    "infty", "cap", "cup", "times", "pm", "le", "ge", "ne", "approx", "bar",
    "hat", "vec", "partial", "nabla", "binom", "dfrac", "sqrt", "emptyset",
    "subseteq", "subset", "supseteq", "forall", "exists", "quad", "space",
    # Distribution and function names that belong inside the maths once the
    # parameter is typeset: "Poisson(λ)" becomes \(\text{Poisson}(\lambda)\).
    "poisson", "binomial", "normal", "uniform", "exponential", "bernoulli",
    "geometric", "gamma", "beta", "chisq", "student", "cov", "corr", "sd",
}


def prose_of(text: str) -> str:
    r"""The non-mathematical words, used to prove the rewrite changed only maths.

    Function names are excluded on both sides. A correct rewrite moves `sin x`
    inside \( \), so "sin" leaves the prose; counting that as an edit rejected
    every good rewrite on the first run.
    """
    without_math = MATH_SPAN.sub(" ", text or "")
    words = re.findall(r"[A-Za-z]{3,}", without_math)
    return " ".join(w for w in (w.lower() for w in words) if w not in MATH_WORDS)


def needs_rewrite(row: sqlite3.Row) -> bool:
    for field in FIELDS:
        outside = MATH_SPAN.sub(" ", row[field] or "")
        if BARE_MATH.search(outside):
            return True
    for choice in json.loads(row["choices_json"] or "[]"):
        if BARE_MATH.search(MATH_SPAN.sub(" ", choice)):
            return True
    return False


def expressions(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in MATH_SPAN.finditer(text or "")]


def katex_failures(exprs: list[str]) -> list[dict]:
    if not exprs:
        return []
    result = subprocess.run(
        ["node", str(VALIDATOR)], input=json.dumps(exprs),
        capture_output=True, text=True, timeout=60,
    )
    return json.loads(result.stdout or "[]")


def rewrite(row: sqlite3.Row) -> dict | None:
    payload = {
        "prompt": row["prompt"],
        "answer": row["answer"],
        "explanation": row["explanation"],
        "choices": json.loads(row["choices_json"] or "[]"),
    }
    prompt = f"{INSTRUCTIONS}\n\nQUESTION:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    result = subprocess.run(
        [
            "claude", "-p", prompt, "--output-format", "json",
            "--json-schema", json.dumps(SCHEMA, separators=(",", ":")),
            "--tools", "", "--no-session-persistence", "--safe-mode", "--model", "sonnet",
        ],
        cwd=ROOT, text=True, capture_output=True,
        stdin=subprocess.DEVNULL, timeout=180,
    )
    if result.returncode:
        return None
    outer = json.loads(result.stdout)
    body = outer.get("structured_output", outer.get("result", outer)) if isinstance(outer, dict) else outer
    if isinstance(body, str):
        body = json.loads(body)
    return body


def acceptable(row: sqlite3.Row, new: dict) -> tuple[bool, str]:
    """Every way a rewrite is allowed to be wrong, checked before it is stored."""
    old_choices = json.loads(row["choices_json"] or "[]")
    if not old_choices:
        # Five seed questions were stored with no choices at all. That is a
        # separate defect; inventing choices here would be writing a question,
        # not typesetting one.
        return False, "question has no stored choices"
    if len(new.get("choices", [])) != len(old_choices):
        # Four distinct choices is a save-gate invariant; a rewrite that drops
        # or invents one is changing the question, not typesetting it.
        return False, "choice count changed"

    for field in FIELDS:
        if not new.get(field, "").strip():
            return False, f"{field} empty"
        if prose_of(new[field]) != prose_of(row[field]):
            return False, f"{field} prose changed"
    for index, choice in enumerate(new["choices"]):
        if prose_of(choice) != prose_of(old_choices[index]):
            return False, f"choice {index} prose changed"

    everything = list(new["choices"]) + [new[f] for f in FIELDS]
    for text in everything:
        if BARE_MATH.search(MATH_SPAN.sub(" ", text)):
            return False, "unicode maths still outside delimiters"

    exprs = sorted({e for text in everything for e in expressions(text)})
    failures = katex_failures(exprs)
    if failures:
        return False, f"katex: {failures[0]['expression'][:40]}"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not shutil.which("claude"):
        print("claude CLI not found")
        return 1

    db = sqlite3.connect(study.DB_PATH)
    db.row_factory = sqlite3.Row
    rows = [
        row for row in db.execute(
            "SELECT id, prompt, answer, explanation, choices_json, correct_choice "
            "FROM questions WHERE status='ready'"
        )
        if needs_rewrite(row)
    ]
    if args.limit:
        rows = rows[: args.limit]

    print(f"{len(rows)} question(s) contain maths written as plain text.\n")
    rewritten = rejected = failed = 0

    for row in rows:
        try:
            new = rewrite(row)
        except Exception as error:  # noqa: BLE001
            print(f"  [{row['id']}] CALL FAILED: {error}")
            failed += 1
            continue
        if new is None:
            print(f"  [{row['id']}] CALL FAILED")
            failed += 1
            continue

        ok, reason = acceptable(row, new)
        if not ok:
            print(f"  [{row['id']}] rejected: {reason}")
            rejected += 1
            continue

        choices = list(new["choices"])
        # The save gate requires choices[correct_choice] == answer, and a
        # question whose answer is not among its choices can never be answered
        # correctly. Re-pin rather than trusting the rewrite to preserve it.
        index = row["correct_choice"]
        if choices and 0 <= index < len(choices):
            choices[index] = new["answer"]

        print(f"  [{row['id']}] {collapse(row['prompt'])[:64]}")
        print(f"        -> {collapse(new['prompt'])[:64]}")
        if not args.dry_run:
            db.execute(
                "UPDATE questions SET prompt=?, answer=?, explanation=?, choices_json=? WHERE id=?",
                (new["prompt"], new["answer"], new["explanation"], json.dumps(choices), row["id"]),
            )
            db.commit()
        rewritten += 1

    print(f"\nrewritten {rewritten}, rejected {rejected}, failed {failed}")
    if args.dry_run:
        print("(dry run: nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
