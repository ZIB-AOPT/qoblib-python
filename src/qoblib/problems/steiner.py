"""Node-Disjoint Steiner Trees (04-steiner): connect every group of terminals
by a tree so that no two trees share a node, at minimum total edge cost."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from qoblib._base import Problem, data_lines
from qoblib._index import index

_FILES = ("arcs.dat", "terms.dat", "param.dat", "roots.dat")


def _rows(path: Path) -> list[list[str]]:
    return [line.split() for line in data_lines(path.read_text())] if path.is_file() else []


@dataclass(eq=False)
class Steiner(Problem):
    """One Steiner tree packing instance.

    A solution is a list of ``(node1, node2, net)`` triples, one per edge
    used by the tree of ``net``. The objective is the total edge cost.

    Attributes:
        n_nodes:   Number of nodes; nodes are numbered from 1.
        edges:     ``{(u, v): cost}`` of the undirected edges, with ``u < v``.
        terminals: ``{net: [terminal nodes]}``.
        roots:     ``{net: root terminal}`` as used by the QOBLIB models.
        path:      Directory holding ``arcs.dat`` and ``terms.dat``.
    """

    n_nodes: int
    edges: dict[tuple[int, int], int]
    terminals: dict[int, list[int]]
    roots: dict[int, int]
    name: str = ""
    path: Path | None = None

    directory = "04-steiner"
    _objective = re.compile(r"Total Cost (-?[\d.]+)")

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> Steiner:
        """Read an instance from a directory with ``arcs.dat`` and ``terms.dat``.

        ``param.dat`` and ``roots.dat`` are read when present.
        """
        path = Path(path)
        edges = {}
        for u, v, cost in _rows(path / "arcs.dat"):
            edges[tuple(sorted((int(u), int(v))))] = float(cost) if "." in cost else int(cost)
        terminals: dict[int, list[int]] = {}
        for node, net in _rows(path / "terms.dat"):
            terminals.setdefault(int(net), []).append(int(node))
        params = dict(_rows(path / "param.dat"))
        n_nodes = int(params.get("nodes", max((v for _, v in edges), default=0)))
        roots = {int(net): int(node) for node, net in _rows(path / "roots.dat")}
        return cls(n_nodes, edges, terminals, roots, name or path.name, path)

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for path in index().under(f"{cls.directory}/instances/"):
            parts = path.split("/")
            if len(parts) == 4 and parts[3] in _FILES:
                found.setdefault(parts[2], []).append(path)
        return found

    @classmethod
    def _build(cls, name: str, paths: list[Path]) -> Steiner:
        return cls.from_file(paths[0].parent, name=name)

    def _parse_solution(self, text: str) -> list[tuple[int, int, int]]:
        return [tuple(map(int, line.split()[:3])) for line in data_lines(text)]

    def _format_solution(self, solution) -> str:
        return "".join(f"{u} {v} {net}\n" for u, v, net in solution)

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        directory = self._instance_path()
        return ["--arcs", directory / "arcs.dat", "--terms", directory / "terms.dat", "--sol", solution]
