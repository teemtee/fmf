""" Flexible Metadata Format """

from __future__ import annotations

import importlib.metadata

from fmf.base import Tree
from fmf.context import Context
from fmf.utils import filter

__version__ = importlib.metadata.version("fmf")

__all__ = [
    "Context",
    "Tree",
    "filter",
    ]
