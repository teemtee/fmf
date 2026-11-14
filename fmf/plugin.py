"""Base class for fmf metadata plugins."""

from abc import ABC, abstractmethod
from inspect import isabstract
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Type

from fmf._compat.metadata import entry_points
from fmf.utils import FileError, dict_to_yaml


class Plugin(ABC):
    """Read and write metadata using a format-specific implementation."""

    #: Section of ``.fmf/config`` used by this plugin.
    CONFIG_SECTION: ClassVar[str]

    #: Plugin classes discovered through entry points, in discovery order.
    _plugins: ClassVar[List[Type['Plugin']]] = []
    _discovered: ClassVar[bool] = False

    @classmethod
    def register(cls, plugin_class: Type['Plugin']) -> None:
        """Register a concrete plugin class once."""
        if not isinstance(plugin_class, type) or not issubclass(plugin_class, Plugin):
            raise ValueError(f"{plugin_class} is not a Plugin subclass")
        if isabstract(plugin_class):
            raise ValueError(f"{plugin_class.__name__} is abstract")
        if not isinstance(getattr(plugin_class, 'CONFIG_SECTION', None), str):
            raise ValueError(f"{plugin_class.__name__} must define CONFIG_SECTION")
        if plugin_class not in Plugin._plugins:
            Plugin._plugins.append(plugin_class)

    @classmethod
    def discover(cls) -> None:
        """Load metadata plugin entry points once per process."""
        if Plugin._discovered:
            return
        for entry_point in entry_points(group='fmf.plugins'):
            try:
                cls.register(entry_point.load())
            except Exception as error:
                raise FileError(f"Failed to load plugin '{entry_point.name}': {error}") from error
        Plugin._discovered = True

    @classmethod
    def for_tree(cls, config: Dict[str, Any]) -> List['Plugin']:
        """Reuse configured instances within a tree, keeping trees isolated."""
        cls.discover()
        instances = []
        for plugin_class in Plugin._plugins:
            instance = plugin_class()
            instance.read_config(config)
            instances.append(instance)
        return instances

    @staticmethod
    def for_file(filename: str, instances: List['Plugin']) -> Optional['Plugin']:
        """Select an instance that accepts the file."""
        return next((plugin for plugin in instances if plugin.can_handle(filename)), None)

    def config_section_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return this plugin's configuration mapping, empty when omitted."""
        section = config.get(self.CONFIG_SECTION, {})
        if not isinstance(section, dict):
            raise FileError(f"Plugin config '{self.CONFIG_SECTION}' must be a mapping")
        return section

    @abstractmethod
    def read_config(self, config: Dict[str, Any]) -> None:
        """Read this plugin's section from the full config once per tree."""

    @abstractmethod
    def can_handle(self, filename: str) -> bool:
        """Return whether the plugin can read the given file."""

    @abstractmethod
    def read(self, filename: str) -> Dict[str, Any]:
        """Read a file into raw metadata, including hierarchy and merge keys."""

    def write(
            self,
            filename: str,
            hierarchy: List[str],
            data: Dict[str, Any],
            append_dict: Dict[str, Any],
            modified_dict: Dict[str, Any],
            deleted_items: List[str]) -> None:
        """Write complete raw source data, retaining ``key+``/``key-`` keys.

        ``hierarchy`` locates the edited node within the source. The three
        operation arguments are reserved for non-YAML writers and currently
        arrive empty; ``deleted_items`` cannot encode valued subtraction.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support writing")

    def _write_fmf_fallback(self, destination: Path, data: Dict[str, Any]) -> None:
        """Create a .fmf sidecar from raw data, refusing to overwrite a file."""
        destination = Path(destination)
        if destination.suffix != '.fmf':
            raise FileError(f"Sidecar destination must end in .fmf: {destination}")
        with destination.open('x', encoding='utf-8') as stream:
            stream.write(dict_to_yaml(data))
