"""Python interface to QOBLIB, the Quantum Optimization Benchmarking Library.

Every problem of https://github.com/ZIB-AOPT/QOBLIB is one class, and every
object of such a class is one instance::

    from qoblib import MarketSplit

    MarketSplit.instances()                    # names, works offline
    MarketSplit.download()                     # all instances and solutions
    problem = MarketSplit.load("ms_03_050_002")
    problem.check(problem.best_known.solution)
"""
from qoblib._base import BestKnown, CheckResult, Problem
from qoblib._download import cache_dir
from qoblib._index import REPOSITORY, QoblibError, get_ref, set_ref
from qoblib.problems import PROBLEMS, MarketSplit

__version__ = "0.2.0"

__all__ = [
    "PROBLEMS",
    "REPOSITORY",
    "BestKnown",
    "CheckResult",
    "MarketSplit",
    "Problem",
    "QoblibError",
    "__version__",
    "cache_dir",
    "get_ref",
    "set_ref",
]
