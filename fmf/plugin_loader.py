"""Plugin Registry for FMF - manages built-in plugins."""

from typing import List, Optional, Type

from fmf.plugin import Plugin
from fmf.utils import log


class PluginRegistry:
    """Registry for built-in FMF plugins."""

    def __init__(self):
        self._plugins: List[Type[Plugin]] = []

    def register(self, plugin_class: Type[Plugin]) -> None:
        """Register a plugin class."""
        if not issubclass(plugin_class, Plugin):
            raise ValueError(f"{plugin_class} is not a Plugin subclass")
        if plugin_class not in self._plugins:
            self._plugins.append(plugin_class)
            log.debug(f"Registered plugin: {plugin_class.__name__}")

    def load_from_config(self, config: dict) -> None:
        """Validate plugin names and apply priority overrides from .fmf/config."""
        plugin_names = config.get("plugins", [])
        if not isinstance(plugin_names, list):
            log.warning(f"Config 'plugins' should be a list, got {type(plugin_names)}")
            return

        from fmf.plugins import PLUGIN_NAMES
        for name in plugin_names:
            if not isinstance(name, str):
                log.warning(f"Plugin name should be a string, got {type(name)}")
            elif name not in PLUGIN_NAMES:
                log.warning(f"Unknown plugin '{name}'. "
                            f"Available: {', '.join(PLUGIN_NAMES.keys())}")

        # Apply priority overrides from config
        # Format: plugin_name: { priority: 120 }
        for plugin_name, plugin_class in PLUGIN_NAMES.items():
            if plugin_name in config and isinstance(config[plugin_name], dict):
                priority = config[plugin_name].get("priority")
                if priority is not None:
                    if isinstance(priority, int) and 0 <= priority <= 200:
                        plugin_class.priority = priority
                        log.debug(f"Override {plugin_name} priority to {priority}")
                    else:
                        log.warning(f"Invalid priority for {plugin_name}: {priority} "
                                    f"(must be int 0-200)")

    def get_plugin_for_file(self, filename: str) -> Optional[Type[Plugin]]:
        """Find the best plugin to handle a file by priority."""
        self._ensure_plugins_loaded()

        candidates = []
        for plugin_class in self._plugins:
            try:
                if plugin_class().can_handle(filename):
                    candidates.append((plugin_class, plugin_class.priority))
            except Exception as error:
                log.debug(f"Plugin {plugin_class.__name__} "
                          f"can_handle failed: {error}")

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return None

    def _ensure_plugins_loaded(self) -> None:
        """Reload plugins if registry is empty (after clear() in tests)."""
        if not self._plugins:
            import importlib

            import fmf.plugins
            importlib.reload(fmf.plugins)

    def clear(self) -> None:
        """Clear all registered plugins (for tests)."""
        self._plugins.clear()


_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry
