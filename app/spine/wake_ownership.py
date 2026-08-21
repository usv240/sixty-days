"""Decide which wakes a worker is allowed to claim.

Every project's wakes live in one shared collection, and claiming is a compare and swap: whichever
worker claims first wins. That is exactly the property that makes overlapping scheduler calls safe,
and it is also the failure mode when two services share a database.

A worker that claims a wake it has no handler for still *completes* it. The wake is then done, and
a wake fires once. So a neighbouring service scanning the same collection does not merely duplicate
work, it permanently retires another service's safeguard, silently, with no error anywhere. For a
deadline keeper that means the packet safeguard never runs.

The fix is ownership, not coordination: a scanner claims only the projects it can actually execute.
Wakes belonging to anyone else are left pending for the worker that owns them.
"""

from __future__ import annotations

from typing import Callable

from spine.state import Run
from spine.wake import Wake

RunLookup = Callable[[str], Run | None]


def owning_project(get_run: RunLookup, wake: Wake) -> str | None:
    """The project that registered this wake, or None if its run cannot be resolved."""
    run = get_run(wake.run_id)
    if run is None:
        return None
    return run.project_id.strip().lower()


def project_predicate(get_run: RunLookup, *projects: str) -> Callable[[Wake], bool]:
    """A `dispatch_due` predicate that claims wakes for `projects` and nothing else.

    An unresolvable run is never claimed. Leaving such a wake pending is the safe direction: it
    stays visible and reclaimable, whereas claiming it would complete work no handler understood.
    """
    owned = frozenset(project.strip().lower() for project in projects if project.strip())

    def predicate(wake: Wake) -> bool:
        project = owning_project(get_run, wake)
        return project is not None and project in owned

    return predicate
