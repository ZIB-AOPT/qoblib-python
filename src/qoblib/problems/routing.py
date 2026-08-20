"""Capacitated Vehicle Routing Problem (CVRP) plugin.

Find minimum-cost vehicle routes from a depot visiting all customers, each
vehicle subject to a capacity constraint.

Instance format: TSPLIB/CVRPLIB ``.vrp`` files.
Solution format::

    Route #1: <customer1> <customer2> ...
    Route #2: ...
    Cost <total-cost>
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class CVRPInstance:
    """A parsed CVRP instance.

    Attributes:
        name:       Instance name.
        n:          Total number of nodes (including depot).
        capacity:   Vehicle capacity.
        coords:     Node coordinates (1-based index).
        demands:    Node demands (1-based index).
        depot:      Depot node (1-based, usually 1).
        path:       Local path to the ``.vrp`` file.
    """

    name: str = ""
    n: int = 0
    capacity: int = 0
    coords: Dict[int, Tuple[float, float]] = field(default_factory=dict)
    demands: Dict[int, int] = field(default_factory=dict)
    depot: int = 1
    path: Optional[Path] = None


@dataclass
class CVRPSolution:
    """A CVRP solution.

    Attributes:
        routes:      List of routes; each route is a list of customer node IDs
                     (excluding the depot).
        claimed_cost: Cost declared in the file's ``Cost`` line (or ``None``).
        name:         Logical solution name.
        path:         Local path to the solution file.
    """

    routes: List[List[int]] = field(default_factory=list)
    claimed_cost: Optional[float] = None
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise to the CVRPLIB solution format."""
        lines = []
        for i, route in enumerate(self.routes, start=1):
            lines.append(f"Route #{i}: " + " ".join(str(c) for c in route))
        if self.claimed_cost is not None:
            lines.append(f"Cost {int(self.claimed_cost)}")
        return "\n".join(lines) + "\n"


@register_problem
class RoutingProblem(Problem):
    """Plugin for the CVRP (Capacitated Vehicle Routing) problem class.

    Quickstart::

        import qoblib
        rt = qoblib.get_problem("routing")
        inst = rt.load_instance("E-n22-k4")
        sol  = rt.load_solution("E-n22-k4")
        result = rt.check_solution(inst, sol)
        print(result.status, result.objective)   # total route cost
    """

    slug = "routing"
    description = "Capacitated Vehicle Routing (CVRP)"

    def load_instance(self, name: str) -> CVRPInstance:
        """Fetch and parse a CVRPLIB ``.vrp`` instance file."""
        path = self.fetch(name, kind="instance")
        inst = _parse_vrp(path, name)
        inst.path = path
        return inst

    def load_solution(self, name: str) -> CVRPSolution:
        """Fetch and parse a CVRP solution file."""
        path = self.fetch(name, kind="solution")
        sol = _parse_solution(path, name)
        sol.path = path
        return sol

    def compute_objective(
        self,
        instance: CVRPInstance,
        solution: CVRPSolution,
    ) -> Optional[float]:
        """Compute the total Euclidean route cost (rounded to nearest integer)."""
        total = 0.0
        for route in solution.routes:
            full_route = [instance.depot] + route + [instance.depot]
            for a, b in zip(full_route, full_route[1:]):
                ax, ay = instance.coords.get(a, (0.0, 0.0))
                bx, by = instance.coords.get(b, (0.0, 0.0))
                total += round(math.sqrt((ax - bx) ** 2 + (ay - by) ** 2))
        return total


# ------------------------------------------------------------------ parsers


def _parse_vrp(path: Path, name: str = "") -> CVRPInstance:
    """Parse a TSPLIB/CVRPLIB .vrp file."""
    inst = CVRPInstance(name=name or path.stem)
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line and not line[0].isdigit():
            key, _, val = line.partition(":")
            key, val = key.strip().upper(), val.strip()
            if key == "NAME":
                inst.name = val
            elif key == "DIMENSION":
                inst.n = int(val)
            elif key == "CAPACITY":
                inst.capacity = int(val)
            continue
        if line.upper().startswith("NODE_COORD_SECTION"):
            section = "coords"
            continue
        elif line.upper().startswith("DEMAND_SECTION"):
            section = "demands"
            continue
        elif line.upper().startswith("DEPOT_SECTION"):
            section = "depot"
            continue
        elif line.upper() in ("EOF", "-1"):
            section = ""
            continue

        parts = line.split()
        if section == "coords" and len(parts) >= 3:
            node, x, y = int(parts[0]), float(parts[1]), float(parts[2])
            inst.coords[node] = (x, y)
        elif section == "demands" and len(parts) >= 2:
            node, demand = int(parts[0]), int(parts[1])
            inst.demands[node] = demand
        elif section == "depot" and parts[0].lstrip("-").isdigit():
            d = int(parts[0])
            if d > 0:
                inst.depot = d
    return inst


def _parse_solution(path: Path, name: str = "") -> CVRPSolution:
    """Parse a CVRP solution file."""
    import re
    sol = CVRPSolution(name=name, path=path)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"Route\s*#\d+\s*:\s*(.*)", line, re.IGNORECASE)
        if m:
            nodes = [int(x) for x in m.group(1).split() if x.isdigit()]
            sol.routes.append(nodes)
            continue
        m = re.match(r"Cost\s+([\d.]+)", line, re.IGNORECASE)
        if m:
            sol.claimed_cost = float(m.group(1))
    return sol
