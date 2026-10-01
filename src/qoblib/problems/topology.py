"""Order/Degree Topology (10-topology): find a graph with ``n`` nodes and
maximum degree ``degree`` whose diameter is as small as possible."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from qoblib._base import Problem, read_graph
from qoblib._download import fetch
from qoblib._index import index


@dataclass(eq=False)
class Topology(Problem):
    """The topology instance with ``n`` nodes and maximum degree ``degree``.

    An instance is just this pair of numbers, so ``Topology(n, degree)``
    works for any values; :meth:`instances` lists the ones in QOBLIB.

    A solution is the graph: an (m, 2) array or list of edges ``(u, v)`` with
    nodes numbered from 1. The objective is its diameter. ``check`` takes an
    optional ``max_diameter``; a graph with a larger diameter is then
    reported as infeasible.
    """

    n: int
    degree: int

    directory = "10-topology"
    _instance_suffix = ".dat"
    _objective = re.compile(r"diameter (\d+)")
    _bounds_file = "10-topology/instances/bounds.csv"

    @property
    def name(self) -> str:
        return f"topology_{self.n}_{self.degree}"

    @cached_property
    def bounds(self) -> tuple[int, int] | None:
        """Lower and upper bound on the diameter used by the QOBLIB models, if listed."""
        if self._bounds_file not in index().files:
            return None
        for line in fetch(self._bounds_file).read_text().splitlines()[1:]:
            n, degree, lower, upper = (int(value) for value in line.split(","))
            if (n, degree) == (self.n, self.degree):
                return lower, upper
        return None

    @classmethod
    def _build(cls, name: str, paths: list[Path]) -> Topology:
        n, degree = paths[0].read_text().split()
        return cls(int(n), int(degree))

    def read_solution(self, path) -> np.ndarray:
        return read_graph(path)[1]

    def write_solution(self, solution, path) -> Path:
        edges = np.asarray(solution, dtype=np.int64).reshape(-1, 2)
        path = Path(path)
        with open(path, "w", encoding="utf-8") as out:
            out.write(f"p edge {self.n} {len(edges)}\n")
            np.savetxt(out, edges, fmt="e %d %d")
        return path

    def _checker_args(self, solution: Path, tmp: Path, max_diameter: int | None = None) -> list:
        # The checker rejects graphs whose diameter exceeds the given one; n
        # can only be exceeded by a disconnected graph, which it rejects anyway.
        return [self.n, self.degree, self.n if max_diameter is None else max_diameter, solution]
