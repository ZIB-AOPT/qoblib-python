"""Birkhoff decomposition problem plugin.

Given a doubly stochastic matrix *D*, find the minimum number of permutation
matrices and weights such that ``D = Σ λ_i P_i`` with ``Σ λ_i = 1``.

Instances and solutions are JSON files.  The checker operates on full JSON
files (one file may contain many instances), so instance and solution objects
carry the path to the backing file.

References:
    Birkhoff–von Neumann theorem; see also Schicker et al., QOBLIB 2025.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from qoblib._problem import Problem, register_problem


@dataclass
class BirkhoffInstance:
    """A parsed Birkhoff instance.

    Attributes:
        instances: Dict mapping instance IDs to their data dicts.
        name:      Logical name (e.g. ``"qbench_03_sparse"``).
        path:      Local path to the JSON file — used by the Rust checker.
    """

    instances: Dict[str, Any]
    name: str = ""
    path: Optional[Path] = None


@dataclass
class BirkhoffSolution:
    """A Birkhoff solution.

    Attributes:
        solutions: Dict mapping instance IDs to their solution dicts.
        name:      Logical name.
        path:      Local path to the JSON solution file.
    """

    solutions: Dict[str, Any]
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise back to JSON (the Rust checker reads JSON solution files)."""
        return json.dumps(self.solutions, indent=2)


@register_problem
class BirkhoffProblem(Problem):
    """Plugin for the Birkhoff decomposition problem class.

    Quickstart::

        import qoblib
        bk = qoblib.get_problem("birkhoff")
        inst = bk.load_instance("qbench_03_sparse")
        sol  = bk.load_solution("qbench_03_sparse")
        result = bk.check_solution(inst, sol)
        print(result.status, result.objective)   # total permutation count
    """

    slug = "birkhoff"
    description = "Minimum Birkhoff Decomposition"

    def load_instance(self, name: str) -> BirkhoffInstance:
        """Parse a Birkhoff JSON instance file."""
        path = self.fetch(name, kind="instance")
        data = json.loads(path.read_text(encoding="utf-8"))
        instances = {k: v for k, v in data.items() if not k.startswith("_")}
        return BirkhoffInstance(instances=instances, name=name, path=path)

    def load_solution(self, name: str) -> BirkhoffSolution:
        """Parse a Birkhoff JSON solution file."""
        path = self.fetch(name, kind="solution")
        data = json.loads(path.read_text(encoding="utf-8"))
        solutions = {k: v for k, v in data.items() if not k.startswith("_")}
        return BirkhoffSolution(solutions=solutions, name=name, path=path)

    def compute_objective(
        self,
        instance: BirkhoffInstance,
        solution: BirkhoffSolution,
    ) -> Optional[float]:
        """Return the total number of permutation matrices across all sub-instances."""
        return float(sum(
            len(s.get("weights", [])) for s in solution.solutions.values()
        ))
