"""Order-Degree (Topology) problem plugin.

Given a number of nodes *n* and maximum degree *d*, find an undirected graph
that minimises the diameter subject to those constraints.

Instance and solution are the same kind of object: a DIMACS-like graph file
(``.gph``, plain or gzip-compressed).  The "instance" is a triple ``(n, d, D)``
— node count, max degree, required diameter — and the "solution" is the graph
file itself.

The instance parameters *n*, *d*, and *D* are encoded in the solution filename::

    topology_<n>_<d>.opt.gph   (diameter read from file header)
    topology_<n>_<d>.bst.gph

The Rust checker CLI is::

    check_topology <n> <degree> <diameter> <solution-graph-file>
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class TopologyInstance:
    """Topology (Order-Degree) instance descriptor.

    Attributes:
        n:        Required node count.
        degree:   Maximum allowed node degree.
        diameter: Required maximum diameter (read from solution file header or
                  derived from the BKV).  May be ``None`` if unknown.
        name:     Logical instance name (e.g. ``"topology_15_3"``).
    """

    n: int
    degree: int
    diameter: Optional[int] = None
    name: str = ""


@dataclass
class TopologySolution:
    """A topology solution graph.

    Attributes:
        n:        Node count (from ``p edge`` header).
        edges:    Frozenset of ``(u, v)`` with ``u < v``.
        diameter: Diameter declared in the file's comment header, or ``None``.
        degree:   Max degree declared / computed, or ``None``.
        name:     Logical solution name.
        path:     Local path to the ``.gph`` file.
    """

    n: int
    edges: FrozenSet[Tuple[int, int]]
    diameter: Optional[int] = None
    degree: Optional[int] = None
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise back to DIMACS format."""
        lines = []
        if self.diameter is not None:
            lines.append(f"c Undirected Graph with Diameter {self.diameter}")
        lines.append(f"p edge {self.n} {len(self.edges)}")
        for u, v in sorted(self.edges):
            lines.append(f"e {u} {v}")
        return "\n".join(lines) + "\n"


@register_problem
class TopologyProblem(Problem):
    """Plugin for the Order-Degree (Topology) problem class.

    The "instance" is a logical descriptor ``(n, degree)``; the "solution" is
    a graph stored in a ``.gph`` file.

    Quickstart::

        import qoblib
        top = qoblib.get_problem("topology")
        inst = top.load_instance("topology_15_3")
        sol  = top.load_solution("topology_15_3")
        result = top.check_solution(inst, sol)
        print(result.status, result.objective)   # actual diameter
    """

    slug = "topology"
    description = "Order-Degree / Network Topology"

    def load_instance(self, name: str) -> TopologyInstance:
        """Parse the instance parameters from *name*.

        *name* must encode ``n`` and ``degree``, e.g. ``"topology_15_3"``.
        The diameter is not needed for the instance descriptor; it is read
        from the solution file by :meth:`compute_objective`.
        """
        m = re.match(r"topology[_-](\d+)[_-](\d+)", name)
        if not m:
            raise ValueError(
                f"Cannot extract (n, degree) from instance name {name!r}. "
                "Expected a name like 'topology_15_3'."
            )
        return TopologyInstance(n=int(m.group(1)), degree=int(m.group(2)), name=name)

    def load_solution(self, name: str) -> TopologySolution:
        """Fetch and parse a topology ``.gph`` solution file."""
        path = self.fetch(name, kind="solution")
        sol = _parse_gph(path, name)
        sol.path = path
        m = re.match(r"topology[_-](\d+)[_-](\d+)", name)
        if m and sol.degree is None:
            sol.degree = int(m.group(2))
        return sol

    def compute_objective(
        self,
        instance: TopologyInstance,
        solution: TopologySolution,
    ) -> Optional[float]:
        """Compute the actual graph diameter via BFS and return it.

        The diameter is the objective for the topology problem (minimise it).
        This uses BFS from every node — O(n·(n+m)).
        """
        n = solution.n
        if n == 0:
            return None

        adj: dict[int, list[int]] = {i: [] for i in range(1, n + 1)}
        for u, v in solution.edges:
            adj[u].append(v)
            adj[v].append(u)

        diameter = 0
        for start in range(1, n + 1):
            dist: dict[int, int] = {start: 0}
            queue: deque[int] = deque([start])
            while queue:
                node = queue.popleft()
                for nb in adj[node]:
                    if nb not in dist:
                        dist[nb] = dist[node] + 1
                        queue.append(nb)
            if len(dist) < n:
                return None  # disconnected — let Rust checker report infeasible
            diameter = max(diameter, max(dist.values()))

        return float(diameter)


# ------------------------------------------------------------------ file parsers


def _parse_gph(path: Path, name: str = "") -> TopologySolution:
    """Parse a DIMACS-like .gph topology solution file (plain or gzip)."""
    import gzip

    if path.suffix == ".gz":
        text = gzip.open(path, "rt", encoding="utf-8").read()
    else:
        text = path.read_text(encoding="utf-8")

    n = 0
    edges: list[Tuple[int, int]] = []
    diameter: Optional[int] = None
    degree: Optional[int] = None

    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "c":
            m = re.search(r"[Dd]iameter\s+(\d+)", line)
            if m:
                diameter = int(m.group(1))
            m = re.search(r"[Dd]egree\s+(\d+)", line)
            if m:
                degree = int(m.group(1))
        elif parts[0] == "p" and len(parts) >= 3:
            n = int(parts[2])
        elif parts[0] == "e" and len(parts) >= 3:
            u, v = int(parts[1]), int(parts[2])
            edges.append((min(u, v), max(u, v)))

    return TopologySolution(
        n=n,
        edges=frozenset(edges),
        diameter=diameter,
        degree=degree,
        name=name,
    )
