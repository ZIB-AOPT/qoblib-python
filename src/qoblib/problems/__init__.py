"""Built-in problem-class plugins for QOBLIB.

Importing this package registers all built-in :class:`~qoblib.Problem`
subclasses in the global registry.  It is imported automatically by
``qoblib.__init__``, so end-users never need to import it directly.

Third-party plugins can register themselves via::

    import qoblib

    @qoblib.register_problem
    class MyProblem(qoblib.Problem):
        slug = "myproblem"
        ...
"""

from qoblib.problems import (
    birkhoff,
    independentset,
    labs,
    marketsplit,
    network,
    portfolio,
    routing,
    sports,
    steiner,
    topology,
)

__all__ = [
    "birkhoff",
    "independentset",
    "labs",
    "marketsplit",
    "network",
    "portfolio",
    "routing",
    "sports",
    "steiner",
    "topology",
]
