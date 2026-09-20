#!/usr/bin/env python3
"""Top up every under-examined node in a class.

    python3 tools/deepen_bank.py "STAT 350" --target 4

Resumable by construction: it recomputes the thin topics from the database each
time, so a run that is interrupted, rate-limited, or killed loses only the batch
in flight. Re-running picks up exactly where it stopped, which matters because a
full class is an hour of model calls.

The per-material failure is caught and reported rather than raised. One material
that trips the model should not abandon the other sixty.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deepen  # noqa: E402
import study  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", help='class name, e.g. "STAT 350"')
    parser.add_argument("--target", type=int, default=deepen.TARGET_PER_TOPIC,
                        help="questions a node should hold (default %(default)s)")
    parser.add_argument("--limit", type=int, help="stop after this many materials")
    parser.add_argument("--dry-run", action="store_true", help="report the gap without calling the model")
    parser.add_argument("--shard", type=int, default=0,
                        help="this worker's index, for running several in parallel")
    parser.add_argument("--shards", type=int, default=1,
                        help="how many workers are running (default %(default)s)")
    args = parser.parse_args()

    db = deepen.share(study.connect())
    materials = db.execute(
        "SELECT * FROM materials WHERE campaign=? ORDER BY id", (args.campaign,)
    ).fetchall()
    if not materials:
        print(f"No material for {args.campaign!r}.")
        return 1

    # A class is hours of sequential model calls, so the work is split by
    # material. Each worker owns whole materials, which is what makes sharding
    # safe: two workers never generate for the same topic, so they cannot
    # duplicate a question or race on the same node. SQLite serialises the
    # writes, and every worker recomputes its own thin topics from the database.
    if args.shards > 1:
        materials = [m for index, m in enumerate(materials) if index % args.shards == args.shard]
        print(f"shard {args.shard}/{args.shards}: {len(materials)} material(s)")

    if args.dry_run:
        short = 0
        for material in materials:
            thin = deepen.thin_topics(db, material["id"], args.target)
            if thin:
                print(f"{material['title']}: {len(thin)} thin node(s), {sum(n for _, n in thin)} short")
                short += sum(n for _, n in thin)
        print(f"\n{short} question(s) short of target {args.target}.")
        return 0

    started = time.time()
    total_saved = total_requested = 0
    for index, material in enumerate(materials[: args.limit], 1):
        thin = deepen.thin_topics(db, material["id"], args.target)
        if not thin:
            continue
        print(f"[{index}/{len(materials)}] {material['title']}: {len(thin)} thin node(s)", flush=True)
        try:
            saved, requested = deepen.deepen_material(db, material, args.target)
        except Exception as error:  # noqa: BLE001 - one bad material must not end the run
            print(f"   FAILED: {error}", flush=True)
            continue
        total_saved += saved
        total_requested += requested
        print(f"   saved {saved}/{requested}  ({total_saved} so far, "
              f"{(time.time() - started) / 60:.1f} min)", flush=True)

    print(f"\nSaved {total_saved} of {total_requested} requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
