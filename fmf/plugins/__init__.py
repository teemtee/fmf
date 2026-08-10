"""
FMF Plugins Package

All built-in plugins are registered here.
"""

from fmf.plugin_loader import get_registry
# Import and register all built-in plugins
from fmf.plugins.fmf import FmfPlugin  # noqa: F401

# Register built-in plugins
_registry = get_registry()
_registry.register(FmfPlugin)

# Plugin name mapping for config
PLUGIN_NAMES = {
    'fmf': FmfPlugin,
    # Future plugins will be added here:
    # 'bash': BashPlugin,
    # 'pytest': PytestPlugin,
    }

__all__ = ['PLUGIN_NAMES']
