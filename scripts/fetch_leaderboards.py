"""Fetch SpOC4 leaderboard cutoffs (READ-ONLY).

GOALS.md §1: the live rank-3 cutoff is the binding falsifiability
anchor for every active hypothesis. Snapshots are written to
`vault/observations/O-NNN-leaderboard-YYYY-MM-DD.md`.

Constraint (GOALS.md §4, user.md): the agent never writes to the
internet. Only read-only HTTP is allowed — specifically GraphQL
`query` operations against https://api.optimize.esa.int/graphql/.
No mutation, no submission, no posting.

STUB — fresh-start scaffold 2026-05-18. The concrete GraphQL query
is implemented during frontier bootstrap, once the schema is
confirmed against the live endpoint.
"""

OPTIMIZE_GRAPHQL = "https://api.optimize.esa.int/graphql/"


def fetch_leaderboard(problem: str) -> dict:
    """Return the current leaderboard for `problem` (read-only)."""
    raise NotImplementedError(
        "Implemented during frontier bootstrap — see open-paths.md."
    )


if __name__ == "__main__":
    raise SystemExit(fetch_leaderboard.__doc__)
