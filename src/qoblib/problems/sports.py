"""Sports scheduling problem plugin (05-sports).

The sports scheduling problem asks for a round-robin tournament schedule
that satisfies various hard and soft constraints (balanced home/away games,
pattern constraints, break minimization, etc.), following the ITC2021
benchmark format.

No official Rust solution checker is currently shipped in the QOBLIB
repository for this problem class.  This plugin provides:

- Data-access methods (``instances()``, ``fetch()``, ``fetch_all()``) that
  work via the generic download layer.
- ``load_instance()`` / ``load_solution()`` that return the raw file paths.
- ``check_solution()`` raises :exc:`~qoblib.QoblibError` with a clear message
  until a checker is added to the repository.

When a checker is added to the repository, this plugin will be updated.
"""
from __future__ import annotations

from pathlib import Path

from qoblib._core import QoblibError
from qoblib._problem import Problem, register_problem


@register_problem
class SportsProblem(Problem):
    """Plugin for the Sports Scheduling problem class.

    No solution checker is currently available for this problem.
    File download and listing work as usual::

        import qoblib
        sp = qoblib.get_problem("sports")
        sp.instances()
        path = sp.fetch("ITC2021_Super14", kind="instance")
    """

    slug = "sports"
    description = "Sports Scheduling (ITC2021)"

    def load_instance(self, name: str) -> Path:
        """Return the local path to the instance file for *name*."""
        return self.fetch(name, kind="instance")

    def load_solution(self, name: str) -> Path:
        """Return the local path to the solution file for *name*."""
        return self.fetch(name, kind="solution")

    def check_solution(self, instance, solution) -> None:  # type: ignore[override]
        raise QoblibError(
            "No solution checker is currently available for the sports scheduling "
            "problem class.  When a checker is added to the QOBLIB repository this "
            "plugin will be updated automatically."
        )
