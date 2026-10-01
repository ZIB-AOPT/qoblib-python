"""Capacitated Vehicle Routing (09-routing): serve all customers from one depot
with capacity-limited vehicles at minimum total distance."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qoblib._base import Problem, data_lines


@dataclass(eq=False)
class Routing(Problem):
    """One CVRP instance.

    A solution is a list of routes; each route lists the customers one
    vehicle visits, in order, without the depot. The objective is the total
    distance, with Euclidean distances rounded to the nearest integer.

    Attributes:
        capacity: Vehicle capacity.
        coords:   Array of shape (dimension, 2); row ``i - 1`` holds node ``i``.
        demands:  Demand of every node; the depot has demand 0.
        depot:    Node number of the depot (nodes are numbered from 1).
    """

    capacity: int
    coords: np.ndarray
    demands: np.ndarray
    depot: int
    name: str = ""
    path: Path | None = None

    directory = "09-routing"
    _instance_suffix = ".vrp"
    _objective = re.compile(r"Total cost: (\d+)")

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> Routing:
        """Read an instance from a TSPLIB/CVRPLIB ``.vrp`` file."""
        path = Path(path)
        header: dict[str, str] = {}
        sections: dict[str, list[list[str]]] = {}
        section = None
        for line in data_lines(path.read_text()):
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip()] = value.strip()
            elif line.endswith("_SECTION"):
                section = sections.setdefault(line, [])
            elif line != "EOF" and section is not None:
                section.append(line.split())
        dimension = int(header["DIMENSION"])
        coords = np.zeros((dimension, 2))
        for node, x, y in sections["NODE_COORD_SECTION"]:
            coords[int(node) - 1] = float(x), float(y)
        demands = np.zeros(dimension, dtype=np.int64)
        for node, demand in sections["DEMAND_SECTION"]:
            demands[int(node) - 1] = int(demand)
        depot = int(sections["DEPOT_SECTION"][0][0])
        return cls(int(header["CAPACITY"]), coords, demands, depot, name or path.stem, path)

    def _parse_solution(self, text: str) -> list[list[int]]:
        routes = re.findall(r"^Route\s*#\d+:(.*)$", text, flags=re.MULTILINE)
        return [[int(node) for node in route.split()] for route in routes]

    def _format_solution(self, solution) -> str:
        return "".join(
            f"Route #{number}: {' '.join(str(int(node)) for node in route)}\n"
            for number, route in enumerate(solution, start=1)
        )

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        return [self._instance_path(), solution]
