"""Plugin Registry for FMF - discovers plugins via entry points."""

from importlib.metadata import entry_points
from typing import Any, Dict, Iterable, List, Optional, Type

from fmf.plugin import Plugin
from fmf.utils import log

# Entry point group under which built-in and third-party plugins are advertised.
# See the ``[project.entry-points."fmf.plugins"]`` section in ``pyproject.toml``.
ENTRY_POINT_GROUP = "fmf.plugins"


def _iter_entry_points(group: str) -> Iterable:
    """Return entry points for the given group (Python 3.9+ compatible)."""
    discovered = entry_points()
    # Python 3.10+ returns an EntryPoints object with select(),
    # Python 3.9 returns a plain dict keyed by group name.
    if hasattr(discovered, "select"):
        return discovered.select(group=group)
    return discovered.get(group, [])  # type: ignore[attr-defined]  # Python 3.9


class PluginRegistry:
    """
    Registry for FMF metadata loader plugins discovered via entry points.

    Plugin instances are cached and reused for the whole loading run. A tree
    can contain thousands of ``.fmf`` files and each ``Plugin`` construction
    is comparatively expensive (for example ``FmfPlugin`` builds a
    ``ruamel.yaml.YAML`` parser in its ``__init__``, which costs roughly a
    third of what parsing a small file costs). Constructing a fresh instance
    for every file -- once just to test :meth:`Plugin.can_handle` and once
    more to actually read -- added a significant, avoidable per-file tax on
    large trees. Caching one instance per plugin class removes it.

    This is safe because plugins are effectively stateless per file:
    :meth:`Plugin.read` and :meth:`Plugin.write` take the filename as an
    argument, and :meth:`Plugin.read_config` is idempotent and applied once
    per tree via :meth:`configure`. The cache therefore assumes single
    threaded loading (fmf's model); it is not safe to share a registry across
    threads loading different trees concurrently.
    """

    def __init__(self) -> None:
        self._plugins: List[Type[Plugin]] = []
        self._instances: Dict[Type[Plugin], Plugin] = {}
        # Config applied to plugin instances via configure(); kept so that
        # instances created lazily afterwards get configured on creation too.
        self._config: Optional[Dict[str, Any]] = None
        self._discovered = False

    def register(self, plugin_class: Type[Plugin]) -> None:
        """Register a plugin class."""
        if not (isinstance(plugin_class, type) and issubclass(plugin_class, Plugin)):
            raise ValueError(f"{plugin_class} is not a Plugin subclass")
        if plugin_class not in self._plugins:
            self._plugins.append(plugin_class)
            log.debug(f"Registered plugin: {plugin_class.__name__}")

    def discover(self) -> None:
        """Discover and register all plugins advertised via entry points."""
        for entry_point in _iter_entry_points(ENTRY_POINT_GROUP):
            try:
                plugin_class = entry_point.load()
            except Exception as error:
                log.warning(f"Failed to load plugin '{entry_point.name}': {error}")
                continue
            try:
                self.register(plugin_class)
            except ValueError as error:
                log.warning(f"Ignoring invalid plugin '{entry_point.name}': {error}")
        self._discovered = True

    def _ensure_plugins_loaded(self) -> None:
        """Discover plugins from entry points if not done yet."""
        if not self._discovered:
            self.discover()

    def _get_instance(self, plugin_class: Type[Plugin]) -> Plugin:
        """
        Return the cached instance for a plugin class, creating it on demand.

        Newly created instances are configured with the most recent config
        passed to :meth:`configure` so they behave consistently regardless of
        whether they existed when the tree config was applied.
        """
        instance = self._instances.get(plugin_class)
        if instance is None:
            instance = plugin_class()
            if self._config is not None:
                instance.read_config(self._config)
            self._instances[plugin_class] = instance
        return instance

    def configure(self, config: Dict[str, Any]) -> None:
        """
        Apply a tree's ``.fmf/config`` to all plugins, once per tree.

        The config is identical for every node in a tree, so each plugin only
        needs to read its own section once. This is called by the tree before
        loading instead of per file.
        """
        self._ensure_plugins_loaded()
        self._config = config
        for instance in self._instances.values():
            instance.read_config(config)

    def get_plugin_instance_for_file(self, filename: str) -> Optional[Plugin]:
        """
        Find the (cached) plugin instance to handle a file.

        When several plugins can handle the same file, the first one in
        registration order (i.e. the order the plugin modules were loaded)
        is used.
        """
        self._ensure_plugins_loaded()

        for plugin_class in self._plugins:
            try:
                instance = self._get_instance(plugin_class)
                if instance.can_handle(filename):
                    return instance
            except Exception as error:
                log.debug(f"Plugin {plugin_class.__name__} "
                          f"can_handle failed: {error}")
        return None

    def get_plugin_for_file(self, filename: str) -> Optional[Type[Plugin]]:
        """Find the plugin *class* to handle a file (see
        :meth:`get_plugin_instance_for_file`)."""
        instance = self.get_plugin_instance_for_file(filename)
        return type(instance) if instance is not None else None

    def clear(self) -> None:
        """Clear all registered plugins and cached instances (for tests)."""
        self._plugins.clear()
        self._instances.clear()
        self._config = None
        self._discovered = False


_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry
