"""Entry point selection compatibility for Python 3.9."""

import sys

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

__all__ = ["entry_points"]
