""" Flexible Metadata Format """

# Version is replaced before building the package
__version__ = 'running from the source'

__all__ = [
    "Context",
    "Tree",
    "filter",
    ]

from fmf.base import Tree
from fmf.context import Context
from fmf.utils import filter
