"""Fetch SpOC4 leaderboard cutoffs (READ-ONLY).

GOALS.md §1: the live cutoffs are the binding falsifiability anchor
for every active hypothesis. Snapshots are written to
`vault/observations/O-NNN-leaderboard-YYYY-MM-DD.md` (by the caller).

Constraint (GOALS.md §4, user.md): the agent never writes to the
internet. Only read-only HTTP is allowed — specifically GraphQL
`query` operations against https://api.optimize.esa.int/graphql/.
No mutation, no submission, no posting.

Query shape confirmed live 2026-06-12 (used for the 04:00 deep-review
refetch of all 6 boards):

    { challenge(id: "<challenge-id>") {
        problems { id name solutions { rank score user { id } } } } }

Usage:
    python scripts/fetch_leaderboards.py            # both challenges, top 10
    python scripts/fetch_leaderboards.py --depth 12
"""

import argparse
import json
import urllib.request

OPTIMIZE_GRAPHQL = "https://api.optimize.esa.int/graphql/"

CHALLENGES = {
    "ch1": "spoc-4-luna-tomato-logistics",
    "ch2": "spoc-4-keplerian-tomato-traveling-salesperson",
}

QUERY = (
    '{ challenge(id: "%s") { problems '
    "{ id name solutions { rank score user { id } } } } }"
)


def fetch_leaderboard(challenge_id: str) -> dict:
    """Return {problem_name: [(rank, score, user_id), ...]} (read-only)."""
    payload = json.dumps({"query": QUERY % challenge_id}).encode()
    req = urllib.request.Request(
        OPTIMIZE_GRAPHQL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    out = {}
    for prob in data["data"]["challenge"]["problems"]:
        rows = [
            (s["rank"], s["score"], (s.get("user") or {}).get("id"))
            for s in prob["solutions"]
        ]
        rows.sort(key=lambda r: (r[0] is None, r[0]))
        out[prob["name"]] = rows
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--depth", type=int, default=10, help="ranks to print")
    args = ap.parse_args()
    for label, cid in CHALLENGES.items():
        print(f"=== {label}: {cid} ===")
        for name, rows in fetch_leaderboard(cid).items():
            print(f"--- {name} ({len(rows)} solutions) ---")
            for rank, score, user in rows[: args.depth]:
                print(f"  r{rank:<3} {score:<16} {user}")


if __name__ == "__main__":
    main()
