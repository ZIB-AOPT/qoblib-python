"""Sports Scheduling (05-sports): time-constrained double round-robin
tournaments in the ITC2021 format."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from qoblib._base import Problem
from qoblib._download import open_text, strip_compression
from qoblib._index import index


@dataclass(eq=False)
class Sports(Problem):
    """One ITC2021 tournament instance.

    A solution is a list of ``(home, away, slot)`` tuples of team and slot
    ids. QOBLIB ships no checker for this problem, so :meth:`check` raises a
    :class:`~qoblib.QoblibError`.

    Attributes:
        teams: Team names; the position is the team id.
        slots: Slot names; the position is the slot id.
        root:  The parsed ``<Instance>`` XML element, which holds the
               constraints (see the ITC2021 format description).
    """

    teams: list[str]
    slots: list[str]
    root: ET.Element
    name: str = ""
    path: Path | None = None

    directory = "05-sports"

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> Sports:
        """Read an instance from an ITC2021 ``.xml`` file (optionally compressed)."""
        path = Path(path)
        with open_text(path) as handle:
            root = ET.fromstring(handle.read())

        def names(tag: str) -> list[str]:
            elements = sorted(root.iter(tag), key=lambda element: int(element.get("id")))
            return [element.get("name") for element in elements]

        name = name or Path(strip_compression(path.name)).stem
        return cls(names("team"), names("slot"), root, name, path)

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        paths = index().under(f"{cls.directory}/instances/")
        return {path.split("/")[-1].removesuffix(".xml.gz"): [path] for path in paths}

    @classmethod
    def _solution_files(cls) -> dict[str, tuple[str, bool]]:
        # Schedules are the .xml files; a .opt.sol next to one marks it optimal.
        optimal = super()._solution_files()
        found = {}
        for path in index().under(f"{cls.directory}/solutions/"):
            if path.endswith(".xml.gz"):
                name = path.split("/")[-1].removesuffix(".xml.gz")
                found[name] = (path, name in optimal)
        return found

    def _parse_solution(self, text: str) -> list[tuple[int, int, int]]:
        matches = ET.fromstring(text).iter("ScheduledMatch")
        return [(int(m.get("home")), int(m.get("away")), int(m.get("slot"))) for m in matches]

    def _format_solution(self, solution) -> str:
        games = "".join(
            f'    <ScheduledMatch home="{home}" away="{away}" slot="{slot}"/>\n'
            for home, away, slot in solution
        )
        return f"<Solution>\n  <Games>\n{games}  </Games>\n</Solution>\n"
