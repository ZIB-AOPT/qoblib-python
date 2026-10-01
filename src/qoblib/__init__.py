"""Python interface to QOBLIB, the Quantum Optimization Benchmarking Library.

Every problem of https://github.com/ZIB-AOPT/QOBLIB is one class, and every
object of such a class is one instance::

    from qoblib import MarketSplit

    MarketSplit.instances()                    # names, works offline
    MarketSplit.download()                     # all instances and solutions
    MarketSplit.download(dest="data")          # ... into a directory of your choice
    problem = MarketSplit.load("ms_03_050_002")
    problem.check(problem.best_known.solution)
"""
from importlib.metadata import version as _version

from qoblib._base import BestKnown, CheckResult, Problem
from qoblib.cli import download
from qoblib._download import cache_dir
from qoblib._index import REPOSITORY, QoblibError, get_ref, set_ref
from qoblib.problems import (
    PROBLEMS,
    Birkhoff,
    IndependentSet,
    Labs,
    MarketSplit,
    Network,
    Portfolio,
    Routing,
    Sports,
    Steiner,
    Topology,
)

__version__ = _version("qoblib")

__all__ = [
    "PROBLEMS",
    "REPOSITORY",
    "BestKnown",
    "Birkhoff",
    "CheckResult",
    "IndependentSet",
    "Labs",
    "MarketSplit",
    "Network",
    "Portfolio",
    "Problem",
    "QoblibError",
    "Routing",
    "Sports",
    "Steiner",
    "Topology",
    "__version__",
    "cache_dir",
    "download",
    "get_ref",
    "set_ref",
]
