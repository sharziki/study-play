#!/usr/bin/env python3
"""Rewrite unit headings that were derived from source filenames.

The STAT 350 importer built each heading with `slug.title()` over a URL
fragment, so the learner saw "10.3 Ht For Mean Sigma Unknown" above the
hypothesis-testing unit and "7.4 Discret Rvs And Clt" above the CLT unit — an
upstream typo included. The heading is the only name that body of material ever
has in the app, so an unreadable heading makes the path unreadable.

`titles.humanize` is idempotent, so this is safe to re-run; it reports only the
rows it actually changes. The importers call the same function, so a re-import
cannot reintroduce the old form.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402
import titles  # noqa: E402


def retitle(db: sqlite3.Connection, verbose: bool = True) -> int:
    changed = 0
    for row in db.execute("SELECT id, title FROM materials").fetchall():
        better = titles.humanize(row[1])
        if better == row[1]:
            continue
        db.execute("UPDATE materials SET title=? WHERE id=?", (better, row[0]))
        if verbose:
            print(f"{row[1]}\n  -> {better}")
        changed += 1
    return changed


def main() -> int:
    db = sqlite3.connect(study.DB_PATH)
    changed = retitle(db)
    db.commit()
    db.close()
    print(f"\n{changed} heading(s) rewritten." if changed else "All headings already readable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
