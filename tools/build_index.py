"""Regenerate src/qoblib/index.json from the QOBLIB repository.

Usage: uv run tools/build_index.py [ref]    (ref defaults to "main")
"""
import sys

from qoblib._index import write_bundled_index

if __name__ == "__main__":
    print(write_bundled_index(*sys.argv[1:2]))
