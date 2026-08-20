"""Network design problem plugin.

Design a directed network on *n* nodes (5–24) where every node has exactly
two in-edges and two out-edges, minimising the maximum aggregate flow on
any edge while routing a given demand matrix.

Instance structure
------------------
All instances share a single ``demand.txt`` file.  The instance is identified
by the number of nodes *n*, extracted from the solution filename
(``network05.opt.sol`` → *n* = 5).

The Rust checker CLI is::

    check_network <n> <demand-file> <solution-file>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class NetworkInstance:
    """A network design instance.

    Attributes:
        n:           Number of nodes.
        demand:      Demand matrix as ``{(src, dst): demand}`` (scaled ×1000).
        demand_path: Local path to ``demand.txt`` (used by the Rust checker).
        name:        Logical instance name (e.g. ``"network05"``).
    """

    n: int
    demand: Dict[Tuple[int, int], int]
    demand_path: Optional[Path] = None
    name: str = ""


@dataclass
class NetworkSolution:
    """A network design solution (Gurobi-format).

    Attributes:
        objective:    Claimed objective (maximum scaled flow).
        edges:        ``{(i, j): 1/0}`` — topology decisions.
        flows:        ``{(k, i, j): value}`` — commodity flows.
        name:         Logical solution name.
        path:         Local path to the ``.sol`` file.
    """

    objective: Optional[float] = None
    edges: Dict[Tuple[int, int], int] = field(default_factory=dict)
    flows: Dict[Tuple[int, int, int], float] = field(default_factory=dict)
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise back to Gurobi solution format."""
        lines = []
        if self.objective is not None:
            lines.append(f"# Objective value = {self.objective}")
            lines.append(f"z {self.objective}")
        for (i, j), val in sorted(self.edges.items()):
            lines.append(f"x#{i}#{j} {val}")
        for (k, i, j), val in sorted(self.flows.items()):
            lines.append(f"f#{k}#{i}#{j} {val}")
        return "\n".join(lines) + "\n"


@register_problem
class NetworkProblem(Problem):
    """Plugin for the Network Design problem class.

    Quickstart::

        import qoblib
        nd = qoblib.get_problem("network")
        inst = nd.load_instance("network05")
        sol  = nd.load_solution("network05")
        result = nd.check_solution(inst, sol)
        print(result.status, result.objective)   # max flow value
    """

    slug = "network"
    description = "Network Design (Min-Max Flow)"

    def load_instance(self, name: str) -> NetworkInstance:
        """Fetch the shared demand matrix and return a :class:`NetworkInstance`.

        *name* should be a logical instance name like ``"network05"``.
        The number of nodes is extracted from the name.
        """
        import re
        m = re.search(r"(\d+)", name)
        if not m:
            raise ValueError(
                f"Cannot extract node count from instance name {name!r}. "
                "Expected a name like 'network05'."
            )
        n = int(m.group(1))
        demand_path = self.fetch("demand.txt", kind="instance")
        demand = _parse_demand(demand_path, n)
        return NetworkInstance(n=n, demand=demand, demand_path=demand_path, name=name)

    def load_solution(self, name: str) -> NetworkSolution:
        """Fetch and parse a Gurobi-format solution file."""
        path = self.fetch(name, kind="solution")
        sol = _parse_solution(path, name)
        sol.path = path
        return sol

    def compute_objective(
        self,
        instance: NetworkInstance,
        solution: NetworkSolution,
    ) -> Optional[float]:
        """Return the claimed objective from the solution file header."""
        return solution.objective


# ------------------------------------------------------------------ parsers


def _parse_demand(path: Path, n: int) -> Dict[Tuple[int, int], int]:
    """Parse the shared demand.txt file for node count *n*."""
    demand: Dict[Tuple[int, int], int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            try:
                src, dst, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= src <= n and 1 <= dst <= n:
                    demand[(src, dst)] = d
            except ValueError:
                pass
    return demand


def _parse_solution(path: Path, name: str = "") -> NetworkSolution:
    """Parse a Gurobi solution file."""
    import re
    sol = NetworkSolution(name=name, path=path)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = re.search(r"Objective value\s*=\s*([\d.]+)", line)
            if m:
                sol.objective = float(m.group(1))
            continue
        parts = line.split()
        if not parts:
            continue
        key, val = parts[0], parts[1] if len(parts) > 1 else "0"
        if key == "z":
            try:
                sol.objective = float(val)
            except ValueError:
                pass
        elif m := re.fullmatch(r"x#(\d+)#(\d+)", key):
            sol.edges[(int(m.group(1)), int(m.group(2)))] = int(float(val))
        elif m := re.fullmatch(r"f#(\d+)#(\d+)#(\d+)", key):
            sol.flows[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = float(val)
    return sol
