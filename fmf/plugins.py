"""
Python module defining fmf plugin functionality.
"""

from __future__ import annotations

import importlib
import os
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint
    from types import ModuleType
    from typing import ClassVar, Final


plugins_explored: bool = False
meta_plugins: dict[str, type[FMFPlugin]] = {}


class FMFPlugin:
    """
    Fmf plugin metadata definition.

    Subclass this class definition in order to recursively extend fmf plugins.
    """
    entry_point_name: ClassVar[str | None] = "fmf.plugins"
    """
    Entrypoints to be loaded.

    .. seealso:: :py:meth:`load_from_entry_points`
    """
    package_name: ClassVar[str | None] = None
    """
    Packages to be loaded.

    .. seealso:: :py:meth:`load_from_package`
    """
    environment_name: ClassVar[str | None] = "FMF_PLUGIN"
    """
    Environment names to be loaded.

    .. seealso:: :py:meth:`load_from_environment`
    """
    _entry_points_loaded: Final[ClassVar[dict[str, list[EntryPoint]]]] = {}
    """Entrypoint plugins loaded."""
    _packages_loaded: Final[ClassVar[dict[str, ModuleType | None]]] = {}
    """Package plugins loaded."""
    _environments_loaded: Final[ClassVar[dict[str, list[ModuleType | Path]]]] = {}
    """Environment plugins loaded."""

    @classmethod
    def load_from_entry_point(cls) -> None:
        """
        Load plugins from plugin metadata class's entrypoints.

        The entrypoints should point should have unique names w.r.t. the entrypoint used
        """
        # Early exit if the plugin metadata does not define an entrypoint to load
        # or it is already loaded
        if not cls.entry_point_name or cls.entry_point_name in cls._entry_points_loaded:
            return
        plugins = []
        cls._entry_points_loaded[cls.entry_point_name] = plugins
        for ep in entry_points(group=cls.entry_point_name):
            try:
                ep.load()
            except ImportError:
                continue
            plugins.append(ep)

    @classmethod
    def load_from_package(cls) -> None:
        """
        Load plugins from python package.

        The ``__init__`` file determines how plugin modules are loaded.
        """
        # Early exit if the plugin metadata does not define a package to load or
        # it is already loaded
        if not cls.package_name or cls.package_name in cls._packages_loaded:
            return
        # Make sure the package is marked as resolved
        cls._packages_loaded[cls.package_name] = None
        try:
            module = importlib.import_module(cls.package_name)
            cls._packages_loaded[cls.package_name] = module
        except ImportError:
            return

    @classmethod
    def load_from_environment(cls) -> None:
        """
        Load plugins from environment variable paths.

        The environment variable
        """
        # Early exit if the plugin metadata does not define a package to load or
        # it is already loaded
        if not cls.environment_name or cls.environment_name in cls._environments_loaded:
            return
        plugins = []
        cls._environments_loaded[cls.environment_name] = plugins
        env_paths = os.environ[cls.environment_name]
        # Early exit if the environment
        if not env_paths:
            return
        for path in env_paths.split(os.pathsep):
            try:
                module = importlib.import_module(path)
                plugins.append(module)
            except ImportError:
                path = os.path.expandvars(os.path.expanduser(path))
                path = Path(path)
                if not path.exists():
                    continue
                path = path.resolve()
                # TODO: Parse list of python/os paths that should be loaded
                pass

    @classmethod
    def load_plugins(cls) -> None:
        """Load plugins defined in all supported sources."""
        cls.load_from_entry_point()
        cls.load_from_package()
        cls.load_from_environment()

    def __init_subclass__(cls) -> None:
        cls.load_plugins()


# Load all FMF plugins recursively
FMFPlugin.load_plugins()
