"""Network Design (08-network): choose a directed network in which every node
has two incoming and two outgoing edges, and route all demands through it so
that the largest total flow on an edge is as small as possible."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from qoblib._base import Problem
from qoblib._download import fetch


@dataclass(eq=False)
class Network(Problem):
    """The network design instance on the first ``n`` nodes of the demand matrix.

    QOBLIB ships a single 24-node demand matrix, so ``Network(n)`` works for
    every ``n`` up to 24; :meth:`instances` lists the sizes with a reference
    solution.

    A solution is a pair ``(edges, flows)``: the list of directed edges
    ``(i, j)`` of the network, and ``{(k, i, j): flow}`` giving the flow on
    edge ``(i, j)`` that originates at node ``k``. Nodes are numbered from
    1 and flows are integers, scaled by 1000 relative to :attr:`demand`.
    The objective is the largest total flow on an edge.
    """

    n: int

    directory = "08-network"
    _objective = re.compile(r"Computed maximum flow: (\d+)")
    _demand_file = "08-network/instances/demand.txt"

    @property
    def name(self) -> str:
        return f"network{self.n:02d}"

    @cached_property
    def demand(self) -> np.ndarray:
        """Demand matrix of shape (n, n); entry ``[i-1, j-1]`` is the demand from i to j."""
        rows = []
        for line in fetch(self._demand_file).read_text().splitlines():
            if re.match(r"\|\d", line):
                rows.append([int(value) for value in line.split("|")[2].split(",")])
        return np.array(rows, dtype=np.int64)[: self.n, : self.n]

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        return {name: [cls._demand_file] for name in cls._solution_files()}

    @classmethod
    def _build(cls, name: str, paths: list[Path]) -> Network:
        return cls(int(name.removeprefix("network")))

    def _parse_solution(self, text: str) -> tuple[list, dict]:
        edges, flows = [], {}
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            variable, value = line.split()
            kind, *nodes = variable.split("#")
            amount = round(float(value))
            if kind == "x" and amount:
                edges.append(tuple(map(int, nodes)))
            elif kind == "f" and amount:
                flows[tuple(map(int, nodes))] = amount
        return edges, flows

    def _format_solution(self, solution) -> str:
        edges, flows = solution
        lines = [f"x#{i}#{j} 1" for i, j in edges]
        lines += [f"f#{k}#{i}#{j} {int(flow)}" for (k, i, j), flow in flows.items()]
        return "\n".join(lines) + "\n"

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        return [self.n, fetch(self._demand_file), solution]
