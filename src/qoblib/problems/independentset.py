"""Maximum Stable Set (Independent Set) problem plugin.

Find a maximum stable set (independent set) in an undirected graph: a subset
of vertices with no two adjacent.

Instance format: DIMACS ``.gph`` files (plain or gzip-compressed)::

    c comment
    p edge <node_count> <edge_count>
    e <node1> <node2>

Solution format: binary ``01...`` string or index list accepted by the
Rust checker, or a plain list of selected 1-based node indices.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional, Set, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class StableSetInstance:
    """A parsed stable-set graph instance.

    Attributes:
        n:      Number of nodes (1-based).
        edges:  Set of edges as ``(u, v)`` with ``u < v``.
        name:   Logical instance name.
        path:   Local path to the ``.gph`` file (used by the Rust checker).
    """

    n: int
    edges: FrozenSet[Tuple[int, int]]
    name: str = ""
    path: Optional[Path] = None


@dataclass
class StableSetSolution:
    """A stable-set solution.

    Attributes:
        selected:  Set of selected 1-based node indices.
        name:      Logical solution name.
        path:      Local path to the solution file (used by the Rust checker).
    """

    selected: Set[int]
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise as a compact ``01...`` string (1-based, length = n)."""
        if not self.selected:
            return ""
        n = max(self.selected)
        return "".join("1" if i in self.selected else "0" for i in range(1, n + 1))


@register_problem
class StableSetProblem(Problem):
    """Plugin for the Maximum Stable Set (Independent Set) problem class.

    Quickstart::

        import qoblib
        ss = qoblib.get_problem("independentset")
        inst = ss.load_instance("is_example")
        sol  = ss.load_solution("is_example")
        result = ss.check_solution(inst, sol)
        print(result.status, result.objective)   # stable-set size
    """

    slug = "independentset"
    description = "Maximum Stable Set (Independent Set)"

    def load_instance(self, name: str) -> StableSetInstance:
        """Fetch and parse a DIMACS ``.gph`` instance file."""
        path = self.fetch(name, kind="instance")
        inst = _parse_gph(path, name)
        inst.path = path
        return inst

    def load_solution(self, name: str) -> StableSetSolution:
        """Fetch and parse a stable-set solution file."""
        path = self.fetch(name, kind="solution")
        sol = _parse_solution(path, name)
        sol.path = path
        return sol

    def compute_objective(
        self,
        instance: StableSetInstance,
        solution: StableSetSolution,
    ) -> Optional[float]:
        """Return the size of the stable set (number of selected nodes)."""
        return float(len(solution.selected))


# ------------------------------------------------------------------ file parsers


def _parse_gph(path: Path, name: str = "") -> StableSetInstance:
    """Parse a DIMACS .gph file (plain or gzip)."""
    import gzip

    if path.suffix == ".gz":
        text = gzip.open(path, "rt", encoding="utf-8").read()
    else:
        text = path.read_text(encoding="utf-8")

    n = 0
    edges: list[Tuple[int, int]] = []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "p" and len(parts) >= 3:
            n = int(parts[2])
        elif parts[0] == "e" and len(parts) >= 3:
            u, v = int(parts[1]), int(parts[2])
            edges.append((min(u, v), max(u, v)))
    return StableSetInstance(n=n, edges=frozenset(edges), name=name)


def _parse_solution(path: Path, name: str = "") -> StableSetSolution:
    """Parse a stable-set solution file (binary string or index list)."""
    text = path.read_text(encoding="utf-8").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]

    selected: Set[int] = set()

    compact = "".join(lines).replace(",", "").replace(" ", "")
    if compact and all(c in "01" for c in compact):
        for i, c in enumerate(compact, start=1):
            if c == "1":
                selected.add(i)
    else:
        for ln in lines:
            try:
                selected.add(int(ln.split()[0]))
            except (ValueError, IndexError):
                pass

    return StableSetSolution(selected=selected, name=name)
