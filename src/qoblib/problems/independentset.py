"""Maximum Independent Set (07-independentset): find a largest set of pairwise
non-adjacent nodes of a graph."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qoblib._base import Problem, data_lines, read_graph
from qoblib._download import strip_compression


@dataclass(eq=False)
class IndependentSet(Problem):
    """One graph.

    A solution is a collection of node numbers (1-based) that form an
    independent set. The objective is its size.

    Attributes:
        n:     Number of nodes; nodes are numbered from 1.
        edges: Integer array of shape (m, 2), one edge per row.
    """

    n: int
    edges: np.ndarray
    name: str = ""
    path: Path | None = None

    directory = "07-independentset"
    _instance_suffix = ".gph"
    _objective = re.compile(r"stable set size = (\d+)")

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> IndependentSet:
        """Read a graph from a DIMACS ``.gph`` file (optionally compressed)."""
        path = Path(path)
        n, edges = read_graph(path)
        return cls(n, edges, name or Path(strip_compression(path.name)).stem, path)

    def _parse_solution(self, text: str) -> list[int]:
        return [int(token) for line in data_lines(text) for token in line.split()]

    def _format_solution(self, solution) -> str:
        return "".join(f"{int(node)}\n" for node in solution)

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        return [self._instance_path(), solution]
