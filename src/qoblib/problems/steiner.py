"""Node-Disjoint Steiner Tree problem plugin.

Given an undirected weighted graph and several groups of terminal nodes,
find a minimum-cost set of node-disjoint trees, one per group, each
connecting all terminals in its group.

Instance structure
------------------
Each instance lives in its own subdirectory (e.g. ``stp_s003_l1_t2_h0_rs97531/``)
containing:

- ``arcs.dat``  — edge list: ``node1 node2 weight`` (comments with ``#``)
- ``terms.dat`` — terminals: ``node network_id``

The checker CLI is::

    check_steiner --arcs <arcs.dat> --terms <terms.dat> --sol <solution.sol>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class SteinerInstance:
    """A parsed Steiner tree instance.

    Attributes:
        n_nodes:       Total number of distinct nodes in the graph.
        n_nets:        Number of distinct network (Steiner tree) groups.
        edges:         Dict ``(u, v) -> weight`` for all edges (undirected,
                       stored with ``u < v``).
        terminals:     Dict ``network_id -> frozenset of terminal node IDs``.
                       Each key is one net; the trees must be node-disjoint
                       across all nets.
        nodes:         Frozenset of all node IDs present in the graph.
        name:          Logical instance name.
        arcs_path:     Path to the ``arcs.dat`` file (used by the Rust checker).
        terms_path:    Path to the ``terms.dat`` file (used by the Rust checker).
    """

    n_nodes: int
    n_nets: int
    edges: Dict[Tuple[int, int], float]
    terminals: Dict[int, FrozenSet[int]]
    nodes: FrozenSet[int]
    name: str = ""
    arcs_path: Optional[Path] = None
    terms_path: Optional[Path] = None


@dataclass
class SteinerSolution:
    """A Steiner tree solution.

    Attributes:
        edges:  List of ``(node1, node2, network_id)`` triples that are
                selected for the solution.
        name:   Logical solution name.
        path:   Path to the ``.sol`` file (used by the Rust checker directly).
    """

    edges: List[Tuple[int, int, int]]
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise to the ``node1 node2 network_id`` format."""
        return "\n".join(f"{u} {v} {nid}" for u, v, nid in self.edges)


@register_problem
class SteinerProblem(Problem):
    """Plugin for the Node-Disjoint Steiner Tree problem class.

    Quickstart::

        import qoblib
        st = qoblib.get_problem("steiner")
        inst = st.load_instance("stp_s003_l1_t2_h0_rs97531")
        sol  = st.load_solution("stp_s003_l1_t2_h0_rs97531")

        print(inst.n_nodes, inst.n_nets)       # graph dimensions
        print(inst.nodes)                       # frozenset of all node IDs
        print(inst.terminals)                   # {net_id -> frozenset of terminal nodes}
        print(inst.edges)                       # {(u, v) -> weight}

        result = st.check_solution(inst, sol)
        print(result.status, result.objective)  # total selected edge weight
    """

    slug = "steiner"
    description = "Node-Disjoint Steiner Tree"

    def load_instance(self, name: str) -> SteinerInstance:
        """Fetch and parse the arcs and terms files for *name*.

        Downloads both files; the returned object's ``arcs_path`` and
        ``terms_path`` attributes point to the cached local copies for use
        by the Rust checker.
        """
        arcs_path = self.fetch(f"{name}/arcs.dat", kind="instance")
        terms_path = self.fetch(f"{name}/terms.dat", kind="instance")
        return _parse_instance(arcs_path, terms_path, name)

    def load_solution(self, name: str) -> SteinerSolution:
        """Fetch and parse the solution file for *name*."""
        path = self.fetch(name, kind="solution")
        sol_edges = _parse_sol(path)
        return SteinerSolution(edges=sol_edges, name=name, path=path)

    def compute_objective(
        self,
        instance: SteinerInstance,
        solution: SteinerSolution,
    ) -> Optional[float]:
        """Return the total edge weight of the selected solution edges."""
        return sum(
            instance.edges.get((min(u, v), max(u, v)), 0.0)
            for u, v, _ in solution.edges
        )


# ------------------------------------------------------------------ file parsers


def _parse_instance(
    arcs_path: Path, terms_path: Path, name: str = ""
) -> SteinerInstance:
    """Parse arcs.dat and terms.dat into a :class:`SteinerInstance`."""
    edges = _parse_arcs(arcs_path)
    terminals_mutable = _parse_terms_mutable(terms_path)

    # Derive node set from all edge endpoints
    node_set: set[int] = set()
    for u, v in edges:
        node_set.add(u)
        node_set.add(v)
    # Also include any terminal nodes not mentioned in the edge list
    for net_nodes in terminals_mutable.values():
        node_set.update(net_nodes)

    terminals: Dict[int, FrozenSet[int]] = {
        nid: frozenset(nodes) for nid, nodes in terminals_mutable.items()
    }

    return SteinerInstance(
        n_nodes=len(node_set),
        n_nets=len(terminals),
        edges=edges,
        terminals=terminals,
        nodes=frozenset(node_set),
        name=name,
        arcs_path=arcs_path,
        terms_path=terms_path,
    )


def _parse_arcs(path: Path) -> Dict[Tuple[int, int], float]:
    edges: Dict[Tuple[int, int], float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            u, v, w = int(parts[0]), int(parts[1]), float(parts[2])
            edges[(min(u, v), max(u, v))] = w
    return edges


def _parse_terms_mutable(path: Path) -> Dict[int, Set[int]]:
    terminals: Dict[int, Set[int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            node, nid = int(parts[0]), int(parts[1])
            terminals.setdefault(nid, set()).add(node)
    return terminals


def _parse_sol(path: Path) -> List[Tuple[int, int, int]]:
    edges: List[Tuple[int, int, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            edges.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return edges
